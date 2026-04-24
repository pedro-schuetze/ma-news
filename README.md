# m&a_news

Pipeline diário que coleta notícias de M&A (Brasil + global), extrai campos estruturados via Claude, salva no Supabase e (Fase 2+) dispara newsletter.

## Setup

1. `python -m venv .venv && .venv/Scripts/activate` (Windows) ou `source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. Copie `.env.example` para `.env` e preencha as credenciais.
4. No Supabase SQL Editor, rode `db/schema.sql`.
5. `python pipeline.py` para rodar uma coleta de 24h.

## Estrutura

- `collectors/` — fontes (RSS por enquanto)
- `extractor/` — chamadas ao Claude
- `db/` — schema + cliente Supabase
- `pipeline.py` — orquestrador

## Fases

- **Fase 1** (atual): coleta Brazil Journal + extração + dedup + insert no Supabase
- **Fase 2**: newsletter HTML via Gmail SMTP
- **Fase 3**: fontes adicionais (Pipeline, Neofeed, Reuters, Bloomberg, PR Newswire)
- **Fase 4**: UI Streamlit com filtros
- **Fase 5**: GitHub Actions cron diário
