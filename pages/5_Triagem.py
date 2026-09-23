"""
Triagem de mensagens que chegaram mas nao viraram lead.

Cards, nao data_editor: cada acao distribui um lead de verdade e dispara
WhatsApp para um vendedor. O auto-save por hash de pages/4_Leads.py
promoveria leads numa edicao acidental.
"""
import streamlit as st
import pandas as pd
from utils.ui import (
    render_page_header,
    loading_spinner,
    success_message,
    error_message,
    info_message,
    inject_global_css,
)
from utils.auth import obter_loja_logada
from utils.queries import (
    listar_mensagens_para_revisao,
    listar_mensagens_recebidas,
    promover_mensagem_para_lead,
    arquivar_mensagem,
)
from utils.validators import validar_whatsapp, formatar_whatsapp

render_page_header("Triagem")
inject_global_css()

loja = obter_loja_logada()

_ABAS = ["A revisar", "Já revisadas", "Todas as mensagens"]
if "triagem_aba" not in st.session_state:
    st.session_state["triagem_aba"] = _ABAS[0]

with loading_spinner("Carregando mensagens..."):
    pendentes = listar_mensagens_para_revisao(loja["loja_id"])

st.radio(
    "Aba",
    _ABAS,
    key="triagem_aba",
    horizontal=True,
    label_visibility="collapsed",
    format_func=lambda a: f"{a} ({len(pendentes)})" if a == _ABAS[0] else a,
)
aba = st.session_state["triagem_aba"]


def _horario(iso: str) -> str:
    """Converte o timestamp do banco para horario de Sao Paulo."""
    if not iso:
        return "-"
    try:
        return (
            pd.to_datetime(iso)
            .tz_convert("America/Sao_Paulo")
            .strftime("%d/%m %H:%M")
        )
    except Exception:
        return str(iso)[:16]


def _tabela(mensagens):
    """Renderiza uma lista de mensagens como tabela somente leitura."""
    if not mensagens:
        info_message("Nenhuma mensagem aqui.")
        return
    df = pd.DataFrame(
        [
            {
                "Recebido": _horario(m.get("recebido_em")),
                "Origem": m.get("origem_detectada") or "-",
                "Cliente": m.get("remetente_nome") or "-",
                "Telefone": m.get("telefone_extraido") or "-",
                "Veículo": m.get("anuncio_extraido") or "-",
                "Mensagem": (m.get("texto") or "")[:90],
                "Situação": m.get("revisao_acao") or m.get("decisao") or "pendente",
            }
            for m in mensagens
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


if aba == "A revisar":
    if not pendentes:
        success_message(
            "Nenhuma mensagem esperando. Tudo que chegou tinha telefone do cliente."
        )
    else:
        info_message(
            f"{len(pendentes)} mensagem(ns) chegaram sem telefone aproveitável. "
            "A plataforma repassou o lead sem o contato do cliente — abra a "
            "oportunidade no portal dela, pegue o telefone e distribua aqui."
        )

    for m in pendentes:
        mid = m["id"]
        with st.container(border=True):
            topo, acao = st.columns([3, 1])
            with topo:
                st.markdown(
                    f"**{m.get('remetente_nome') or 'Cliente não identificado'}**  \n"
                    f"{m.get('origem_detectada') or 'origem desconhecida'} · "
                    f"{_horario(m.get('recebido_em'))}"
                )
                if m.get("anuncio_extraido"):
                    st.markdown(f"Veículo: **{m['anuncio_extraido']}**")
                if m.get("texto"):
                    st.caption(m["texto"][:400])

            with acao:
                if st.button(
                    "Arquivar",
                    key=f"arq_{mid}",
                    use_container_width=True,
                    help="Não era um lead. Fica registrado, não some.",
                ):
                    try:
                        arquivar_mensagem(loja["loja_id"], mid, "Arquivado na triagem")
                        success_message("Mensagem arquivada.")
                        st.rerun()
                    except Exception as e:
                        error_message(f"Não foi possível arquivar: {e}")

            st.markdown("---")
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                tel = st.text_input(
                    "Telefone do cliente",
                    key=f"tel_{mid}",
                    placeholder="(19) 99999-9999",
                    help="Pegue no portal da plataforma e cole aqui.",
                )
            with c2:
                nome = st.text_input(
                    "Nome",
                    key=f"nome_{mid}",
                    value=m.get("remetente_nome") or "",
                )
            with c3:
                st.markdown('<div style="height: 1.8rem;"></div>', unsafe_allow_html=True)
                promover = st.button(
                    "Distribuir",
                    key=f"prom_{mid}",
                    use_container_width=True,
                    type="primary",
                )

            if promover:
                valido, erro = validar_whatsapp(tel)
                if not valido:
                    error_message(erro or "Telefone inválido.")
                else:
                    try:
                        r = promover_mensagem_para_lead(
                            loja["loja_id"],
                            mid,
                            formatar_whatsapp(tel),
                            nome or None,
                            m.get("anuncio_extraido"),
                        )
                        vendedor = r.get("vendedor_nome") or "?"
                        if r.get("duplicado"):
                            info_message(
                                f"Cliente já estava com {vendedor} — "
                                "nenhum lead novo criado."
                            )
                        else:
                            success_message(f"Lead distribuído para {vendedor}.")
                        st.rerun()
                    except Exception as e:
                        error_message(f"Não foi possível distribuir: {e}")

elif aba == "Já revisadas":
    with loading_spinner("Carregando..."):
        _tabela(listar_mensagens_recebidas(loja["loja_id"], revisadas=True))

else:
    with loading_spinner("Carregando..."):
        _tabela(listar_mensagens_recebidas(loja["loja_id"]))

with st.expander("Como funciona"):
    st.markdown(
        """
        Toda mensagem que chega no WhatsApp da loja é registrada aqui, mesmo
        quando não vira lead. Nada some em silêncio.

        **A revisar** mostra o que chegou sem telefone aproveitável — quase
        sempre uma plataforma repassando o lead sem o contato do cliente.
        Nesses casos o sistema não tem para quem distribuir: alguém precisa
        abrir a oportunidade no portal da plataforma, pegar o telefone e
        colar aqui.

        **Distribuir** manda o lead para a fila normal — mesmo vendedor se o
        cliente já estiver sendo atendido, próximo da fila se for novo. A
        regra é a mesma de sempre; esta tela não decide para quem vai.

        **Arquivar** marca a mensagem como não sendo um lead. Ela continua
        registrada, com o texto original.
        """
    )
