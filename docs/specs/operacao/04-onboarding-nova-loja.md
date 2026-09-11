# Onboarding de Nova Loja

> Revisado a partir do `docs/OPERACAO_ONBOARDING_NOVA_LOJA.md` original do vault, corrigindo o que ficou desatualizado. **Atenção**: o procedimento abaixo nunca foi executado de fato em produção — hoje existe apenas 1 loja (Renato Motors), cadastrada manualmente antes deste processo existir como documento. Trate como um roteiro a validar na prática antes de confiar nele para um onboarding real.

## Limitação importante não documentada antes

O workflow n8n de produção **não é genérico por loja** hoje: o nome do webhook principal, os webhooks dedicados de Mobiauto/Webmotors, e o `lojaId` usado no parsing de e-mail da NaPista estão **hardcoded para "Renato Motors"** dentro dos nós do workflow (ver [tecnica/03-workflow-n8n.md](../tecnica/03-workflow-n8n.md)). Onboarding de uma segunda loja hoje **não é só inserir linhas no banco** — exigiria duplicar/adaptar nós do workflow n8n também. Isso não estava em nenhum documento anterior. Trate os passos abaixo como válidos apenas para a camada de dados (Supabase); a camada de automação (n8n) precisa de trabalho de engenharia adicional para suportar múltiplas lojas de verdade.

## Passo a passo (camada de dados)

1. **Criar sessão no Evolution API** para o número de WhatsApp dedicado da loja, escanear o QR Code, e configurar o webhook da sessão para o evento `MESSAGES_UPSERT`. A URL do webhook deve apontar para o path real do workflow em produção — **não** use `https://webhook.yavoh.cloud/webhook/distribuicao-leads` (esse era o path planejado num rascunho antigo nunca usado); confirme o path atual direto no nó "Webhook" do workflow ativo antes de configurar.
2. **Cadastrar a loja** em `lojas` (`nome`, `numero_whatsapp`, `instancia_evolution` — deve bater exatamente com o nome da sessão criada no passo 1 — `ativa = true`).
3. **Cadastrar vendedores** em `vendedores` (`loja_id`, `nome`, `numero_whatsapp`, `status = 'ativo'`). **Correção**: a coluna `ordem_fila` **não** controla a ordem real do round-robin — a ordem real é `criado_em` (ordem de inserção). Preenchê-la com cuidado não é necessário para o funcionamento do sistema hoje (ver [regras-de-negocio/01](../regras-de-negocio/01-round-robin.md)); ela só afeta a visualização de drag-and-drop no Dashboard.
4. `lojas.proximo_vendedor_id` **não precisa** ser inicializado manualmente — a função `distribuir_lead()` já trata ponteiro `NULL` pegando o primeiro vendedor ativo por `criado_em`.
5. **Cadastrar gerente** em `gerentes` (`loja_id`, `numero_whatsapp`, `nome`, `ativo = true`).
6. **Validar**: `instancia_evolution` é `UNIQUE` no banco — uma segunda loja com a mesma instância falha com erro de constraint, por design.

## Teste end-to-end

1. Envie uma mensagem de um número de teste para o WhatsApp da loja → confirme que um lead foi criado em `leads` com `vendedor_id` preenchido e `distribuido_em` não nulo.
2. Envie de um segundo número → confirme que foi para o **próximo** vendedor por ordem de cadastro (não necessariamente "ordem_fila").
3. Envie `status` do número do gerente → confirme resposta (lembre: retorna dados dos **últimos 3 dias**, não só hoje — ver [02-comandos-whatsapp.md](02-comandos-whatsapp.md)).

## Instruções para o cliente (corrigido)

- Gerente e vendedores: podem enviar `status` ou `leads`. **O comando `relatorio` não existe mais** — foi renomeado para `leads` (documentação antiga do onboarding ainda citava o nome antigo).
- Vendedores não precisam fazer nada — leads chegam automaticamente no WhatsApp deles.
