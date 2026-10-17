# Monitor de lojas (desde 2026-10-17)

`monitor_lojas.py` — somente leitura, cobre **todas as lojas ativas** (a `auditoria_producao.py` só olha a Renato Motors). Criado no dia em que Fitcar e TbMotors entraram.

## O que alerta

| Check | Alerta quando |
|---|---|
| WhatsApp da loja | `connectionState` da instância ≠ `open` |
| Silêncio | nenhuma mensagem em `mensagens_recebidas` há mais de 4 h, **só entre 8h e 20h (BRT)** e só com o WhatsApp conectado |
| Lead sem vendedor | algum lead das últimas 24 h com `vendedor_id` nulo |
| Erro registrado | `mensagens_recebidas.erro` preenchido nas últimas 24 h |
| Filtro de grupo | lead das últimas 24 h com `numero_cliente` com `-` ou com mais de 13 dígitos (regressão do filtro `@g.us`) |
| Fila | loja sem vendedor ativo, ou `proximo_vendedor_id` apontando para vendedor inativo/de outra loja |

**Silêncio de 4 h é um palpite**: a Renato Motors recebe ~25 mensagens/dia e a Fitcar ~140. Para a TbMotors ainda não há base, então pode dar falso alarme. Ajuste `SILENCIO_HORAS` quando houver histórico.

## Como roda

- Manual: `python3 monitor_lojas.py` (relatório) ou `--curto` (só alertas). Sai com código 1 se houver alerta.
- Agendado: launchd, `~/Library/LaunchAgents/com.yavoh.monitor-lojas.plist`, **de hora em hora, das 8h às 20h, de segunda a sábado**, com `--curto --avisar`. Log em `/tmp/monitor-lojas.log`.
- Aviso: **só para o dono, nunca para a loja.** Notificação no Mac sempre. WhatsApp para `DONO_WHATSAPP` (padrão `5519996977453`) **só** se o `.env` tiver `ALERTA_INSTANCIA` e `ALERTA_INSTANCIA_KEY`, de um número exclusivo do sistema. O script recusa instância de loja. **Só avisa quando o conjunto de alertas muda**, e avisa "tudo normalizado" quando zera. O último conjunto enviado fica em `.monitor_estado` (fora do git); apague esse arquivo para forçar um reenvio.

## Por que não sai pelo número de uma loja (2026-10-17)

A primeira versão mandava o alerta pela instância da Renato Motors. Tudo que sai por uma instância fica na conversa do celular da loja: o Renato viu o alerta, com o nome da TbMotors dentro. Regra do dono: **alertas não vão para as lojas, vão para o dono.**

**Mesmo problema, ainda aberto no n8n:** "Alerta Lead Não Distribuído" e "Alerta NaPista Sem Telefone" mandam WhatsApp para o dono **pela instância da própria loja** (decisão de 10/10, ver [onboarding-segunda-loja.md](onboarding-segunda-loja.md), Passo 7). A loja vê o alerta dela, mas não vê dados de outra loja. Para corrigir, os alertas precisam sair do número do sistema, assim que ele existir.

## Limites (não é a Fase E)

- **Roda no Mac do dono.** Mac desligado = sem monitor. Se o Mac estava dormindo, o launchd roda uma vez ao acordar. O lugar certo a longo prazo é um workflow agendado no n8n, que ficou de fora porque a `N8N_API_KEY` não está no `.env`.
- Enquanto não houver número do sistema, o aviso é **só a notificação do Mac**: com você longe do computador, ninguém vê.
- Não olha origem por origem (NaPista, iCarros…): isso continua na `auditoria_producao.py`, só para a Renato Motors.
- Não lê execuções com erro do n8n.

Desligar: `launchctl bootout gui/$(id -u)/com.yavoh.monitor-lojas`.
