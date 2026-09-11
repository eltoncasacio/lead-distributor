# Integração com Evolution API

> Papel da Evolution API no sistema: transporte puro de WhatsApp (QR code, envio/recebimento de mensagens). Nenhuma regra de negócio vive aqui — tudo é decidido no Supabase, orquestrado pelo n8n.

## Vínculo instância ↔ loja

Cada loja tem uma instância Evolution própria (`lojas.instancia_evolution`, `UNIQUE`). É esse campo — não o número de telefone — que o sistema usa para saber de qual loja veio uma mensagem (`identificar_remetente(p_instancia, ...)`). Ver [regras-de-negocio/04](../regras-de-negocio/04-isolamento-multi-loja.md).

## Autenticação da API

A tabela `lojas` tem uma coluna `evolution_api_key` (adicionada depois da versão inicial do schema) — indica a intenção de armazenar a chave por loja no banco. Na prática, ao menos os nós inspecionados do workflow n8n (envio de alerta de conexão, extração de e-mail NaPista) têm a chave **hardcoded diretamente no nó**, não lida dessa coluna. Isso é uma limitação conhecida da conta gratuita do n8n (sem suporte a variáveis de ambiente) — por instrução do usuário, não é tratado como pendência de segurança nesta rodada, apenas registrado aqui.

## Eventos consumidos

O Webhook principal recebe todos os eventos da instância, incluindo:
- **Mensagens** (`MESSAGES_UPSERT` — tipo real do evento não confirmado neste código, mas é o padrão da Evolution API para mensagens recebidas): seguem para o pipeline de identificação/distribuição.
- **Eventos de estado de conexão** (`state: close`/`open`): disparam o alerta de desconexão descrito em [03-workflow-n8n.md](03-workflow-n8n.md) — funcionalidade real, não documentada antes desta reescrita.

## Envio de mensagens

Feito via `POST /message/sendText/{instancia}` da Evolution API, chamado tanto para encaminhar leads a vendedores quanto para responder comandos (`status`/`leads`) e para o alerta de conexão.

## Limitações conhecidas

- Sem retry configurado nas chamadas de envio inspecionadas — uma falha de rede na hora de encaminhar um lead ao vendedor não é percebida nem re-tentada (ver [operacao/03-tratamento-de-erros.md](../operacao/03-tratamento-de-erros.md)).
- Identificação de origem de plataforma (iCarros/NaPista) depende de números de telefone fixos e conhecidos, hardcoded no workflow — se a plataforma trocar o número que usa para mandar mensagens, a detecção quebra silenciosamente.
