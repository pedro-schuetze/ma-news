from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from db.client import get_client  # noqa: E402


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

_COUNTRY_FLAGS = {
    "brasil": "🇧🇷", "brazil": "🇧🇷",
    "estados unidos": "🇺🇸", "eua": "🇺🇸", "usa": "🇺🇸", "us": "🇺🇸", "united states": "🇺🇸",
    "colombia": "🇨🇴", "colômbia": "🇨🇴",
    "alemanha": "🇩🇪", "germany": "🇩🇪",
    "canada": "🇨🇦", "canadá": "🇨🇦",
    "italia": "🇮🇹", "itália": "🇮🇹", "italy": "🇮🇹",
    "franca": "🇫🇷", "frança": "🇫🇷", "france": "🇫🇷",
    "reino unido": "🇬🇧", "uk": "🇬🇧", "united kingdom": "🇬🇧",
    "espanha": "🇪🇸", "spain": "🇪🇸",
    "portugal": "🇵🇹",
    "japao": "🇯🇵", "japão": "🇯🇵", "japan": "🇯🇵",
    "china": "🇨🇳", "india": "🇮🇳", "índia": "🇮🇳",
    "mexico": "🇲🇽", "méxico": "🇲🇽",
    "argentina": "🇦🇷", "chile": "🇨🇱", "peru": "🇵🇪",
    "suica": "🇨🇭", "suíça": "🇨🇭", "switzerland": "🇨🇭",
    "holanda": "🇳🇱", "netherlands": "🇳🇱",
}


def _flag_for(pais: str | None, regiao: str | None) -> str:
    if pais:
        key = pais.strip().lower()
        if key in _COUNTRY_FLAGS:
            return _COUNTRY_FLAGS[key]
    if regiao == "BR":
        return "🇧🇷"
    return "🌐"


def _format_value(v_usd, v_brl) -> str:
    if v_usd is not None:
        v = float(v_usd)
        if v >= 1e9:
            return f"US$ {v / 1e9:.2f}bi"
        if v >= 1e6:
            return f"US$ {v / 1e6:.0f}M"
        return f"US$ {v / 1e3:.0f}k"
    if v_brl is not None:
        v = float(v_brl)
        if v >= 1e9:
            return f"R$ {v / 1e9:.2f}bi"
        if v >= 1e6:
            return f"R$ {v / 1e6:.0f}M"
        return f"R$ {v / 1e3:.0f}k"
    return "n/d"


def _format_date_str(d: date) -> str:
    return f"{d.day} de {_MESES[d.month - 1]} de {d.year}"


def fetch_recent_deals(lookback_hours: int = 30) -> list[dict]:
    """Busca deals criados nas últimas N horas (usamos created_at, não data_anuncio,
    para capturar deals processados hoje mesmo que o anúncio oficial seja mais antigo).
    Default 30h para dar folga em relação ao cron diário.
    """
    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    deals = (
        client.table("deals")
        .select("*")
        .gte("created_at", cutoff)
        .order("regiao")
        .order("valor_usd", desc=True, nullsfirst=False)
        .execute()
        .data
    )
    if not deals:
        return []

    deal_ids = [d["id"] for d in deals]
    mentions = (
        client.table("deal_mentions")
        .select("deal_id,titulo,url,fonte")
        .in_("deal_id", deal_ids)
        .execute()
        .data
    )

    by_deal: dict[int, list[dict]] = {}
    for m in mentions:
        by_deal.setdefault(m["deal_id"], []).append(m)
    for d in deals:
        d["mentions"] = by_deal.get(d["id"], [])

    return deals


def build_context(deals: list[dict]) -> dict:
    enriched = []
    for d in deals:
        enriched.append(
            {
                **d,
                "flag": _flag_for(d.get("pais"), d.get("regiao")),
                "valor_str": _format_value(d.get("valor_usd"), d.get("valor_brl")),
            }
        )

    brasil = [d for d in enriched if d.get("regiao") == "BR"]
    globais = [d for d in enriched if d.get("regiao") == "Global"]

    def _sort_by_value(items):
        return sorted(items, key=lambda x: (x.get("valor_usd") or 0), reverse=True)

    groups = []
    if brasil:
        groups.append({"label": "🇧🇷 BRASIL", "deals": _sort_by_value(brasil)})
    if globais:
        groups.append({"label": "🌐 GLOBAL", "deals": _sort_by_value(globais)})

    fontes_unicas = {m["fonte"] for d in enriched for m in d.get("mentions", [])}

    return {
        "data_str": _format_date_str(date.today()),
        "total": len(enriched),
        "brasil_count": len(brasil),
        "global_count": len(globais),
        "groups": groups,
        "sources_summary": f"{len(fontes_unicas)} fontes monitoradas",
    }


def render_html(context: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(_HERE)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("template.html")
    return tmpl.render(**context)


def send_email(html: str, subject: str, to_email: str) -> None:
    user = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(user, password)
        server.sendmail(user, [to_email], msg.as_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/send daily M&A newsletter")
    parser.add_argument("--send", action="store_true", help="Envia email via Gmail SMTP")
    parser.add_argument("--lookback-hours", type=int, default=30)
    parser.add_argument("--to", type=str, default=None, help="Override do destinatário")
    args = parser.parse_args()

    load_dotenv(override=True)

    deals = fetch_recent_deals(args.lookback_hours)
    print(f"[info] {len(deals)} deals encontrados nas últimas {args.lookback_hours}h")

    if not deals:
        print("[skip] nenhum deal novo — newsletter não gerada")
        return

    context = build_context(deals)
    html = render_html(context)

    subject = f"M&A News — {context['data_str']} ({context['total']} deals)"

    preview_path = _ROOT / "newsletter_preview.html"
    preview_path.write_text(html, encoding="utf-8")
    print(f"[ok] preview gerado em {preview_path}")

    if args.send:
        to_email = args.to or os.environ["NEWSLETTER_TO"]
        print(f"[info] enviando para {to_email}...")
        send_email(html, subject, to_email)
        print(f"[ok] enviada: {subject}")
    else:
        print(f"[dry] use --send para enviar. Assunto seria: {subject}")


if __name__ == "__main__":
    main()
