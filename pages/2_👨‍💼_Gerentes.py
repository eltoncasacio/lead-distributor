"""
Gestao de Gerentes.
"""
import streamlit as st
import pandas as pd
from utils.ui import render_page_header, loading_spinner, success_message, error_message, info_message, inject_global_css
from utils.auth import obter_loja_logada
from utils.queries import (
    listar_gerentes,
    adicionar_gerente,
    editar_gerente,
    deletar_gerente,
    whatsapp_ja_existe,
)
from utils.validators import validar_whatsapp, validar_nome, formatar_whatsapp

# Header compacto
render_page_header("Gerentes")

# CSS global
inject_global_css()

loja = obter_loja_logada()

# Buscar gerentes
with loading_spinner("Carregando gerentes..."):
    gerentes = listar_gerentes(loja["loja_id"])

# Botao adicionar
_, col_add = st.columns([3, 1])
with col_add:
    if st.button("Adicionar Gerente", use_container_width=True, type="primary"):
        st.session_state["add_gerente"] = True
        st.rerun()

# Formulario de adicionar (aparece acima da tabela)
if st.session_state.get("add_gerente"):
    with st.container(border=True):
        st.markdown("**Novo Gerente**")
        c1, c2 = st.columns(2)
        nome_key = "new_gerente_nome"
        whats_key = "new_gerente_whats"
        with c1:
            st.text_input("Nome", placeholder="Ex: Carlos Mendes", key=nome_key)
        with c2:
            st.text_input("WhatsApp", placeholder="Ex: 11999998888", help="DDD + numero (55 adicionado automaticamente)", key=whats_key)
        b1, b2, _ = st.columns([1, 1, 4])
        with b1:
            salvar = st.button("Salvar", use_container_width=True, type="primary")
        with b2:
            cancelar = st.button("Cancelar", use_container_width=True)

        if cancelar:
            st.session_state.pop("add_gerente", None)
            st.rerun()

        if salvar:
            nome = st.session_state.get(nome_key, "").strip()
            whatsapp = st.session_state.get(whats_key, "").strip()

            nome_valido, msg_nome = validar_nome(nome)
            if not nome_valido:
                error_message(msg_nome)
                st.stop()

            whatsapp_formatado = formatar_whatsapp(whatsapp)
            whatsapp_valido, msg_whatsapp = validar_whatsapp(whatsapp_formatado)
            if not whatsapp_valido:
                error_message(msg_whatsapp)
                st.stop()

            if whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"]):
                error_message("Este WhatsApp ja esta cadastrado (gerente ou vendedor)")
                st.stop()

            try:
                adicionar_gerente(loja["loja_id"], nome, whatsapp_formatado)
                success_message(f"Gerente **{nome}** adicionado!")
                st.session_state.pop("add_gerente", None)
                st.rerun()
            except Exception as e:
                error_message(f"Erro ao salvar: {e}")

# Tabela editavel
if gerentes:
    st.caption(f"{len(gerentes)} gerente(s) cadastrado(s). Edite diretamente na tabela.")

    pode_remover = len(gerentes) > 1

    # Montar DataFrame com coluna Remover
    df = pd.DataFrame(gerentes)
    df = df[["id", "nome", "numero_whatsapp"]]
    df.columns = ["id", "Nome", "WhatsApp"]
    df["Remover"] = False

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Remover"] if not pode_remover else [],
        column_config={
            "id": None,  # coluna oculta
            "Nome": st.column_config.TextColumn("Nome", width="medium"),
            "WhatsApp": st.column_config.TextColumn("WhatsApp", width="medium"),
            "Remover": st.column_config.CheckboxColumn(
                "Remover",
                width="small",
                help="Remover gerente" if pode_remover else "Nao pode remover o unico gerente",
            ),
        },
        key="gerentes_editor",
    )

    # Processar remocoes
    if edited is not None:
        removidos = edited[edited["Remover"]]
        for _, row in removidos.iterrows():
            try:
                deletar_gerente(row["id"], loja["loja_id"])
                success_message(f"**{row['Nome']}** removido")
            except Exception as e:
                error_message(f"Erro ao remover {row['Nome']}: {e}")
        if not removidos.empty:
            st.rerun()

    # Detectar alteracoes de nome/whatsapp e salvar
    if edited is not None:
        for idx, row in edited.iterrows():
            original = df.iloc[idx]
            nome_mudou = row["Nome"] != original["Nome"]
            whats_mudou = row["WhatsApp"] != original["WhatsApp"]

            if nome_mudou or whats_mudou:
                gid = row["id"]
                novo_nome = row["Nome"].strip()
                novo_whats = row["WhatsApp"].strip()

                nome_valido, msg_nome = validar_nome(novo_nome)
                if not nome_valido:
                    error_message(f"{original['Nome']}: {msg_nome}")
                    continue

                whatsapp_formatado = formatar_whatsapp(novo_whats)
                whatsapp_valido, msg_whatsapp = validar_whatsapp(whatsapp_formatado)
                if not whatsapp_valido:
                    error_message(f"{novo_nome}: {msg_whatsapp}")
                    continue

                if whats_mudou and whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"], gid):
                    error_message(f"{novo_nome}: WhatsApp ja cadastrado")
                    continue

                try:
                    editar_gerente(gid, novo_nome, whatsapp_formatado, loja["loja_id"])
                    success_message(f"**{novo_nome}** atualizado!")
                    st.rerun()
                except Exception as e:
                    error_message(f"Erro ao salvar {novo_nome}: {e}")
else:
    info_message("Nenhum gerente cadastrado. Clique em 'Adicionar Gerente' para comecar.")
