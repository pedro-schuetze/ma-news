-- Migration 002: distinguir "valor não divulgado" de "matéria não falou
-- do valor". Antes, ambos viravam valor_usd = NULL; agora separamos.
--
-- Valores possíveis:
--   'divulgado'      -> valor_usd/valor_brl preenchido
--   'nao_divulgado'  -> matéria explicitamente diz "não divulgado/undisclosed"
--   'desconhecido'   -> matéria simplesmente não menciona valor
--   NULL             -> deal antigo, sem classificação (será tratado como desconhecido)
--
-- Rodar uma vez no SQL Editor do Supabase. Idempotente.

alter table deals
    add column if not exists valor_status text;

-- Constraint só se ainda não existir (Postgres não tem IF NOT EXISTS para constraints)
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'deals_valor_status_check'
    ) then
        alter table deals
            add constraint deals_valor_status_check
            check (valor_status in ('divulgado', 'nao_divulgado', 'desconhecido') or valor_status is null);
    end if;
end$$;

-- Backfill: deals com valor preenchido = 'divulgado'; demais ficam NULL (desconhecido)
update deals
   set valor_status = 'divulgado'
 where valor_status is null
   and (valor_usd is not null or valor_brl is not null);
