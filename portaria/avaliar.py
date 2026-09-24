"""Portaria — passo 2: rodar o prompt contra a amostra rotulada e medir.

Usa HTTP cru de proposito, com o mesmo formato de chamada que o no do n8n vai
usar — assim o que e medido aqui e o que roda la.

    source venv/bin/activate
    python3 portaria/avaliar.py

Precisa de:
  - portaria/amostra_para_rotular.csv com a coluna ROTULO_HUMANO preenchida
  - ANTHROPIC_API_KEY no .env

O PORTAO: zero mensagens rotuladas como cliente (lead_novo ou pos_venda) que o
modelo tenha classificado como nao_lead. Falso lead_novo e tolerado — ja e o
comportamento de hoje. Se o portao falhar, NAO SOBE.
"""
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter

from dotenv import load_dotenv

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
load_dotenv(os.path.join(os.path.dirname(AQUI), ".env"))

from portaria.prompt import (  # noqa: E402
    FEW_SHOT, MODELO, SCHEMA, SYSTEM_PROMPT, aplicar_travas, decidir,
)

CLIENTE = {"lead_novo", "pos_venda"}


def classificar(texto, chave, modelo=MODELO):
    mensagens = []
    for exemplo, saida in FEW_SHOT:
        mensagens.append({"role": "user", "content": exemplo})
        mensagens.append({"role": "assistant",
                          "content": json.dumps(saida, ensure_ascii=False)})
    mensagens.append({"role": "user", "content": texto})

    corpo = {
        "model": modelo,
        "max_tokens": 512,
        "system": SYSTEM_PROMPT,
        "messages": mensagens,
        "output_config": {"effort": "low",
                          "format": {"type": "json_schema", "schema": SCHEMA}},
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(corpo).encode("utf-8"),
        headers={"x-api-key": chave, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.load(r)
    return json.loads(resp["content"][0]["text"])


def main():
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if not chave:
        raise SystemExit(
            "ANTHROPIC_API_KEY nao esta no .env.\n"
            "Acrescente:  echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env")

    caminho = os.path.join(AQUI, "amostra_para_rotular.csv")
    if not os.path.exists(caminho):
        raise SystemExit("rode antes: python3 portaria/amostrar.py")

    with open(caminho, encoding="utf-8") as f:
        linhas = [l for l in csv.DictReader(f)
                  if (l.get("ROTULO_HUMANO") or "").strip()]
    if not linhas:
        raise SystemExit(
            "nenhuma linha rotulada em %s.\n"
            "Preencha a coluna ROTULO_HUMANO com lead_novo / pos_venda / "
            "nao_lead / incerto." % caminho)

    print("avaliando %d mensagens rotuladas com %s...\n" % (len(linhas), MODELO))

    matriz, violacoes, travas, erros, saidas = Counter(), [], Counter(), 0, []
    for i, l in enumerate(linhas, 1):
        texto, humano = l["mensagem"], l["ROTULO_HUMANO"].strip()
        try:
            bruto = classificar(texto, chave)
        except (urllib.error.URLError, KeyError, ValueError) as e:
            erros += 1
            print("  [%3d/%d] ERRO: %s" % (i, len(linhas), str(e)[:70]))
            continue

        final, disparos = aplicar_travas(bruto, texto, payload_bruto=texto)
        for d in disparos:
            travas[d] += 1
        maquina = final["classificacao"]
        matriz[(humano, maquina)] += 1
        saidas.append({"id": l["id"], "humano": humano, "maquina": maquina,
                       "confianca": final.get("confianca"),
                       "acao": decidir(final), "mensagem": texto[:90]})

        if humano in CLIENTE and maquina == "nao_lead":
            violacoes.append((texto, humano, final))
        print("  [%3d/%d] humano=%-10s modelo=%-10s %s"
              % (i, len(linhas), humano, maquina,
                 "<<< VIOLACAO" if (humano in CLIENTE and maquina == "nao_lead") else ""))

    print("\n" + "=" * 68)
    print("MATRIZ  (linha = rotulo humano, coluna = modelo)")
    print("=" * 68)
    cats = ["lead_novo", "pos_venda", "nao_lead", "incerto"]
    print("%-12s" % "" + "".join("%11s" % c for c in cats))
    for h in cats:
        if not any(matriz[(h, m)] for m in cats):
            continue
        print("%-12s" % h + "".join("%11d" % matriz[(h, m)] for m in cats))

    acertos = sum(matriz[(c, c)] for c in cats)
    total = sum(matriz.values())
    if total:
        print("\nconcordancia exata: %d/%d (%.1f%%)" % (acertos, total, 100 * acertos / total))
    if erros:
        print("chamadas com erro: %d" % erros)
    if travas:
        print("\ntravas que dispararam:")
        for t, n in travas.most_common():
            print("  %-45s %d" % (t, n))

    with open(os.path.join(AQUI, "resultado_avaliacao.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(saidas[0].keys()) if saidas else ["id"])
        w.writeheader()
        w.writerows(saidas)

    print("\n" + "=" * 68)
    if violacoes:
        print("PORTAO: REPROVADO — %d cliente(s) classificado(s) como nao_lead" % len(violacoes))
        print("=" * 68)
        for texto, humano, r in violacoes:
            print("\n  rotulo humano: %s" % humano)
            print("  mensagem.....: %s" % texto[:150])
            print("  motivo do modelo: %s" % r.get("motivo"))
            print("  confianca....: %s" % r.get("confianca"))
        print("\nNAO SUBIR. Ajuste o prompt e rode de novo.")
        sys.exit(1)

    print("PORTAO: PASSOU — nenhum cliente foi classificado como nao_lead")
    print("=" * 68)
    print("Proximo passo: ramo sombra no n8n (Fase 6), >=2 semanas e >=200")
    print("mensagens antes de qualquer corte.")


if __name__ == "__main__":
    main()
