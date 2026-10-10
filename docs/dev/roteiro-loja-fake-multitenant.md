> **Substituído em 2026-10-10** por `sql/fase_b/teste_isolamento.sql` (roda em produção dentro de transação desfeita, sem deixar resto, e cobre comandos/IA). Este roteiro era para o Streamlit, que saiu do plano, e tem um erro: `numero_whatsapp` **não** é único no banco inteiro — o schema real é `UNIQUE (loja_id, numero_whatsapp)`.

# Roteiro: criar uma loja fake para testar isolamento multi-tenant

> Verificado contra o schema real do Supabase em 2026-09-11 (ver [specs/tecnica/02-modelo-de-dados.md](../specs/tecnica/02-modelo-de-dados.md)). Rode os comandos abaixo você mesmo no SQL Editor do Supabase (produção) — nenhum destes INSERTs foi executado por mim.

## O que este roteiro testa (e o que não testa)

Testa o **isolamento de dados no Postgres/Dashboard**: se uma segunda loja consegue existir sem que a Renato Motors veja os dados dela, e vice-versa (ver [regras-de-negocio/04-isolamento-multi-loja.md](../specs/regras-de-negocio/04-isolamento-multi-loja.md)).

**Não** testa o fluxo real de WhatsApp ponta a ponta para a loja nova — isso exigiria uma segunda instância Evolution API de verdade conectada no n8n. Aqui você simula a chegada de leads chamando a função `distribuir_lead` diretamente por SQL, o que é suficiente para validar isolamento de dados e round-robin.

## Passo 1 — Criar a loja fake

```sql
insert into public.lojas (nome, numero_whatsapp, instancia_evolution, ativa)
values ('Loja Teste Multitenant', '5511900000000', 'loja-teste-fake', true)
returning id;
```

Guarde o `id` retornado — é o `<LOJA_TESTE_ID>` usado nos passos seguintes.

## Passo 2 — Criar o código de acesso ao Dashboard

```sql
insert into public.loja_acesso (loja_id, codigo_acesso)
values ('<LOJA_TESTE_ID>', 'TST-20260911-FAKE')
returning *;
```

Esse é o código que você vai digitar na tela de login do Dashboard (`AUT-YYYYMMDD-XXXX` é só uma convenção de formato, não uma validação — qualquer string única em `codigo_acesso` funciona).

## Passo 3 — Criar vendedores e gerente fake

```sql
insert into public.vendedores (loja_id, nome, numero_whatsapp, status, ordem_fila)
values
  ('<LOJA_TESTE_ID>', 'Vendedor Fake 1', '5511911111111', 'ativo', 1),
  ('<LOJA_TESTE_ID>', 'Vendedor Fake 2', '5511922222222', 'ativo', 2);

insert into public.gerentes (loja_id, nome, numero_whatsapp, ativo)
values ('<LOJA_TESTE_ID>', 'Gerente Fake', '5511933333333', true);
```

`numero_whatsapp` é `UNIQUE` globalmente (não só por loja) em `vendedores` e `gerentes` — use números que não existam em nenhuma loja real.

## Passo 4 — Simular leads chegando (testa round-robin real)

Chame a função real de distribuição (7 argumentos, com `p_origem` — é a versão em uso, não a de 6 argumentos que é overload legado morto):

```sql
select * from public.distribuir_lead(
  '<LOJA_TESTE_ID>'::uuid,
  '5511944444444',
  'Cliente Teste 1',
  'Anuncio Teste',
  'Mensagem de teste',
  now(),
  'WhatsApp Direto'
);
```

Repita 3-4 vezes trocando `numero_cliente` (`p_numero_cliente`) — o retorno deve alternar `vendedor_nome` entre "Vendedor Fake 1" e "Vendedor Fake 2", confirmando que o round-robin dessa loja é independente do round-robin da Renato Motors.

## Passo 5 — Validar isolamento

**No Dashboard:**
1. Acesse a URL do app e faça login com `TST-20260911-FAKE`.
2. Confirme que só aparecem os 2 vendedores fake, o gerente fake, e os leads de teste — nada da Renato Motors.
3. Faça logout e login novamente com o código real da Renato Motors. Confirme que nada da "Loja Teste Multitenant" aparece lá.

**Direto no banco (cross-check):**
```sql
select loja_id, count(*) from public.leads group by 1;
select loja_id, count(*) from public.vendedores group by 1;
select loja_id, count(*) from public.gerentes group by 1;
```
Cada `loja_id` deve ter só os registros que você esperaria — nenhuma linha com `loja_id` errado.

## Passo 6 — Limpar depois do teste

```sql
delete from public.leads where loja_id = '<LOJA_TESTE_ID>';
delete from public.atividades where loja_id = '<LOJA_TESTE_ID>';
delete from public.mensagens_prontas where loja_id = '<LOJA_TESTE_ID>';
delete from public.vendedores where loja_id = '<LOJA_TESTE_ID>';
delete from public.gerentes where loja_id = '<LOJA_TESTE_ID>';
delete from public.loja_acesso where loja_id = '<LOJA_TESTE_ID>';
delete from public.lojas where id = '<LOJA_TESTE_ID>';
```

Alternativa mais simples se quiser manter a loja fake por mais tempo para outros testes: `update public.lojas set ativa = false where id = '<LOJA_TESTE_ID>';` — o login com o código dela passa a ser rejeitado (`validar_codigo` checa `ativa`), sem apagar nada.

## O que este teste não cobre (fica para quando for onboardar uma loja de verdade)

- Uma segunda instância Evolution API real recebendo mensagens de WhatsApp de verdade.
- O comportamento do workflow n8n com 2 instâncias simultâneas (o workflow hoje tem a chave da Evolution API de cada loja **hardcoded no nó**, não lida da coluna `lojas.evolution_api_key` — ver [specs/tecnica/04-integracao-evolution-api.md](../specs/tecnica/04-integracao-evolution-api.md). Isso significa que **onboardar uma loja nova hoje exige editar manualmente o workflow n8n**, não é self-service).
