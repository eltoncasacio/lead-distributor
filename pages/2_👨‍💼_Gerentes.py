"""
Gestao de Gerentes.
"""
import streamlit as st
import pandas as pd
from utils.ui import render_page_header, loading_spinner, success_message, error_message, info_message, inject_global_css
from utils.auth import obter_loja_logada
from utils.theme import get_colors
from utils.queries import (
    listar_gerentes,
    adicionar_gerente,
    editar_gerente,
    desativar_gerente,
    deletar_gerente,
    whatsapp_ja_existe
)
from utils.validators import validar_whatsapp, validar_nome, formatar_whatsapp

# Header compacto
render_page_header("Gerentes")

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
if "editando_gerente" not in st.session_state:
    st.session_state.editando_gerente = None

# Buscar gerentes
with loading_spinner("Carregando gerentes..."):
    gerentes = listar_gerentes(loja["loja_id"])

# Botao adicionar
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("Adicionar Gerente", use_container_width=True, type="primary"):
        st.session_state.editando_gerente = "novo"
        st.rerun()

# Formulario de adicionar/editar
if st.session_state.editando_gerente:
    gerente_atual = None
    titulo_form = "Adicionar Novo Gerente"

    if st.session_state.editando_gerente != "novo":
        # Modo edicao
        gerente_atual = next(
            (g for g in gerentes if g["id"] == st.session_state.editando_gerente),
            None
        )
        titulo_form = f"Editar Gerente: {gerente_atual['nome']}"

    with st.form("form_gerente", clear_on_submit=True):
        st.markdown(f"### {titulo_form}")

        nome = st.text_input(
            "Nome completo",
            value=gerente_atual["nome"] if gerente_atual else "",
            placeholder="Ex: Carlos Mendes"
        )

        whatsapp = st.text_input(
            "WhatsApp",
            value=gerente_atual["numero_whatsapp"] if gerente_atual else "",
            placeholder="Ex: 11999998888",
            help="DDD + numero (o 55 e adicionado automaticamente)"
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("Salvar", use_container_width=True)
        with col_btn2:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if cancelar:
            st.session_state.editando_gerente = None
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
            excluir_id = gerente_atual["id"] if gerente_atual else None
            if whatsapp_ja_existe(whatsapp_formatado, loja["loja_id"], excluir_id):
                error_message("Este WhatsApp ja esta cadastrado (gerente ou vendedor)")
                st.stop()

            # Salvar
            try:
                if gerente_atual:
                    # Editar
                    editar_gerente(gerente_atual["id"], nome, whatsapp_formatado)
                    success_message(f"Gerente **{nome}** atualizado!")
                else:
                    # Adicionar
                    adicionar_gerente(loja["loja_id"], nome, whatsapp_formatado)
                    success_message(f"Gerente **{nome}** adicionado!")

                st.session_state.editando_gerente = None
                st.rerun()

            except Exception as e:
                error_message(f"Erro ao salvar: {str(e)}")

# Tabela de gerentes
if gerentes:
    with st.container(border=True):
        st.markdown("### Lista de Gerentes")

        # Preparar dados para tabela
        df = pd.DataFrame(gerentes)
        df = df[["nome", "numero_whatsapp", "ativo"]]
        df.columns = ["Nome", "WhatsApp", "Ativo"]
        df["Ativo"] = df["Ativo"].apply(lambda x: "Sim" if x else "Nao")

        # Mostrar tabela
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # Acoes por gerente
    st.markdown("### Acoes")
    for gerente in gerentes:
        col1, col2 = st.columns([4, 2])

        with col1:
            st.text(gerente["nome"])

        with col2:
            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                if st.button(":material/edit:", key=f"edit_{gerente['id']}", help="Editar gerente"):
                    st.session_state.editando_gerente = gerente["id"]
                    st.rerun()
            with btn2:
                if gerente["ativo"]:
                    if st.button(":material/pause:", key=f"deactivate_{gerente['id']}", help="Desativar gerente"):
                        desativar_gerente(gerente["id"])
                        success_message(f"Gerente **{gerente['nome']}** desativado")
                        st.rerun()
            with btn3:
                if st.button(":material/delete:", key=f"delete_{gerente['id']}", help="Remover gerente"):
                    deletar_gerente(gerente["id"])
                    success_message(f"Gerente **{gerente['nome']}** removido")
                    st.rerun()

else:
    info_message("Nenhum gerente cadastrado. Clique em 'Adicionar Gerente' para comecar.")

# Dicas de uso
st.divider()
with st.expander("Dicas de Uso"):
    st.markdown("""
    **Sobre gerentes:**
    - Gerentes tem acesso aos comandos WhatsApp: `status` e `leads`
    - Podem visualizar metricas e relatorios do dia
    - Nao recebem leads (apenas vendedores recebem)

    **Status:**
    - **Ativo**: Pode usar comandos WhatsApp
    - **Inativo**: Nao pode usar comandos (mas permanece cadastrado)

    **Importante:**
    - O WhatsApp do gerente deve ser unico (nao pode ser usado como vendedor)
    """)
