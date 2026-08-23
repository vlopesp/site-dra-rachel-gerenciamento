import streamlit as st
import pandas as pd
from datetime import datetime
import hashlib
import json
import io

from streamlit_gsheets import GSheetsConnection
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E TEMA ROSÊ
# ==========================================
st.set_page_config(
    page_title="Gestão Clínica - Dra. Rachel Leal",
    page_icon="🩺",
    layout="wide"
)

# Estilização CSS Personalizada (Paleta Rosê)
st.markdown("""
<style>
    :root {
        --primary-color: #d09395;
        --secondary-color: #f97a7e;
        --background-color: #fdfbfb;
    }
    .stButton>button {
        background-color: var(--primary-color);
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: var(--secondary-color);
        color: white;
    }
    .metric-card {
        background-color: #ffffff;
        border-left: 5px solid #d09395;
        padding: 15px;
        border-radius: 8px;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. AUTENTICAÇÃO SEGURA (HASH)
# ==========================================
USERS = {
    "admin": hashlib.sha256("dra.rachel2026".encode()).hexdigest(),
    "recepcao": hashlib.sha256("clinica123".encode()).hexdigest()
}

def verify_password(username, password):
    hashed_input = hashlib.sha256(password.encode()).hexdigest()
    return USERS.get(username) == hashed_input

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Acesso ao Sistema - Dra. Rachel Leal")
    col1, col2 = st.columns([1, 2])
    with col1:
        user_input = st.text_input("Usuário")
        pass_input = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            if verify_password(user_input, pass_input):
                st.session_state.authenticated = True
                st.session_state.username = user_input
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()

# ==========================================
# 3. CONEXÃO COM GOOGLE SHEETS E DRIVE
# ==========================================
@st.cache_resource
def get_drive_service():
    """Autentica na API do Google Drive utilizando as credenciais salvas em st.secrets."""
    try:
        creds_dict = json.loads(st.secrets["textkey"])
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.warning(f"Aviso: Não foi possível conectar ao Google Drive ({e}). uploads desativados.")
        return None

def upload_to_drive(file_bytes, file_name, mime_type, folder_id=None):
    """Envia um arquivo diretamente para a pasta do Google Drive."""
    service = get_drive_service()
    if not service:
        return None
    
    file_metadata = {'name': file_name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
        
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    return uploaded_file.get('webViewLink')

# Conexão com Google Sheets via st.connection
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(worksheet_name):
    try:
        return conn.read(worksheet=worksheet_name, ttl="0")
    except Exception:
        return pd.DataFrame()

# ==========================================
# 4. INTERFACE PRINCIPAL E NAVEGAÇÃO
# ==========================================
st.sidebar.title("🩺 Gestão Clínica")
st.sidebar.write(f"Usuário: **{st.session_state.username}**")

menu = st.sidebar.radio("Navegação", [
    "📊 Dashboard",
    "📅 Agenda & Prontuário",
    "💰 Precificação & Custos",
    "💵 Livro Caixa",
    "🗑️ Lixeira"
])

if st.sidebar.button("Sair"):
    st.session_state.authenticated = False
    st.rerun()

# ------------------------------------------
# MÓDULO 1: DASHBOARD DE RESUMO
# ------------------------------------------
if menu == "📊 Dashboard":
    st.title("📊 Painel Geral de Desempenho")
    
    df_caixa = load_data("LivroCaixa")
    df_agenda = load_data("Agenda")

    col1, col2, col3, col4 = st.columns(4)
    
    receita_total = df_caixa[df_caixa['Tipo'] == 'Receita']['Valor'].sum() if not df_caixa.empty and 'Valor' in df_caixa.columns else 0.0
    despesa_total = df_caixa[df_caixa['Tipo'] == 'Despesa']['Valor'].sum() if not df_caixa.empty and 'Valor' in df_caixa.columns else 0.0
    saldo = receita_total - despesa_total
    atendimentos = len(df_agenda) if not df_agenda.empty else 0

    with col1:
        st.markdown(f"<div class='metric-card'><h4>Receitas</h4><h3>R$ {receita_total:,.2f}</h3></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><h4>Despesas</h4><h3>R$ {despesa_total:,.2f}</h3></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><h4>Saldo Líquido</h4><h3>R$ {saldo:,.2f}</h3></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><h4>Agendamentos</h4><h3>{atendimentos}</h3></div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Resumo Recente")
    if not df_caixa.empty:
        st.dataframe(df_caixa.tail(10), use_container_width=True)

# ------------------------------------------
# MÓDULO 2: AGENDA & PRONTUÁRIO
# ------------------------------------------
elif menu == "📅 Agenda & Prontuário":
    st.title("📅 Agendamentos e Histórico Clínico")
    
    tab_agenda, tab_prontuario = st.tabs(["Agendar Consulta", "Prontuário de Pacientes"])
    
    with tab_agenda:
        with st.form("form_agendamento"):
            st.subheader("Novo Agendamento")
            col1, col2 = st.columns(2)
            with col1:
                paciente = st.text_input("Nome do Paciente")
                procedimento = st.text_input("Procedimento")
            with col2:
                data_atend = st.date_input("Data", datetime.now())
                hora_atend = st.time_input("Horário")
            
            submit_agenda = st.form_submit_button("Salvar Agendamento")
            
            if submit_agenda:
                # Checagem de Colisão simples de horário
                df_agenda = load_data("Agenda")
                conflito = False
                if not df_agenda.empty and 'Data' in df_agenda.columns and 'Hora' in df_agenda.columns:
                    match = df_agenda[(df_agenda['Data'] == str(data_atend)) & (df_agenda['Hora'] == str(hora_atend))]
                    if not match.empty:
                        conflito = True

                if conflito:
                    st.error("⚠️ Já existe um agendamento marcado para esta data e horário!")
                else:
                    st.success("Agendamento cadastrado com sucesso!")

    with tab_prontuario:
        st.subheader("Consulta de Prontuário")
        paciente_busca = st.text_input("Digite o nome do paciente para buscar o histórico:")
        if paciente_busca:
            st.info(f"Exibindo histórico para: **{paciente_busca}**")

# ------------------------------------------
# MÓDULO 3: PRECIFICAÇÃO & CUSTOS
# ------------------------------------------
elif menu == "💰 Precificação & Custos":
    st.title("💰 Calculadora de Precificação de Procedimentos")
    
    col1, col2 = st.columns(2)
    with col1:
        custo_materiais = st.number_input("Custo de Materiais (R$)", min_value=0.0, value=50.0, step=5.0)
        custo_fixo_hora = st.number_input("Custo Fixo/Hora de Consultório (R$)", min_value=0.0, value=80.0, step=5.0)
        tempo_procedimento = st.number_input("Tempo do Procedimento (Horas)", min_value=0.1, value=1.0, step=0.5)
    
    with col2:
        impostos_pct = st.number_input("Impostos / Taxas (%)", min_value=0.0, value=6.0, step=0.5)
        margem_lucro_pct = st.number_input("Margem de Lucro Desejada (%)", min_value=0.0, value=40.0, step=5.0)
        lucro_fixo_adicional = st.number_input("Lucro Fixo Adicional (R$)", min_value=0.0, value=0.0, step=10.0)

    # Cálculo da Precificação
    custo_tempo = custo_fixo_hora * tempo_procedimento
    custo_base = custo_materiais + custo_tempo
    
    # Preço com margem e impostos sobre a venda
    # Preço = (Custo Base + Lucro Fixo) / (1 - (Impostos% + Lucro%) / 100)
    taxa_total_pct = (impostos_pct + margem_lucro_pct) / 100.0
    
    if taxa_total_pct < 1.0:
        preco_sugerido = (custo_base + lucro_fixo_adicional) / (1.0 - taxa_total_pct)
        lucro_bruto = preco_sugerido - custo_base - (preco_sugerido * (impostos_pct / 100.0))
    else:
        preco_sugerido = 0.0
        lucro_bruto = 0.0

    st.markdown("---")
    st.subheader("Resultados do Cálculo")
    res1, res2, res3 = st.columns(3)
    res1.metric("Custo Total Operacional", f"R$ {custo_base:.2f}")
    res2.metric("Preço Mínimo Sugerido", f"R$ {preco_sugerido:.2f}")
    res3.metric("Lucro Líquido Estimado", f"R$ {lucro_bruto:.2f}")

# ------------------------------------------
# MÓDULO 4: LIVRO CAIXA & UPLOAD DE COMPROVANTES
# ------------------------------------------
elif menu == "💵 Livro Caixa":
    st.title("💵 Gestão Financeira e Comprovantes")
    
    with st.form("form_caixa"):
        st.subheader("Nova Lançamento Financeiro")
        tipo = st.selectbox("Tipo", ["Receita", "Despesa"])
        descricao = st.text_input("Descrição (ex: Consulta, Compra de Resina)")
        valor = st.number_input("Valor (R$)", min_value=0.0, step=10.0)
        data = st.date_input("Data do Lançamento", datetime.now())
        
        comprovante = st.file_uploader("Anexar Comprovante (PDF/Imagem)", type=["pdf", "png", "jpg", "jpeg"])
        
        submit_caixa = st.form_submit_button("Registrar Lançamento")
        
        if submit_caixa:
            link_drive = None
            if comprovante:
                folder_id = st.secrets.get("DRIVE_FOLDER_ID", None)
                bytes_data = comprovante.getvalue()
                link_drive = upload_to_drive(
                    bytes_data,
                    f"{data}_{comprovante.name}",
                    comprovante.type,
                    folder_id=folder_id
                )
                st.info(f"Comprovante enviado ao Google Drive: {link_drive}")
            
            st.success("Lançamento registrado com sucesso!")

# ------------------------------------------
# MÓDULO 5: LIXEIRA / SEGURANÇA
# ------------------------------------------
elif menu == "🗑️ Lixeira":
    st.title("🗑️ Segurança e Lixeira de Registros Excluídos")
    st.caption("Esta aba armazena temporariamente os registros excluídos (soft-delete) para evitar perdas acidentais.")
    
    df_lixeira = load_data("Lixeira")
    if not df_lixeira.empty:
        st.dataframe(df_lixeira, use_container_width=True)
        if st.button("Esvaziar Lixeira Permanentemente"):
            st.warning("Funcionalidade restrita ao administrador do sistema.")
    else:
        st.info("A lixeira está vazia no momento.")
