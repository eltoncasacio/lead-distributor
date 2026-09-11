# ADR 0007 — n8n como roteador de canal e origem, convergindo num contrato único

## Status
Aceito (implementado, cresceu organicamente)

## Contexto
Leads chegam por canais muito diferentes: WhatsApp direto, plataformas que mandam mensagem de template por WhatsApp usando um número fixo (iCarros, e parte da NaPista), plataformas com webhook HTTP dedicado (Mobiauto, Webmotors), e uma plataforma que manda por e-mail (NaPista via Gmail). Cada uma tem um formato de dado diferente.

## Decisão
O n8n normaliza cada origem no seu próprio branch (`Prepara Dados {Origem}`) e converge tudo num formato único antes de chamar `distribuir_lead()` — o Postgres nunca precisa saber de onde veio o lead em termos de formato de payload, só recebe `origem` como uma string já normalizada.

## Consequências
- Fácil adicionar uma nova origem (só adicionar um branch + um "Prepara Dados") sem tocar na lógica de negócio no banco.
- Como contrapartida, a lista de origens suportadas só existe "de fato" dentro do workflow n8n — nenhum documento de produto batia com a realidade antes desta reescrita (chegou a haver a afirmação, incorreta, de que não existia integração direta com portais). Isso é o tipo de drift que motivou a auditoria completa registrada em [historico/AUDITORIA_2026-09-11.md](../historico/AUDITORIA_2026-09-11.md).
- O crescimento orgânico gerou duplicação: dois parsers paralelos para a NaPista (WhatsApp legado + e-mail atual, ver [tecnica/03-workflow-n8n.md](../specs/tecnica/03-workflow-n8n.md)) que nunca foram consolidados.
- Cada origem nova tende a fixar valores específicos da loja (nomes de webhook, `lojaId` hardcoded) diretamente nos nós, o que limita a reutilização do workflow para uma segunda loja sem trabalho de engenharia adicional (ver [operacao/04-onboarding-nova-loja.md](../specs/operacao/04-onboarding-nova-loja.md)).
