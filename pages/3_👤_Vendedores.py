"""
Gestao de Vendedores.
"""

import re
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
    listar_vendedores,
    adicionar_vendedor,
    editar_vendedor,
    alterar_status_vendedor,
    whatsapp_ja_existe,
    contar_vendedores_ativos,
    listar_mensagens_prontas_loja,
    listar_mensagens_prontas_vendedor,
    adicionar_mensagem_pronta,
    editar_mensagem_pronta,
    deletar_mensagem_pronta,
)
from utils.validators import validar_whatsapp, validar_nome, formatar_whatsapp

# Header compacto
render_page_header("Vendedores")

# CSS global
inject_global_css()

loja = obter_loja_logada()

# Estado para controlar edicao
if "editando_vendedor" not in st.session_state:
    st.session_state.editando_vendedor = None

# Buscar vendedores
with loading_spinner("Carregando vendedores..."):
    vendedores = listar_vendedores(loja["loja_id"])

# Botao adicionar
_, col_add = st.columns([3, 1])
with col_add:
    if st.button("Adicionar Vendedor", use_container_width=True, type="primary"):
        st.session_state.editando_vendedor = "novo"
        st.rerun()

# Formulario de adicionar/editar (aparece acima da tabela)
if st.session_state.editando_vendedor:
    vendedor_atual = None
    if st.session_state.editando_vendedor != "novo":
        vendedor_atual = next(
            (v for v in vendedores if v["id"] == st.session_state.editando_vendedor),
            None,
        )

    with st.container(border=True):
        st.markdown(f"**{'Editar Vendedor' if vendedor_atual else 'Novo Vendedor'}**")
        c1, c2 = st.columns(2)
        nome_key = "form_vendedor_nome"
        whats_key = "form_vendedor_whats"

        # Inicializar valores para edicao (apenas uma vez)
        init_key = "_init_form_vendedor"
        if init_key not in st.session_state:
            st.session_state[init_key] = True
            if vendedor_atual:
                st.session_state[nome_key] = vendedor_atual["nome"]
                st.session_state[whats_key] = vendedor_atual["numero_whatsapp"]
            else:
                st.session_state.setdefault(nome_key, "")
                st.session_state.setdefault(whats_key, "")

        with c1:
            st.text_input("Nome", placeholder="Ex: Joao Silva", key=nome_key)
        with c2:
            st.text_input("WhatsApp", placeholder="Ex: 11999998888", help="DDD + numero (55 adicionado automaticamente)", key=whats_key)
        b1, b2, _ = st.columns([1, 1, 4])
        with b1:
            salvar = st.button("Salvar", use_container_width=True, type="primary")
        with b2:
            cancelar = st.button("Cancelar", use_container_width=True)

        if cancelar:
            for k in [nome_key, whats_key, init_key]:
                st.session_state.pop(k, None)
            st.session_state.editando_vendedor = None
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

            excluir_id = vendedor_atual["id"] if vendedor_atual else None
            if whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"], excluir_id):
                error_message("Este WhatsApp ja esta cadastrado (gerente ou vendedor)")
                st.stop()

            try:
                if vendedor_atual:
                    editar_vendedor(vendedor_atual["id"], nome, whatsapp_formatado)
                    success_message(f"Vendedor **{nome}** atualizado!")
                else:
                    adicionar_vendedor(loja["loja_id"], nome, whatsapp_formatado)
                    success_message(f"Vendedor **{nome}** adicionado a fila!")
                for k in [nome_key, whats_key, init_key]:
                    st.session_state.pop(k, None)
                st.session_state.editando_vendedor = None
                st.rerun()
            except Exception as e:
                msg = str(e)
                if "23505" in msg or "duplicate key" in msg.lower():
                    error_message("Este numero de WhatsApp ja esta cadastrado.")
                else:
                    error_message(f"Erro ao salvar: {msg}")

# ============================================
# TABELA DE VENDEDORES (st.data_editor + delete)
# ============================================

vendedores_visiveis = [v for v in vendedores if v["status"] != "removido"]

if vendedores_visiveis:
    st.caption(f"{len(vendedores_visiveis)} vendedor(es) cadastrado(s). Clique duas vezes na celula para editar — salva automaticamente.")

    df = pd.DataFrame(vendedores_visiveis)
    df = df[["id", "nome", "numero_whatsapp", "status"]]
    df.columns = ["id", "Nome", "WhatsApp", "Status"]
    df["Excluir"] = False

    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "id": None,
            "Nome": st.column_config.TextColumn("Nome", width="medium"),
            "WhatsApp": st.column_config.TextColumn("WhatsApp", width="medium"),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["ativo", "inativo"],
                required=True,
                width="small",
            ),
            "Excluir": st.column_config.CheckboxColumn(
                "Excluir",
                width="small",
                help="Marque para remover o vendedor da fila",
            ),
        },
        key="vendedores_editor",
    )

    # Processar exclusoes
    if edited is not None:
        removidos = edited[edited["Excluir"]]
        for _, row in removidos.iterrows():
            if row["Status"] == "ativo":
                total_ativos = contar_vendedores_ativos(loja["loja_id"])
                if total_ativos <= 1:
                    error_message("Nao pode remover o unico vendedor ativo. Adicione outro vendedor primeiro.")
                    continue
            alterar_status_vendedor(row["id"], "removido")
            success_message(f"**{row['Nome']}** removido da fila")
        if not removidos.empty:
            st.rerun()

    # Processar edicoes (nome, whatsapp, status) — auto-save
    if edited is not None:
        for idx, row in edited.iterrows():
            if row["Excluir"]:
                continue  # ja processado acima

            original = df.iloc[idx]
            nome_mudou = row["Nome"] != original["Nome"]
            whats_mudou = row["WhatsApp"] != original["WhatsApp"]
            status_mudou = row["Status"] != original["Status"]

            if not (nome_mudou or whats_mudou or status_mudou):
                continue

            vid = row["id"]

            # Status change
            if status_mudou:
                novo_status = row["Status"]
                if novo_status == "inativo" and original["Status"] == "ativo":
                    total_ativos = contar_vendedores_ativos(loja["loja_id"])
                    if total_ativos <= 1:
                        error_message(f"Nao pode desativar **{row['Nome']}** — unico vendedor ativo")
                        continue
                alterar_status_vendedor(vid, novo_status)
                success_message(f"**{row['Nome']}** {'ativado' if novo_status == 'ativo' else 'inativado'}")
                st.rerun()

            # Nome/WhatsApp change
            if nome_mudou or whats_mudou:
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

                if whats_mudou and whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"], vid):
                    error_message(f"{novo_nome}: WhatsApp ja cadastrado")
                    continue

                try:
                    editar_vendedor(vid, novo_nome, whatsapp_formatado)
                    success_message(f"**{novo_nome}** atualizado!")
                    st.rerun()
                except Exception as e:
                    error_message(f"Erro ao salvar {novo_nome}: {e}")

elif not vendedores:
    info_message("Nenhum vendedor cadastrado. Clique em 'Adicionar Vendedor' para comecar.")
else:
    info_message("Todos os vendedores foram removidos. Adicione novos vendedores para comecar.")

# ============================================
# MENSAGENS PRONTAS
# ============================================

st.divider()
st.markdown("### Mensagens Prontas")
st.info(
    "A primeira mensagem da lista é enviada automaticamente como link wa.me quando um lead e distribuido. O vendedor clica no link para iniciar a conversa."
)

# Estado para controlar edicao de mensagem
if "editando_mensagem" not in st.session_state:
    st.session_state.editando_mensagem = None

tab_loja, tab_vendedor = st.tabs(["Padrao da Loja", "Por Vendedor"])

# --- Constantes de placeholders ---
_PLACEHOLDERS_VALIDOS = {"nome_cliente", "vendedor_nome", "anuncio", "origem"}
_PLACEHOLDER_INFO = {
    "{nome_cliente}": "Nome do cliente que enviou o lead",
    "{vendedor_nome}": "Seu nome (nome do vendedor)",
    "{anuncio}": "Veiculo ou anuncio de interesse",
    "{origem}": "Plataforma de origem (iCarros, NaPista, etc.)",
}
_PREVIEW_DADOS = {
    "nome_cliente": "Joao Silva",
    "vendedor_nome": "Carlos",
    "anuncio": "Honda Civic 2020",
    "origem": "iCarros",
}


def _inserir_placeholder(key: str, placeholder: str):
    """Callback para inserir placeholder no final do texto."""
    st.session_state[key] = st.session_state.get(key, "") + placeholder


def _render_form_mensagem(
    key_prefix: str, loja_id: str, vendedor_id=None, mensagem_atual=None
):
    """Renderiza formulario de adicionar/editar mensagem pronta."""
    titulo_form = "Editar Mensagem" if mensagem_atual else "Nova Mensagem"
    st.markdown(f"**{titulo_form}**")

    titulo_key = f"titulo_{key_prefix}"
    texto_key = f"texto_{key_prefix}"

    # Inicializar session_state com valores existentes (apenas uma vez)
    init_key = f"_init_{key_prefix}"
    if init_key not in st.session_state:
        st.session_state[init_key] = True
        if mensagem_atual:
            st.session_state[titulo_key] = mensagem_atual["titulo"]
            st.session_state[texto_key] = mensagem_atual["texto"]
        else:
            st.session_state.setdefault(titulo_key, "")
            st.session_state.setdefault(texto_key, "")

    st.text_input(
        "Titulo",
        placeholder="Ex: Saudacao padrao",
        key=titulo_key,
    )

    # Chips de placeholder
    st.caption("Clique para inserir no texto:")
    chip_cols = st.columns(4)
    for i, (ph, descr) in enumerate(_PLACEHOLDER_INFO.items()):
        with chip_cols[i]:
            st.button(
                ph,
                key=f"chip_{key_prefix}_{ph}",
                help=descr,
                on_click=_inserir_placeholder,
                args=(texto_key, ph),
                use_container_width=True,
            )

    st.text_area(
        "Texto da mensagem",
        placeholder="Ola {nome_cliente}! Aqui e {vendedor_nome}...",
        key=texto_key,
        height=120,
    )

    # Preview ao vivo
    texto_atual = st.session_state.get(texto_key, "")
    if texto_atual.strip():
        preview_texto = texto_atual
        for var, valor in _PREVIEW_DADOS.items():
            preview_texto = preview_texto.replace(f"{{{var}}}", f"**{valor}**")
        with st.container(border=True):
            st.markdown(f"**Preview:**\n\n{preview_texto}")

    # Botoes Salvar / Cancelar
    col_s, col_c = st.columns(2)
    with col_s:
        salvar = st.button(
            "Salvar",
            key=f"salvar_{key_prefix}",
            use_container_width=True,
            type="primary",
        )
    with col_c:
        cancelar = st.button(
            "Cancelar", key=f"cancelar_{key_prefix}", use_container_width=True
        )

    if cancelar:
        # Limpar estado do formulario
        for k in [titulo_key, texto_key, init_key]:
            st.session_state.pop(k, None)
        st.session_state.editando_mensagem = None
        st.rerun()

    if salvar:
        titulo = st.session_state.get(titulo_key, "").strip()
        texto = st.session_state.get(texto_key, "").strip()

        if not titulo:
            error_message("Titulo e obrigatorio")
            st.stop()
        if not texto:
            error_message("Texto e obrigatorio")
            st.stop()

        # Validar placeholders desconhecidos
        encontrados = re.findall(r"\{([^}]+)\}", texto)
        desconhecidos = [f for f in encontrados if f not in _PLACEHOLDERS_VALIDOS]
        if desconhecidos:
            nomes = ", ".join(f"{{{d}}}" for d in desconhecidos)
            error_message(
                f"Placeholder desconhecido: {nomes}. Use os botoes acima para inserir placeholders corretos."
            )
            st.stop()

        try:
            if mensagem_atual:
                editar_mensagem_pronta(mensagem_atual["id"], titulo, texto, loja_id)
                success_message("Mensagem atualizada!")
            else:
                adicionar_mensagem_pronta(loja_id, titulo, texto, vendedor_id)
                success_message("Mensagem adicionada!")
            # Limpar estado do formulario
            for k in [titulo_key, texto_key, init_key]:
                st.session_state.pop(k, None)
            st.session_state.editando_mensagem = None
            st.rerun()
        except Exception as e:
            error_message(f"Erro: {e}")


def _render_lista_mensagens(mensagens: list, key_prefix: str, loja_id: str):
    """Renderiza lista de mensagens com botoes de editar/deletar."""
    if not mensagens:
        info_message("Nenhuma mensagem cadastrada.")
        return

    for msg in mensagens:
        with st.container(border=True):
            col_info, col_acoes = st.columns([6, 1])
            with col_info:
                st.markdown(f"**{msg['titulo']}**")
                st.text(msg["texto"])
            with col_acoes:
                b1, b2 = st.columns(2)
                with b1:
                    if st.button(
                        ":material/edit:",
                        key=f"edit_msg_{key_prefix}_{msg['id']}",
                        help="Editar",
                    ):
                        st.session_state.editando_mensagem = msg["id"]
                        st.rerun()
                with b2:
                    if st.button(
                        ":material/delete:",
                        key=f"del_msg_{key_prefix}_{msg['id']}",
                        help="Deletar",
                    ):
                        deletar_mensagem_pronta(msg["id"], loja_id)
                        success_message(f"Mensagem **{msg['titulo']}** removida")
                        st.rerun()

        # Form de edicao inline
        if st.session_state.editando_mensagem == msg["id"]:
            _render_form_mensagem(
                key_prefix=f"edit_{key_prefix}_{msg['id']}",
                loja_id=loja_id,
                mensagem_atual=msg,
            )


# --- Tab Padrao da Loja ---
with tab_loja:
    mensagens_loja = listar_mensagens_prontas_loja(loja["loja_id"])

    col_add, _ = st.columns([1, 3])
    with col_add:
        if st.button(
            "Adicionar Mensagem",
            key="add_msg_loja",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.editando_mensagem = "nova_loja"
            st.rerun()

    if st.session_state.editando_mensagem == "nova_loja":
        _render_form_mensagem(key_prefix="nova_loja", loja_id=loja["loja_id"])

    _render_lista_mensagens(mensagens_loja, "loja", loja["loja_id"])


# --- Tab Por Vendedor ---
with tab_vendedor:
    vendedores_ativos = [v for v in vendedores if v["status"] == "ativo"]
    if not vendedores_ativos:
        info_message("Nenhum vendedor ativo.")
    else:
        vendedor_selecionado = st.selectbox(
            "Selecione o vendedor",
            options=vendedores_ativos,
            format_func=lambda v: v["nome"],
            key="sel_vendedor_msg",
        )

        if vendedor_selecionado:
            vid = vendedor_selecionado["id"]
            mensagens_vendedor = listar_mensagens_prontas_vendedor(loja["loja_id"], vid)

            col_add_v, _ = st.columns([1, 3])
            with col_add_v:
                if st.button(
                    "Adicionar Mensagem",
                    key="add_msg_vendedor",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.editando_mensagem = f"nova_vendedor_{vid}"
                    st.rerun()

            if st.session_state.editando_mensagem == f"nova_vendedor_{vid}":
                _render_form_mensagem(
                    key_prefix=f"nova_v_{vid}", loja_id=loja["loja_id"], vendedor_id=vid
                )

            _render_lista_mensagens(mensagens_vendedor, f"v_{vid}", loja["loja_id"])

            if not mensagens_vendedor:
                st.caption("Este vendedor usara as mensagens padrao da loja.")


# Info util
st.divider()
with st.expander("Dicas de Uso"):
    st.markdown("""
    **Gerenciamento de vendedores:**
    - Use o botao **Adicionar Vendedor** para cadastrar novos vendedores
    - Edite **Nome**, **WhatsApp** e **Status** diretamente na tabela
    - Marque a coluna **Remover** para excluir um vendedor da fila
    - Para reordenar a fila de distribuicao, acesse o **Dashboard** e arraste os vendedores

    **Status dos vendedores:**
    - **Ativo**: Recebe leads normalmente na distribuicao Round-Robin
    - **Inativo**: Nao recebe leads, mas permanece cadastrado (pode ser reativado)
    - **Removido**: Excluido permanentemente da fila de distribuicao

    **Importante:**
    - Nao e possivel inativar ou remover o unico vendedor ativo
    - Ao adicionar um novo vendedor, ele entra automaticamente no final da fila
    - Vendedores inativos sao pulados automaticamente na distribuicao
    """)
