"""
Gestao de Vendedores.
"""
import streamlit as st
import pandas as pd
from utils.ui import render_page_header, loading_spinner, success_message, error_message, info_message, inject_global_css
from utils.auth import obter_loja_logada
from utils.theme import get_colors
from utils.queries import (
    listar_vendedores,
    adicionar_vendedor,
    editar_vendedor,
    alterar_status_vendedor,
    whatsapp_ja_existe,
    contar_vendedores_ativos,
)
from utils.validators import validar_whatsapp, validar_nome, formatar_whatsapp

# Header compacto
render_page_header("Vendedores")

# CSS global
inject_global_css()

_c = get_colors()
st.components.v1.html(f"""
<script>
(function() {{
    function colorButtons() {{
        var doc = window.parent.document;
        var buttons = doc.querySelectorAll('button[data-testid="stBaseButton-secondary"]');
        buttons.forEach(function(btn) {{
            var icon = btn.querySelector('span[data-testid="stIconMaterial"]');
            if (!icon) return;
            var text = icon.textContent.trim();
            var color = '';
            if (text === 'edit') color = '{_c["primary"]}';
            else if (text === 'pause') color = '{_c["warning"]}';
            else if (text === 'play_arrow') color = '{_c["success"]}';
            else if (text === 'delete') color = '{_c["error"]}';
            if (color) {{
                btn.style.borderColor = color;
                btn.style.color = color;
                btn.onmouseenter = function() {{ btn.style.backgroundColor = color + '22'; }};
                btn.onmouseleave = function() {{ btn.style.backgroundColor = 'transparent'; }};
            }}
        }});
    }}
    setTimeout(colorButtons, 500);
    setTimeout(colorButtons, 1500);
    setTimeout(colorButtons, 3000);
}})();
</script>
""", height=0)

loja = obter_loja_logada()

# Estado para controlar edicao
if "editando_vendedor" not in st.session_state:
    st.session_state.editando_vendedor = None

# Buscar vendedores
with loading_spinner("Carregando vendedores..."):
    vendedores = listar_vendedores(loja["loja_id"])

# Botao adicionar
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("Adicionar Vendedor", use_container_width=True, type="primary"):
        st.session_state.editando_vendedor = "novo"
        st.rerun()

# Formulario de adicionar/editar
if st.session_state.editando_vendedor:
    vendedor_atual = None
    titulo_form = "Adicionar Novo Vendedor"

    if st.session_state.editando_vendedor != "novo":
        # Modo edicao
        vendedor_atual = next(
            (v for v in vendedores if v["id"] == st.session_state.editando_vendedor),
            None
        )
        titulo_form = f"Editar Vendedor: {vendedor_atual['nome']}"

    with st.form("form_vendedor", clear_on_submit=True):
        st.markdown(f"### {titulo_form}")

        nome = st.text_input(
            "Nome completo",
            value=vendedor_atual["nome"] if vendedor_atual else "",
            placeholder="Ex: Joao Silva"
        )

        whatsapp = st.text_input(
            "WhatsApp",
            value=vendedor_atual["numero_whatsapp"] if vendedor_atual else "",
            placeholder="Ex: 11999998888",
            help="DDD + numero (o 55 e adicionado automaticamente)"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("Salvar", use_container_width=True)
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if cancelar:
            st.session_state.editando_vendedor = None
            st.rerun()

        if submitted:
            # Validacoes
            nome_valido, msg_nome = validar_nome(nome)
            if not nome_valido:
                error_message(msg_nome)
                st.stop()

            whatsapp_formatado = formatar_whatsapp(whatsapp)
            whatsapp_valido, msg_whatsapp = validar_whatsapp(whatsapp_formatado)
            if not whatsapp_valido:
                error_message(msg_whatsapp)
                st.stop()

            # Verificar se WhatsApp ja existe
            excluir_id = vendedor_atual["id"] if vendedor_atual else None
            if whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"], excluir_id):
                error_message("Este WhatsApp ja esta cadastrado (gerente ou vendedor)")
                st.stop()

            # Salvar
            try:
                if vendedor_atual:
                    # Editar
                    editar_vendedor(vendedor_atual["id"], nome, whatsapp_formatado)
                    success_message(f"Vendedor **{nome}** atualizado!")
                else:
                    # Adicionar (ordem_fila auto-calculada)
                    adicionar_vendedor(loja["loja_id"], nome, whatsapp_formatado)
                    success_message(f"Vendedor **{nome}** adicionado a fila!")

                st.session_state.editando_vendedor = None
                st.rerun()

            except Exception as e:
                msg = str(e)
                if "23505" in msg or "duplicate key" in msg.lower():
                    error_message("Este numero de WhatsApp ja esta cadastrado.")
                else:
                    error_message(f"Erro ao salvar: {msg}")

# ============================================
# TABELA DE VENDEDORES COM ACOES INTEGRADAS
# ============================================

vendedores_visiveis = [v for v in vendedores if v["status"] != "removido"]

if vendedores_visiveis:
    with st.container(border=True):
        st.markdown("### Lista de Vendedores")
        st.caption(f"Total: {len(vendedores_visiveis)} vendedor(es)")

        # Cabecalho da tabela customizada
        col_header1, col_header2, col_header3, col_header4 = st.columns([3, 2.5, 1.5, 2])
        with col_header1:
            st.markdown("**Nome**")
        with col_header2:
            st.markdown("**WhatsApp**")
        with col_header3:
            st.markdown("**Status**")
        with col_header4:
            st.markdown("**Ações**")

        st.divider()

        # Renderizar cada vendedor como linha
        for vendedor in vendedores_visiveis:
            col1, col2, col3, col4 = st.columns([3, 2.5, 1.5, 2])

            with col1:
                st.text(vendedor["nome"])

            with col2:
                # Formatar WhatsApp: +55 (11) 99999-8888
                whatsapp = vendedor["numero_whatsapp"]
                if len(whatsapp) == 13:  # 5511999998888
                    whatsapp_formatado = f"+{whatsapp[0:2]} ({whatsapp[2:4]}) {whatsapp[4:9]}-{whatsapp[9:]}"
                else:
                    whatsapp_formatado = whatsapp
                st.text(whatsapp_formatado)

            with col3:
                status_label = {
                    "ativo": "Ativo",
                    "inativo": "Inativo",
                }
                st.text(status_label.get(vendedor["status"], vendedor["status"]))

            with col4:
                btn1, btn2, btn3 = st.columns(3)
                with btn1:
                    if st.button(":material/edit:", key=f"edit_{vendedor['id']}", help="Editar vendedor"):
                        st.session_state.editando_vendedor = vendedor["id"]
                        st.rerun()
                with btn2:
                    if vendedor["status"] == "ativo":
                        total_ativos = contar_vendedores_ativos(loja["loja_id"])
                        if total_ativos <= 1:
                            st.button(":material/pause:", key=f"deactivate_{vendedor['id']}", disabled=True, help="Nao pode desativar o unico vendedor ativo")
                        else:
                            if st.button(":material/pause:", key=f"deactivate_{vendedor['id']}", help="Pausar vendedor"):
                                alterar_status_vendedor(vendedor["id"], "inativo")
                                success_message(f"**{vendedor['nome']}** inativado")
                                st.rerun()
                    else:
                        if st.button(":material/play_arrow:", key=f"activate_{vendedor['id']}", help="Ativar vendedor"):
                            alterar_status_vendedor(vendedor["id"], "ativo")
                            success_message(f"**{vendedor['nome']}** ativado")
                            st.rerun()
                with btn3:
                    if st.button(":material/delete:", key=f"remove_{vendedor['id']}", help="Remover vendedor"):
                        if vendedor["status"] == "ativo":
                            total_ativos = contar_vendedores_ativos(loja["loja_id"])
                            if total_ativos <= 1:
                                error_message("Nao pode remover o unico vendedor ativo. Adicione outro vendedor primeiro.")
                                st.stop()
                        alterar_status_vendedor(vendedor["id"], "removido")
                        success_message(f"**{vendedor['nome']}** removido da fila")
                        st.rerun()

            # Separador visual entre linhas
            if vendedor != vendedores_visiveis[-1]:
                st.divider()

elif not vendedores:
    info_message("Nenhum vendedor cadastrado. Clique em 'Adicionar Vendedor' para comecar.")
else:
    info_message("Todos os vendedores foram removidos. Adicione novos vendedores para comecar.")

# Info util
st.divider()
with st.expander("Dicas de Uso"):
    st.markdown("""
    **Gerenciamento de vendedores:**
    - Use o botao **Adicionar Vendedor** para cadastrar novos vendedores
    - Clique nos botoes da tabela para **Editar**, **Pausar/Ativar** ou **Remover** vendedores
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
