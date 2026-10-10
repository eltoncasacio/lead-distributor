-- Reconstrucao MINIMA das tabelas de producao, so para testar em Postgres
-- descartavel. Colunas conferidas contra o Supabase real em 2026-10-09; os
-- CHECK de status/tipo sao os valores observados, nao o DDL real (nao foi
-- possivel ler o DDL de producao daqui).
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN;

CREATE TABLE public.lojas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nome text NOT NULL,
  ativa boolean NOT NULL DEFAULT true,
  proximo_vendedor_id uuid
);
CREATE TABLE public.vendedores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL REFERENCES public.lojas(id),
  nome text NOT NULL,
  numero_whatsapp text,
  status text NOT NULL DEFAULT 'ativo' CHECK (status IN ('ativo','inativo','removido')),
  ordem_fila int,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.gerentes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL REFERENCES public.lojas(id),
  nome text NOT NULL,
  numero_whatsapp text,
  ativo boolean NOT NULL DEFAULT true,
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL REFERENCES public.lojas(id),
  vendedor_id uuid REFERENCES public.vendedores(id),
  nome_cliente text,
  numero_cliente text,
  anuncio text,
  origem text,
  status_lead text DEFAULT 'negociando',
  criado_em timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.atividades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  loja_id uuid NOT NULL REFERENCES public.lojas(id),
  tipo text NOT NULL CHECK (tipo IN ('novo_lead','fila_reordenada','status_lead_alterado',
    'vendedor_adicionado','vendedor_removido','vendedor_inativado','vendedor_reativado')),
  descricao text,
  criado_em timestamptz NOT NULL DEFAULT now()
);

-- O Supabase concede acesso as tabelas do schema public aos tres papeis; o que
-- barra anon/authenticated em producao e o RLS. Aqui o que importa testar e que
-- o EXECUTE de executar_comando nao chega a eles.
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated, service_role;
