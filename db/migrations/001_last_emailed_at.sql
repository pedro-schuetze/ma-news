-- Migration 001: rastrear último envio do deal por email para evitar
-- re-enviar a mesma transação em vários emails seguidos.
--
-- Rodar uma vez no SQL Editor do Supabase.
-- Idempotente (IF NOT EXISTS).

alter table deals
    add column if not exists last_emailed_at timestamptz;

create index if not exists deals_last_emailed_at_idx
    on deals (last_emailed_at);
