# Runbook — leads perdidos em silêncio (Renato Motors)

> Incidente do lado **n8n**, não SQL. Nenhuma função do Postgres é alterada. `distribuir_lead` e a tabela `leads` ficam intocados.

## Sintoma

14 de 15 mensagens do NaPista por WhatsApp não viraram lead entre 2026-09-09 e 2026-09-23, sem erro e sem alerta. Execuções marcadas como `success`. Descoberto em 2026-09-22 a partir de um vídeo do lojista mostrando a mensagem chegando no aparelho.

## Causa raiz

Três defeitos somados, todos na camada de entrada:

1. **`Prepara Dados NaPista` descarta o telefone que o próprio parser extraiu.** Usa `{{ $('Normaliza Dados').item.json.remetenteNumero }}`, que numa mensagem repassada pela plataforma é o número da NaPista (`551131361712`), não do cliente. Com `anuncio` também vazio, a chave de dedup `(numero_cliente, loja_id, anuncio)` fica constante e tudo depois do primeiro lead vira duplicata. O nó irmão `Prepara Dados icarros` já faz certo (`{{ $json.telefone }}`) — é uma divergência de um campo.
2. **`Duplicado de Plataforma?` e `Vendedor Encontrado?` voltam ao `Loop Over Items` sem avisar ninguém.** O lead some e a execução segue `success`.
3. **`Separar Leads NaPista` lê `templateMessage.hydratedTemplate.hydratedContentText`**, caminho `undefined` em `placeholderMessage` (9 de 14 mensagens, efeito de 62 quedas de sessão da Evolution em 14 dias). O nó tem `onError: continueRegularOutput`, então emite o **objeto de erro como dado** para o resto do fluxo.

Agravante independente: a NaPista removeu o telefone do cliente do template novo e cortou o canal de e-mail em 2026-08-14. Sem telefone não há para quem distribuir — isso é comercial, não tem correção em código.

## Estado da aplicação

| Passo | Estado | Quando | versionId |
|---|---|---|---|
| 0 · ligar alerta de conexão | **aplicado** | 2026-09-23 16:27 BRT | `e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` → `e43645a3-2cda-4db7-9f40-6b6b969c1cdb` |
| 1 · alerta de lead não distribuído | pendente | | |
| 2 · causa raiz | pendente (bloqueado por `comando_leads`) | | |

O Passo 0 foi aplicado **fora da janela 03h–05h**, por decisão do dono. Exposição medida: ~0,35 lead/hora às 16h, o que põe a chance de perda na janela de 1s do save em ~0,01%. Conferido depois: nenhuma execução entre a última anterior (id 8863, 15:17 BRT) e a aplicação — nada se perdeu.

Critérios de aceite e checklist de cada passo: [ACEITE.md](ACEITE.md).

## Arquivos

- `ROLLBACK_workflow_n8n.json` — export do workflow em `versionId e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` (62 nós, `updatedAt 2026-09-22T22:46:46Z`). **Segredos redigidos** (14 ocorrências): serve como registro do estado anterior, **não** para restaurar. Restaurar este arquivo apagaria as credenciais embutidas nos nós.

O rollback de verdade é a **version history do próprio n8n**: restaurar `e14f1ff7-aa49-4989-aaa7-b870a49f0ae8`, que preserva as credenciais.

## Aplicar

**Janela obrigatória: 03h–05h BRT.** Distribuição real por hora põe 04h com 1 lead em sete meses, contra 127 às 23h. Salvar um workflow ativo re-registra o webhook e abre uma janela de <1s em que uma mensagem receberia erro **sem criar execução** — é o único ponto sem rastro em todo o sistema.

Uma mudança por vez. Entre uma e a seguinte, esperar ~20 mensagens limpas.

### Passo 0 — ligar o alerta de conexão (2 minutos)

`Montar Alerta` tem saída vazia e `Enviar Alerta Conexão` não recebe de ninguém: o alerta de queda do WhatsApp **nunca disparou**, ao contrário do que `docs/specs/tecnica/03-workflow-n8n.md` afirmava.

Conectar `Montar Alerta [saída 0]` → `Enviar Alerta Conexão`.

Efeito esperado: ~4 mensagens por dia para o número do operador (62 quedas + 62 reconexões em 14 dias). O ruído é o dado — mede a instabilidade da Evolution.

Blast radius: nenhum. O ramo `É Mensagem? = não` é paralelo ao caminho de distribuição.

### Passo 1 — alertar quando um lead não é distribuído

Nó novo `Alerta Lead Nao Distribuido`, HTTP Request clonado de `Enviar Alerta Conexão` (mesmo endpoint `sendText` da Evolution, mesmo destino), **obrigatoriamente com `onError: continueRegularOutput`**.

> Sem esse `onError`, uma falha de alerta derruba a execução e passa a perder leads que hoje funcionam. Seria trocar um bug silencioso por uma queda geral.

Inserir **entre** o nó e seu destino atual, preservando a semântica do loop:

| Inserir em | Destino hoje | Passa a ser |
|---|---|---|
| `Duplicado de Plataforma?` saída 0 (true) | `Loop Over Items` | alerta → `Loop Over Items` |
| `Vendedor Encontrado?` saída 1 (false) | `Loop Over Items` | alerta → `Loop Over Items` |
| `Loja Encontrada?` saída 1 (false) | *nada* | alerta |

Corpo: origem, número do remetente, 200 primeiros caracteres de `mensagemTexto`, `duplicado`, `lead_id`, timestamp, URL da execução.

Esperar 1–2 semanas de ruído: a saída 0 de `Duplicado de Plataforma?` também dispara em repetição legítima de cliente. Esse volume é a medição da taxa real de duplicata, que hoje não existe.

### Passo 2 — causa raiz

Antes de aplicar, resolver a pendência: **`comando_leads` usa `mensagem_original`?** (`SELECT prosrc FROM pg_proc WHERE proname='comando_leads'`). Se usar, o terceiro item abaixo muda o que o vendedor lê pelo WhatsApp.

| Nó | Campo | Hoje | Vira |
|---|---|---|---|
| `Prepara Dados NaPista` | `telefone` | `{{ $('Normaliza Dados').item.json.remetenteNumero }}` | `{{ $json.telefone }}` |
| `Prepara Dados NaPista` | `anuncio` | `{{ $('Normaliza Dados').item.json.anuncio }}` | `{{ $json.anuncio \|\| $('Normaliza Dados').item.json.mensagemTexto }}` |
| `Distribuir Lead` | `p_mensagem_original` | `{{ $input.item.json.anuncio \|\| $input.item.json.mensagemTexto }}` | `{{ $input.item.json.mensagemTexto }}` |

Mais uma guarda antes de distribuir: telefone vazio **ou** com dígitos iguais a um número de plataforma conhecido (`551131361712` NaPista, `551130044558` iCarros) → não chamar `distribuir_lead`, alertar.

E reescrever `Separar Leads NaPista` para ler `$('Normaliza Dados').item.json.mensagemTexto` (que já tem cadeia de fallback) dentro de try/catch, devolvendo `{ parse_ok: true|false }` — nunca `[]`, nunca objeto de erro, e **sem** `onError: continueRegularOutput`.

> Efeito colateral a comunicar à loja: hoje todo lead NaPista entra com `anuncio = ""`, então o Passo 1 do `distribuir_lead` colapsa tudo num só. Depois da correção, anúncios diferentes do mesmo cliente viram leads separados — está correto, mas o volume aparente de NaPista vai subir.

## Verificar (logo após aplicar)

Conferência por execução, sem depender de ninguém olhar o celular:

```bash
curl -s -H "X-N8N-API-KEY: $N8N_KEY" \
  "https://n8n.yavoh.cloud/api/v1/executions?limit=50" 
```

Para cada execução desde a mudança, abrir com `?includeData=true` e confirmar que `Encaminhar ao Vendedor` aparece em `resultData.runData`. As que não aparecerem: extrair nome, telefone e mensagem do nó `Webhook` e entregar para trabalho manual.

Passo 0: provocar uma queda de conexão da Evolution e confirmar que a mensagem de alerta chega.

Passo 1: reenviar mensagem de um cliente existente para o mesmo anúncio (dispara `Duplicado de Plataforma?` saída 0) e confirmar o alerta.

Passo 2: na próxima mensagem NaPista com template, confirmar `parse_ok: true` com telefone, `lead_id` não-nulo e `Encaminhar ao Vendedor` executado. Numa `placeholderMessage`, confirmar `parse_ok: false` + alerta, sem objeto de erro descendo o fluxo.

## Monitorar (próximos dias)

- Execuções `mode: webhook` que passam por `Separar Leads NaPista` e **não** chegam em `Encaminhar ao Vendedor` — deve tender a zero para mensagens com telefone
- Volume de `connection.update`: 62 em 14 dias é o baseline. Se não cair, a instabilidade da Evolution continua e `placeholderMessage` continua chegando
- Leads com `numero_cliente = 551131361712` ou `551130044558`: deve ser **zero** após o Passo 2

## Rollback

Restaurar o `versionId e14f1ff7-aa49-4989-aaa7-b870a49f0ae8` pela version history do n8n (preserva credenciais). Por passo:

| Passo | Como voltar |
|---|---|
| 0 | apagar a conexão `Montar Alerta` → `Enviar Alerta Conexão` |
| 1 | apagar o nó `Alerta Lead Nao Distribuido` e restaurar as 3 conexões originais |
| 2 | reverter os 3 campos da tabela acima |

**Gatilhos para reverter:**

- Qualquer execução com `status: error` após a mudança (hoje são 0 em 373)
- Queda no volume diário de leads distribuídos comparado à média das duas semanas anteriores
- Alerta disparando em volume que impeça o operador de trabalhar

Leads criados entre a aplicação e o rollback ficam com o formato novo de `mensagem_original` — isso não é revertido nos dados, e não afeta nenhuma tela (verificado: `mensagem_original` não é lido em `pages/` nem `utils/`).
