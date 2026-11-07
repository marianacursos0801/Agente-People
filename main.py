"""Monta a interface Streamlit da Central de Recrutamento."""

import os  # Verifica se os arquivos de configuração estão disponíveis.
from pathlib import Path  # Encontra o CSS ao lado deste arquivo.

import streamlit as st  # Componentes visuais e estado da página.

# Importamos o modelo, o ID da planilha e a função que processa pedidos.
from agente import MODELO_GROQ, PLANILHA_ID, executar_agente_rh

# Configuramos o título, ícone e largura da aplicação.
st.set_page_config(
    page_title="Central de Recrutamento",
    page_icon="\U0001F4BC",
    layout="wide"
)

# O CSS separado define cores, espaçamentos, cartões e botões.
css_path = Path(__file__).with_name("styles.css")
css = css_path.read_text(encoding="utf-8")
st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)

# Estes indicadores mostram se as configurações principais estão presentes.
groq_configurado = bool(os.environ.get("GROQ_API_KEY"))
google_configurado = os.path.exists("credentials.json")
planilha_configurada = bool(PLANILHA_ID)

# A barra lateral resume o nome do sistema, integrações e modelo utilizado.
with st.sidebar:
    st.markdown('<div class="brand-mark">TALENT WORKSPACE</div>', unsafe_allow_html=True)
    st.markdown("## Central de RH")
    st.caption("Assistente de recrutamento")
    st.divider()

    st.markdown("#### Integrações")
    # Cada par associa o nome de uma integração à sua configuração.
    for label, configurado in (
        ("Assistente de IA", groq_configurado),
        ("Google Workspace", google_configurado),
        ("Planilha de candidatos", planilha_configurada),
    ):
        # A classe CSS muda a cor do indicador conforme o estado.
        estado = "Configurado" if configurado else "Verificar configuração"
        classe = "ok" if configurado else "off"
        st.markdown(
            f'<div class="status-line"><span class="status-dot {classe}"></span>'
            f'<span>{label}</span></div>',
            unsafe_allow_html=True
        )
        if not configurado:
            st.caption(estado)

    st.divider()
    st.caption("Modelo de IA")
    st.code(MODELO_GROQ, language=None)
    st.caption("Conectado via Groq Cloud")

# A área principal apresenta o propósito da aplicação.
st.markdown('<div class="eyebrow">OPERAÇÕES DE TALENT ACQUISITION</div>', unsafe_allow_html=True)
st.title("Gestão de recrutamento")
st.markdown(
    '<div class="page-subtitle">Agende entrevistas e mantenha os dados dos candidatos '
    'organizados em um único fluxo.</div>',
    unsafe_allow_html=True
)

# Os dois cartões explicam o que o Calendar e a planilha fazem.
st.markdown("### Integrações disponíveis")
col_calendar, col_sheets = st.columns(2)
with col_calendar:
    with st.container(border=True):
        st.markdown('<div class="integration-title">Agenda e entrevistas</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="integration-copy">Crie convites de entrevista no Google Calendar '
            'com link do Google Meet.</div>',
            unsafe_allow_html=True
        )
with col_sheets:
    with st.container(border=True):
        st.markdown('<div class="integration-title">Gestão de candidatos</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="integration-copy">Registre candidatos, vagas e status diretamente '
            'na planilha conectada.</div>',
            unsafe_allow_html=True
        )

# O formulário aceita pedidos de agendamento, cadastro ou ambos.
st.markdown("### Nova solicitação")
st.markdown(
    "Descreva as ações desejadas e inclua os dados do candidato, a vaga e os horários "
    "quando aplicável. Ao agendar uma entrevista, o candidato também é registrado "
    "automaticamente na planilha."
)

# O formulário só envia o texto quando o botão é pressionado.
with st.form("solicitacao_recrutamento"):
    prompt_usuario = st.text_area(
        "Instruções",
        key="prompt_input",
        height=150,
        placeholder=(
            "Ex.: Agende uma entrevista com nome@empresa.com em 30/10/2026, "
            "das 14h às 15h, para a vaga de Analista Financeiro, e registre "
            "o candidato na planilha."
        )
    )
    submitted = st.form_submit_button(
        "Processar solicitação",
        type="primary",
        use_container_width=True
    )

# A variável submitted informa se o usuário enviou o formulário.
if submitted:
    if not prompt_usuario.strip():
        # Um pedido vazio não chama o modelo nem os serviços Google.
        st.session_state.pop("resultado_processamento", None)
        st.warning("Escreva uma instrução antes de continuar.")
    else:
        # A função do agente retorna resultados ou erros para serem exibidos.
        with st.spinner("Processando a solicitação..."):
            st.session_state.resultado_processamento = executar_agente_rh(prompt_usuario)

# O resultado fica na sessão para continuar visível após a atualização da tela.
if "resultado_processamento" in st.session_state:
    st.markdown("### Resultado da solicitação")
    for item in st.session_state.resultado_processamento:
        if isinstance(item, dict):
            tipo = next(iter(item.keys()), "erro")
            conteudo = item.get(tipo)
        else:
            try:
                tipo, conteudo = item
            except ValueError:
                tipo = "erro"
                conteudo = str(item)

        if tipo == "calendar":
            st.success(f"**Google Calendar e Meet**  \n{conteudo}")
        elif tipo in {"sheets", "planilha"}:
            st.success(f"**Google Sheets**  \n{conteudo}")
        elif tipo == "texto":
            st.info(conteudo)
        elif tipo == "erro":
            st.error(conteudo)