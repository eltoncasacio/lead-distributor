# Runbook — fix race condition `distribuir_lead` (Renato Motors)

## Arquivos
- `backup-20260831/ROLLBACK_distribuir_lead.sql` — estado exato de antes (md5 `2fe1bc6ac396bea8727c5628b8cf56f9`)
- `backup-20260831/SNAPSHOT_estado.json` — fila, ponteiro, contadores, grants
- `FIX_distribuir_lead.sql` — correção (+14 linhas, 3 executáveis)

## Aplicar
Rodar `FIX_distribuir_lead.sql`. É um `CREATE OR REPLACE` único.
Sem DROP, sem ALTER TABLE, sem dados tocados, sem restart de n8n/Supabase.
Efeito na próxima chamada do RPC.

## Verificar (logo após aplicar)
```sql
-- 1) função trocada?
select md5(pg_get_functiondef(p.oid)) <> '2fe1bc6ac396bea8727c5628b8cf56f9' as trocou,
       prosrc like '%pg_advisory_xact_lock%' as tem_lock
from pg_proc p join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public' and p.proname='distribuir_lead' and p.pronargs=7;

-- 2) grants preservados?
select proacl from pg_proc where oid='public.distribuir_lead(uuid,varchar,varchar,varchar,text,timestamptz,varchar)'::regprocedure;

-- 3) fila intacta?
select v.nome as proximo from lojas l join vendedores v on v.id=l.proximo_vendedor_id
where l.id='<LOJA_ID>';
```
Depois: mandar 1 mensagem de teste no WhatsApp da loja e confirmar que chegou para 1 vendedor.

## Monitorar (rodar nos próximos dias)
```sql
-- deve voltar ZERO linhas a partir da data do fix
select a.numero_cliente, a.criado_em, va.nome, vb.nome
from leads a
join leads b on a.numero_cliente=b.numero_cliente and a.loja_id=b.loja_id and a.id<b.id
join vendedores va on va.id=a.vendedor_id
join vendedores vb on vb.id=b.vendedor_id
where a.loja_id='<LOJA_ID>'
  and abs(extract(epoch from (a.criado_em-b.criado_em))) < 5
  and a.vendedor_id is distinct from b.vendedor_id
  and a.criado_em > '2026-08-31'
order by a.criado_em desc;
```

## Rollback
Rodar `backup-20260831/ROLLBACK_distribuir_lead.sql`. Segundos, sem restart.
Gatilhos para reverter:
- erro no node "Distribuir Lead" do n8n (execuções com status error)
- lead deixando de chegar no vendedor
- execuções travando / timeout no RPC
