-- Schema v2: deals (unique deal) + deal_mentions (article-level)
-- Safe to re-run: drops and recreates both tables.

drop table if exists deal_mentions cascade;
drop table if exists deals cascade;

create table deals (
    id bigserial primary key,
    data_anuncio date,
    alvo text,
    alvo_normalizado text,
    alvo_company_id bigint,           -- FK futuro para tabela companies
    comprador text,
    comprador_normalizado text,
    comprador_company_id bigint,      -- FK futuro para tabela companies
    regiao text check (regiao in ('BR', 'Global')),
    pais text,
    setor text,
    subsetor text,
    valor_usd numeric,
    valor_brl numeric,
    valor_status text check (valor_status in ('divulgado', 'nao_divulgado', 'desconhecido')),
    tipo_transacao text,
    status text,
    resumo_uma_frase text,
    last_emailed_at timestamptz,      -- último envio em newsletter (NULL = nunca)
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Unique constraint impede inserir o mesmo (alvo, comprador) duas vezes.
-- Partial index: só vale quando ambos os campos existem (permite linhas
-- com partes desconhecidas sem bloquear).
create unique index if not exists deals_dedup_idx
    on deals (alvo_normalizado, comprador_normalizado)
    where alvo_normalizado is not null and comprador_normalizado is not null;

create index if not exists deals_data_anuncio_idx on deals (data_anuncio desc);
create index if not exists deals_regiao_idx on deals (regiao);
create index if not exists deals_setor_idx on deals (setor);
create index if not exists deals_valor_usd_idx on deals (valor_usd desc);
create index if not exists deals_last_emailed_at_idx on deals (last_emailed_at);
create index if not exists deals_alvo_company_idx on deals (alvo_company_id);
create index if not exists deals_comprador_company_idx on deals (comprador_company_id);

create table deal_mentions (
    id bigserial primary key,
    deal_id bigint not null references deals(id) on delete cascade,
    hash_dedup text unique not null,
    titulo text not null,
    url text not null,
    fonte text not null,
    data_publicacao timestamptz,
    texto_bruto text,
    created_at timestamptz not null default now()
);

create index if not exists deal_mentions_deal_id_idx on deal_mentions (deal_id);
create index if not exists deal_mentions_fonte_idx on deal_mentions (fonte);

-- RLS aberto em Fase 1 (publishable key lê/escreve). Apertar depois.
alter table deals enable row level security;
alter table deal_mentions enable row level security;

drop policy if exists "deals_all" on deals;
create policy "deals_all" on deals for all using (true) with check (true);

drop policy if exists "deal_mentions_all" on deal_mentions;
create policy "deal_mentions_all" on deal_mentions for all using (true) with check (true);
