from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import date, datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

from db.client import get_client  # noqa: E402


_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
          "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _country_display(pais: str | None, regiao: str | None) -> str:
    """Exibe nome do país; se desconhecido, cai para 'Brasil' (BR) ou 'Internacional'."""
    if pais and pais.strip():
        return pais.strip()
    if regiao == "BR":
        return "Brasil"
    return "Internacional"


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


def _format_short_date(d) -> str:
    """28 abr para uso na seção 'caso você tenha perdido'."""
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d).date()
        except ValueError:
            return ""
    if isinstance(d, datetime):
        d = d.date()
    meses_curtos = ["jan", "fev", "mar", "abr", "mai", "jun",
                    "jul", "ago", "set", "out", "nov", "dez"]
    return f"{d.day} {meses_curtos[d.month - 1]}"


def _attach_mentions(client, deals: list[dict]) -> list[dict]:
    """Anexa lista de menções (titulo, url, fonte) a cada deal."""
    if not deals:
        return deals
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
        d["mention_count"] = len(d["mentions"])
    return deals


def fetch_recent_deals(lookback_hours: int = 30) -> list[dict]:
    """Busca deals criados nas últimas N horas, EXCLUINDO os que já foram
    enviados em newsletter recente (default últimos 7 dias, configurável via
    NEWSLETTER_DEDUP_DAYS).

    Aplica também threshold de exibição para Global (DISPLAY_MIN_USD_GLOBAL).
    BR nunca é filtrado por valor.
    """
    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    display_min_global = float(os.environ.get("DISPLAY_MIN_USD_GLOBAL", "500000000"))
    dedup_days = int(os.environ.get("NEWSLETTER_DEDUP_DAYS", "7"))
    dedup_cutoff = (datetime.now(timezone.utc) - timedelta(days=dedup_days)).isoformat()

    query = (
        client.table("deals")
        .select("*")
        .gte("created_at", cutoff)
        .or_(f"last_emailed_at.is.null,last_emailed_at.lt.{dedup_cutoff}")
        .order("regiao")
        .order("valor_usd", desc=True, nullsfirst=False)
    )
    deals = query.execute().data
    if not deals:
        return []

    deals = [
        d for d in deals
        if d.get("regiao") == "BR"
        or (d.get("valor_usd") is not None and float(d["valor_usd"]) >= display_min_global)
    ]
    if not deals:
        return []

    return _attach_mentions(client, deals)


def fetch_recap_deals(days: int = 7, top_n: int = 5,
                      exclude_ids: list[int] | None = None) -> list[dict]:
    """Top N deals dos últimos `days` dias por valor_usd (desempate: número
    de menções), excluindo os IDs informados.

    Aplica DISPLAY_MIN_USD_GLOBAL para Global. BR não filtrado por valor.
    Pensado para a seção 'Caso você tenha perdido'.
    """
    client = get_client()
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    display_min_global = float(os.environ.get("DISPLAY_MIN_USD_GLOBAL", "500000000"))

    deals = (
        client.table("deals")
        .select("*")
        .gte("data_anuncio", cutoff)
        .order("valor_usd", desc=True, nullsfirst=False)
        .execute()
        .data
    )
    if not deals:
        return []

    exclude = set(exclude_ids or [])
    filtered: list[dict] = []
    for d in deals:
        if d["id"] in exclude:
            continue
        if d.get("regiao") == "BR":
            filtered.append(d)
        elif d.get("valor_usd") is not None and float(d["valor_usd"]) >= display_min_global:
            filtered.append(d)

    if not filtered:
        return []

    # Anexa menções para usar como desempate.
    _attach_mentions(client, filtered)

    # Ordena por (valor_usd desc, mention_count desc).
    filtered.sort(
        key=lambda d: (
            float(d.get("valor_usd") or 0),
            int(d.get("mention_count") or 0),
        ),
        reverse=True,
    )
    return filtered[:top_n]


def mark_deals_emailed(deal_ids: list[int]) -> None:
    """Marca os deals como enviados (last_emailed_at = agora)."""
    if not deal_ids:
        return
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()
    client.table("deals").update({"last_emailed_at": now}).in_("id", deal_ids).execute()


def _enrich(deals: list[dict]) -> list[dict]:
    enriched = []
    for d in deals:
        enriched.append(
            {
                **d,
                "country_str": _country_display(d.get("pais"), d.get("regiao")),
                "valor_str": _format_value(d.get("valor_usd"), d.get("valor_brl")),
                "data_anuncio_short": _format_short_date(d.get("data_anuncio")),
            }
        )
    return enriched


def build_context(deals: list[dict], recap: list[dict] | None = None) -> dict:
    enriched = _enrich(deals)

    brasil = [d for d in enriched if d.get("regiao") == "BR"]
    globais = [d for d in enriched if d.get("regiao") == "Global"]

    def _sort_by_value(items):
        return sorted(items, key=lambda x: (x.get("valor_usd") or 0), reverse=True)

    groups = []
    if brasil:
        groups.append({"key": "brasil", "label": "Brasil", "deals": _sort_by_value(brasil)})
    if globais:
        groups.append({"key": "global", "label": "Global", "deals": _sort_by_value(globais)})

    fontes_unicas = {m["fonte"] for d in enriched for m in d.get("mentions", [])}

    recap_enriched = _enrich(recap or [])

    return {
        "data_str": _format_date_str(date.today()),
        "total": len(enriched),
        "brasil_count": len(brasil),
        "global_count": len(globais),
        "groups": groups,
        "recap": recap_enriched,
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
    parser.add_argument("--recap-days", type=int, default=7,
                        help="Janela do 'caso você tenha perdido' (default 7 dias)")
    parser.add_argument("--recap-top", type=int, default=5,
                        help="Quantos deals na seção de recap (default 5)")
    args = parser.parse_args()

    load_dotenv(override=True)

    deals = fetch_recent_deals(args.lookback_hours)
    print(f"[info] {len(deals)} deals novos (já filtrando os enviados nos últimos "
          f"{os.environ.get('NEWSLETTER_DEDUP_DAYS', '7')} dias)")

    today_ids = [d["id"] for d in deals]
    recap = fetch_recap_deals(days=args.recap_days, top_n=args.recap_top,
                              exclude_ids=today_ids)
    print(f"[info] {len(recap)} deals no recap dos últimos {args.recap_days} dias")

    if not deals and not recap:
        print("[skip] nada novo nem para recap — newsletter não gerada")
        return

    context = build_context(deals, recap=recap)
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
        # Marca como enviado SÓ depois do send_email retornar com sucesso,
        # para não 'queimar' deals se o SMTP falhar. Recap não é marcado
        # (a ideia é justamente lembrar de coisas já enviadas antes).
        if today_ids:
            mark_deals_emailed(today_ids)
            print(f"[ok] {len(today_ids)} deals marcados como enviados")
    else:
        print(f"[dry] use --send para enviar. Assunto seria: {subject}")


if __name__ == "__main__":
    main()
