from __future__ import annotations

import json
import os

from anthropic import Anthropic

SYSTEM_PROMPT = """Você é um analista de M&A. Recebe o título, o resumo e (opcionalmente) o corpo de uma notícia e retorna APENAS um JSON com os campos abaixo.

Regras:
- Se a notícia NÃO for sobre uma transação de M&A real (aquisição, fusão, compra de participação, joint venture, IPO com componente de M&A, venda de ativo, follow-on relevante), retorne `{"is_ma": false}` e nada mais.
- Se for M&A, retorne `is_ma: true` e preencha o máximo de campos possível. Use `null` para o que não conseguir inferir.
- `regiao`: "BR" se a transação for primariamente brasileira (partes brasileiras ou ativos no Brasil), senão "Global".
- `valor_usd`: valor total da transação em USD (número, sem formatação). Converta BRL→USD usando taxa aproximada 5,0 se necessário. Se "undisclosed"/"não divulgado", use null.
- `alvo` e `comprador`: APENAS o nome curto e canônico da empresa, sem descrições entre parênteses, sem adjetivos de país (ex: "Ecopetrol" e não "Colombia's Ecopetrol"), sem sufixos societários opcionais. Use o nome pelo qual a empresa é conhecida comercialmente.
- `tipo_transacao`: um de "aquisição", "fusão", "joint venture", "venda de ativo", "IPO", "follow-on", "investimento minoritário", "outro". Regras: se a operação resulta (ou oferta busca resultar) em controle (>50%) do alvo, use "aquisição" mesmo que a tranche inicial seja minoritária (ex.: compra de 26% + OPA para 51% é "aquisição"). Use "investimento minoritário" somente quando NÃO há caminho para controle.
- `status`: "anunciada" ou "concluída".
- `setor`: categoria ampla (ex: "Tecnologia", "Saúde", "Energia", "Serviços Financeiros", "Varejo", "Indústria", "Infraestrutura", "Agronegócio", "Educação", "Imobiliário", "Mídia", "Telecom").
- `resumo_uma_frase`: UMA frase em português do Brasil, começando com verbo no passado, descrevendo o deal com alvo, comprador e valor (se houver). Máx 200 caracteres.

Responda SOMENTE com o JSON, sem markdown, sem explicações."""

RESPONSE_SCHEMA_HINT = """{
  "is_ma": true,
  "regiao": "BR" | "Global",
  "pais": string | null,
  "alvo": string | null,
  "comprador": string | null,
  "setor": string | null,
  "subsetor": string | null,
  "valor_usd": number | null,
  "valor_brl": number | null,
  "tipo_transacao": string | null,
  "status": string | null,
  "resumo_uma_frase": string
}"""


def _build_user_message(titulo: str, resumo_fonte: str, corpo: str | None) -> str:
    parts = [f"Título: {titulo}", f"Resumo da fonte: {resumo_fonte or '(vazio)'}"]
    if corpo:
        parts.append(f"Corpo:\n{corpo[:6000]}")
    parts.append(f"\nRetorne o JSON no formato:\n{RESPONSE_SCHEMA_HINT}")
    return "\n\n".join(parts)


def extract(titulo: str, resumo_fonte: str, corpo: str | None = None) -> dict | None:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    message = client.messages.create(
        model=model,
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": _build_user_message(titulo, resumo_fonte, corpo)}],
    )

    text = "".join(block.text for block in message.content if block.type == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None

    if not data.get("is_ma"):
        return None
    return data
