"""Portaria — passo 1: medir o funil deterministico e gerar a amostra para rotular.

O spec (docs/specs/tecnica/07-portaria-classificacao.md) diz que a IA so ve o
que sobra depois dos filtros deterministicos, e que nada sobe sem antes ser
medido contra mensagens reais rotuladas a mao.

Este script:
  1. le as mensagens reais de origem "WhatsApp Direto" no Supabase (somente leitura)
  2. aplica os filtros deterministicos do spec e mostra quanto cada um corta
  3. sorteia N do que sobra e grava um CSV para o DONO rotular a mao

    source venv/bin/activate
    python3 portaria/amostrar.py [N]

O CSV de saida contem MENSAGENS REAIS DE CLIENTES (nomes, as vezes telefone).
Ele e gravado em portaria/ e esta no .gitignore de proposito — nao commitar.
"""
import csv
import os
import random
import re
import sys
from collections import Counter

from dotenv import load_dotenv
from supabase import create_client

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
load_dotenv(os.path.join(RAIZ, ".env"))

LOJA = "<LOJA_ID>"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
SEMENTE = 20260923  # fixa, para a amostra ser reproduzivel entre sessoes

# --- filtros deterministicos, exatamente como o spec descreve ---
SAUDACAO = re.compile(
    r"^(oi+|ol[aá]|bo[am] (dia|tarde|noite)|tudo bem)[\s!?.]*$", re.I
)


def classificar_deterministico(texto):
    """Devolve o motivo de corte, ou None se a mensagem deve ir para a IA."""
    t = (texto or "").strip()
    if not t:
        return "midia sem texto / vazia"
    if len(t) <= 12 or SAUDACAO.match(t):
        return "so saudacao"
    return None


def main():
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise SystemExit("credenciais nao encontradas no .env")
    sb = create_client(url, key)

    linhas, ini = [], 0
    while True:
        r = (sb.table("leads")
             .select("id,criado_em,mensagem_original,nome_cliente,anuncio")
             .eq("loja_id", LOJA).eq("origem", "WhatsApp Direto")
             .order("criado_em", desc=True).range(ini, ini + 999).execute())
        linhas += r.data or []
        if len(r.data or []) < 1000:
            break
        ini += 1000

    print("mensagens de WhatsApp Direto no banco: %d\n" % len(linhas))

    cortes, sobraram = Counter(), []
    for l in linhas:
        motivo = classificar_deterministico(l.get("mensagem_original"))
        if motivo:
            cortes[motivo] += 1
        else:
            sobraram.append(l)

    print("FUNIL DETERMINISTICO")
    print("-" * 56)
    for motivo, n in cortes.most_common():
        print("  cortado: %-26s %4d  (%4.1f%%)" % (motivo, n, 100 * n / len(linhas)))
    print("  %-35s %4d  (%4.1f%%)" % ("VAI PARA A IA:", len(sobraram),
                                      100 * len(sobraram) / len(linhas)))
    print()
    print("O spec estimava ~60%% indo para a IA. Medido: %.1f%%." %
          (100 * len(sobraram) / len(linhas)))

    random.seed(SEMENTE)
    amostra = random.sample(sobraram, min(N, len(sobraram)))

    saida = os.path.join(AQUI, "amostra_para_rotular.csv")
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "criado_em", "mensagem", "nome_no_lead",
                    "anuncio_no_lead", "ROTULO_HUMANO", "OBSERVACAO"])
        for l in amostra:
            w.writerow([l["id"], (l.get("criado_em") or "")[:16],
                        (l.get("mensagem_original") or "").replace("\n", " "),
                        l.get("nome_cliente") or "", l.get("anuncio") or "", "", ""])

    print("\n%d mensagens gravadas em:\n  %s" % (len(amostra), saida))
    print("""
COMO ROTULAR (coluna ROTULO_HUMANO), um destes:
    lead_novo   quer comprar, trocar, financiar ou vender um veiculo
    pos_venda   JA COMPROU e fala de revisao, garantia, documentacao
    nao_lead    cobranca, boleto, marketing, oferta B2B, engano de numero
    incerto     voce mesmo ficou na duvida

Os casos de fronteira sao decisao SUA — e regra de negocio, nao tecnica.
Depois de rotulado, `portaria/avaliar.py` roda o prompt contra esta amostra
e mede. O portao: ZERO mensagens que voce rotulou como cliente podem sair
como nao_lead.""")


if __name__ == "__main__":
    main()
