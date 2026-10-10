-- Schema das 5 tabelas que o FIX usa, GERADO a partir do catalogo de producao
-- (pg_catalog via API de gestao do Supabase, somente leitura) em 2026-10-10.
-- Substitui teste_schema_minimo.sql, que era reconstruido a mao.
-- Colunas, tipos, NOT NULL, defaults, PK/UNIQUE/CHECK/FK, indices e RLS sao os reais.
-- Producao nao tem triggers nessas tabelas. Extensoes do Supabase nao entram.
CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN;

CREATE TABLE public.lojas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  nome varchar(255) NOT NULL,
  numero_whatsapp varchar(20),
  instancia_evolution varchar(100),
  ativa boolean NOT NULL DEFAULT true,
  proximo_vendedor_id uuid,
  ultima_distribuicao_em timestamp with time zone,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  atualizado_em timestamp with time zone NOT NULL DEFAULT now(),
  limite_leads integer,
  evolution_api_key text
);
CREATE TABLE public.vendedores (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL,
  nome varchar(255) NOT NULL,
  numero_whatsapp varchar(20) NOT NULL,
  status varchar(20) NOT NULL,
  ordem_fila integer NOT NULL,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  atualizado_em timestamp with time zone NOT NULL DEFAULT now()
);
CREATE TABLE public.gerentes (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL,
  numero_whatsapp varchar(20) NOT NULL,
  nome varchar(255) NOT NULL,
  ativo boolean NOT NULL DEFAULT true,
  criado_em timestamp with time zone NOT NULL DEFAULT now()
);
CREATE TABLE public.leads (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL,
  vendedor_id uuid,
  numero_cliente varchar(20) NOT NULL,
  nome_cliente varchar(255),
  anuncio varchar(500),
  mensagem_original text,
  recebido_em timestamp with time zone NOT NULL,
  distribuido_em timestamp with time zone,
  criado_em timestamp with time zone NOT NULL DEFAULT now(),
  status_lead varchar DEFAULT 'negociando'::character varying,
  atualizado_em timestamp with time zone DEFAULT now(),
  origem varchar DEFAULT 'WhatsApp Direto'::character varying
);
CREATE TABLE public.atividades (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL,
  tipo varchar NOT NULL,
  descricao text NOT NULL,
  criado_em timestamp with time zone NOT NULL DEFAULT now()
);
ALTER TABLE public.atividades ADD CONSTRAINT atividades_pkey PRIMARY KEY (id);
ALTER TABLE public.atividades ADD CONSTRAINT atividades_tipo_check CHECK ((((tipo)::text = ANY (ARRAY[('novo_lead'::character varying)::text, ('status_lead_alterado'::character varying)::text, ('vendedor_adicionado'::character varying)::text, ('vendedor_removido'::character varying)::text, ('vendedor_inativado'::character varying)::text, ('vendedor_reativado'::character varying)::text, ('fila_reordenada'::character varying)::text, ('gerente_adicionado'::character varying)::text, ('gerente_desativado'::character varying)::text, ('gerente_removido'::character varying)::text])) OR ((tipo)::text = ANY (ARRAY['mensagem_triada'::text, 'lead_promovido_de_triagem'::text]))));
ALTER TABLE public.gerentes ADD CONSTRAINT gerentes_pkey PRIMARY KEY (id);
ALTER TABLE public.gerentes ADD CONSTRAINT uk_gerentes_loja_whatsapp UNIQUE (loja_id, numero_whatsapp);
ALTER TABLE public.leads ADD CONSTRAINT leads_pkey PRIMARY KEY (id);
ALTER TABLE public.leads ADD CONSTRAINT leads_status_lead_check CHECK (((status_lead)::text = ANY ((ARRAY['negociando'::character varying, 'sem_resposta'::character varying, 'sem_interesse'::character varying, 'vendido'::character varying])::text[])));
ALTER TABLE public.lojas ADD CONSTRAINT chk_loja_ativa_tem_sessao CHECK (((ativa = false) OR (instancia_evolution IS NOT NULL)));
ALTER TABLE public.lojas ADD CONSTRAINT lojas_pkey PRIMARY KEY (id);
ALTER TABLE public.lojas ADD CONSTRAINT uq_lojas_instancia_evolution UNIQUE (instancia_evolution);
ALTER TABLE public.vendedores ADD CONSTRAINT uk_vendedores_loja_whatsapp UNIQUE (loja_id, numero_whatsapp);
ALTER TABLE public.vendedores ADD CONSTRAINT vendedores_pkey PRIMARY KEY (id);
ALTER TABLE public.vendedores ADD CONSTRAINT vendedores_status_check CHECK (((status)::text = ANY ((ARRAY['ativo'::character varying, 'inativo'::character varying, 'removido'::character varying])::text[])));
ALTER TABLE public.atividades ADD CONSTRAINT atividades_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES lojas(id);
ALTER TABLE public.gerentes ADD CONSTRAINT gerentes_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE;
ALTER TABLE public.leads ADD CONSTRAINT leads_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE;
ALTER TABLE public.leads ADD CONSTRAINT leads_vendedor_id_fkey FOREIGN KEY (vendedor_id) REFERENCES vendedores(id) ON DELETE SET NULL;
ALTER TABLE public.lojas ADD CONSTRAINT fk_proximo_vendedor FOREIGN KEY (proximo_vendedor_id) REFERENCES vendedores(id) ON DELETE SET NULL;
ALTER TABLE public.vendedores ADD CONSTRAINT vendedores_loja_id_fkey FOREIGN KEY (loja_id) REFERENCES lojas(id) ON DELETE CASCADE;
CREATE INDEX idx_atividades_loja_id ON public.atividades USING btree (loja_id);
CREATE INDEX idx_gerentes_numero ON public.gerentes USING btree (numero_whatsapp);
CREATE INDEX idx_leads_cliente_loja_recebido ON public.leads USING btree (numero_cliente, loja_id, recebido_em DESC) WHERE (vendedor_id IS NOT NULL);
CREATE INDEX idx_leads_dedup_anuncio ON public.leads USING btree (numero_cliente, loja_id, anuncio, recebido_em DESC);
CREATE INDEX idx_leads_loja_recebido ON public.leads USING btree (loja_id, recebido_em DESC);
CREATE INDEX idx_leads_loja_vendedor_recebido ON public.leads USING btree (loja_id, vendedor_id, recebido_em DESC);
CREATE INDEX idx_leads_vendedor_id ON public.leads USING btree (vendedor_id);
CREATE UNIQUE INDEX idx_lojas_instancia_unique ON public.lojas USING btree (instancia_evolution) WHERE (instancia_evolution IS NOT NULL);
CREATE INDEX idx_lojas_proximo_vendedor ON public.lojas USING btree (proximo_vendedor_id);
CREATE INDEX idx_vendedores_loja_status_ordem ON public.vendedores USING btree (loja_id, status, ordem_fila);
ALTER TABLE public.atividades ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gerentes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lojas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.vendedores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Deny all for anon" ON public.atividades FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for anon" ON public.gerentes FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for anon" ON public.leads FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for anon" ON public.lojas FOR ALL TO anon USING (false);
CREATE POLICY "Deny all for anon" ON public.vendedores FOR ALL TO anon USING (false);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
