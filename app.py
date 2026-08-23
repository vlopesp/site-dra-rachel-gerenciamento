import streamlit as st
import pandas as pd
import hashlib
import io
import os
import base64
import calendar
import re
from datetime import datetime, timedelta, time
from streamlit_gsheets import GSheetsConnection
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# 1. CONFIGURAÇÃO DE PÁGINA E DESIGN/TEMA FIXO
# ==========================================
st.set_page_config(
    page_title="Dra. Rachel Leal - Gestão & Precificação",
    page_icon="🦷",
    layout="wide"
)

ROSE_PRIMARY = "#d19496"
ROSE_SECONDARY = "#e8b9b3"
DARK_TEXT = "#2d2324"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Allura&family=Comfortaa:wght@400;600;700&display=swap');

    .stApp {{
        background-color: #fdfbfb !important;
        color: {DARK_TEXT} !important;
    }}
    
    p, span, label, h1, h2, h3, h4, h5, h6, div, td, th {{
        color: {DARK_TEXT} !important;
        font-family: 'Comfortaa', cursive, sans-serif;
    }}

    .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input, .stTimeInput input, .stTextArea textarea {{
        background-color: #ffffff !important;
        color: {DARK_TEXT} !important;
        border: 1px solid {ROSE_PRIMARY} !important;
        border-radius: 6px !important;
    }}
    
    .stButton > button {{
        background-color: {ROSE_PRIMARY} !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
    }}
    
    .stButton > button p {{
        color: #ffffff !important;
    }}

    .stButton > button:hover {{
        background-color: {ROSE_SECONDARY} !important;
    }}
    
    .stTabs [data-baseweb="tab-list"] {{
        gap: 6px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background-color: #f5e8e8 !important;
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 16px !important;
    }}

    .stTabs [aria-selected="true"] {{
        background-color: {ROSE_PRIMARY} !important;
    }}

    .stTabs [aria-selected="true"] p {{
        color: #ffffff !important;
    }}

    .agenda-card {{
        background-color: #ffffff;
        border-left: 5px solid {ROSE_PRIMARY};
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}

    .cal-header {{
        text-align: center;
        font-weight: bold;
        background-color: #f5e8e8;
        padding: 5px;
        border-radius: 4px;
        margin-bottom: 5px;
    }}
    </style>
""", unsafe_allow_html=True)

def render_logo(width=300, center=True):
    if os.path.exists("logo.png"):
        with open("logo.png", "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        
        align_css = "margin: 0 auto; display: block;" if center else "margin: 0;"
        container_align = "center" if center else "left"
        
        st.markdown(f"""
            <div style="text-align: {container_align}; padding: 10px 0;">
                <img src="data:image/png;base64,{encoded_string}" 
                     style="width: {width}px; max-width: 100%; height: auto; image-rendering: -webkit-optimize-contrast; {align_css}" />
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="font-family: 'Allura', cursive; font-size: 52px; color: {ROSE_PRIMARY}; margin-bottom: -15px;">
                    Dra. Rachel Leal
                </div>
                <div style="font-family: 'Comfortaa', sans-serif; font-size: 13px; letter-spacing: 4px; color: #8a7374; font-weight: 700;">
                    CIRURGIÃ-DENTISTA
                </div>
            </div>
        """, unsafe_allow_html=True)

# ==========================================
# 2. CONEXÃO COM GOOGLE SHEETS & GOOGLE DRIVE
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def read_data(worksheet_name, default_columns):
    try:
        # ttl=0 garante que a leitura seja SEMPRE em tempo real diretamente da planilha
        df = conn.read(worksheet=worksheet_name, ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=default_columns)
        for col in default_columns:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception as e:
        st.error(f"⚠️ Erro ao ler dados da aba '{worksheet_name}': {e}")
        return pd.DataFrame(columns=default_columns)

def write_data(worksheet_name, df):
    # TRAVA DE SEGURANÇA: NUNCA PERMITE SALVAR UMA TABELA VAZIA
    if df is None or df.empty:
        st.error(f"🛡️ TRAVA DE SEGURANÇA: Tentativa de salvar a tabela '{worksheet_name}' vazia foi bloqueada para proteger seus dados!")
        return
    try:
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear()  # Força a limpeza total de qualquer cache em memória
    except Exception as e:
        st.error(f"❌ Erro ao salvar na planilha '{worksheet_name}': {e}")

def get_drive_service():
    scopes = ['https://www.googleapis.com/auth/drive']
    credentials_info = st.secrets["connections"]["gsheets"]
    creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
    return build('drive', 'v3', credentials=creds)

def get_or_create_year_folder(service, parent_id, year_str):
    query = f"'{parent_id}' in parents and name = '{year_str}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    
    if files:
        return files[0]['id']
    else:
        folder_metadata = {
            'name': year_str,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        return folder.get('id')

def upload_nota_to_drive(uploaded_file, custom_filename, year_str):
    try:
        parent_folder_id = st.secrets.get("DRIVE_PARENT_FOLDER_ID", "")
        if not parent_folder_id:
            st.warning("⚠️ ID da pasta do Google Drive não foi configurado em secrets.toml.")
            return ""

        service = get_drive_service()
        year_folder_id = get_or_create_year_folder(service, parent_folder_id, year_str)
        
        media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype=uploaded_file.type, resumable=True)
        file_metadata = {
            'name': custom_filename,
            'parents': [year_folder_id]
        }
        
        file_drive = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return file_drive.get('webViewLink', '')
    except Exception as e:
        st.error(f"Erro no envio para o Google Drive: {e}")
        return ""

def sanitize_str(text):
    text_clean = re.sub(r'[^\w\s-]', '', str(text))
    return text_clean.strip().replace(' ', '_')

# ==========================================
# 3. AUTENTICAÇÃO SEGURA COM PERSISTÊNCIA DE SESSÃO
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

USER_DATABASE = {
    "vinicius.pereira": hash_password("vin%tr2019"),
    "rachel": hash_password("1lindinha2")
}

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# PERSISTÊNCIA DE LOGIN VIA URL
if not st.session_state.authenticated:
    if "user" in st.query_params and st.query_params["user"] in USER_DATABASE:
        st.session_state.authenticated = True
        st.session_state.current_user = st.query_params["user"]

def login_screen():
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.write("")
        render_logo(width=340, center=True)
        st.markdown("<h4 style='text-align: center; color: #777;'>Acesso ao Sistema</h4>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username_input = st.text_input("Usuário").strip().lower()
            password_input = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema", use_container_width=True)
            
            if submit:
                hashed_input = hash_password(password_input)
                if username_input in USER_DATABASE and USER_DATABASE[username_input] == hashed_input:
                    st.session_state.authenticated = True
                    st.session_state.current_user = username_input
                    st.query_params["user"] = username_input
                    st.success("Acesso liberado!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

if not st.session_state.authenticated:
    login_screen()
    st.stop()

# ==========================================
# 4. CABEÇALHO E CONFIGURAÇÕES DE BASE
# ==========================================
c_logo, c_user = st.columns([3, 1])
with c_logo:
    render_logo(width=280, center=False)
with c_user:
    st.write(f"👤 `{st.session_state.current_user}`")
    if st.button("Sair / Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.query_params.clear()
        st.rerun()

def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    return output.getvalue()

# CONFIGURAÇÕES PERMANENTES
CFG_COLS = ['Chave', 'Valor']
df_cfg = read_data("Configuracoes", CFG_COLS)

def get_cfg_val(chave, valor_padrao):
    if not df_cfg.empty and chave in df_cfg['Chave'].values:
        try:
            return float(df_cfg[df_cfg['Chave'] == chave]['Valor'].values[0])
        except Exception:
            return valor_padrao
    return valor_padrao

aluguel_consulta = get_cfg_val('aluguel_consulta', 60.0)
imposto_geral = get_cfg_val('imposto_geral', 6.0)
lucro_geral = get_cfg_val('lucro_geral', 40.0)
taxas_cartao = {i: get_cfg_val(f'taxa_{i}x', round(2.0 + (i * 0.8), 2)) for i in range(1, 13)}

# FUNÇÃO MATEMÁTICA DE RECÁLCULO COMPLETO DE PROCEDIMENTOS
def recalcular_procedimentos_df(df_p, df_m_ref, aluguel_cons, imposto_g, lucro_g, taxas_c):
    if df_p.empty:
        return df_p
        
    df_m_ativos = df_m_ref[df_m_ref['Status'] == 'Ativo'] if not df_m_ref.empty else pd.DataFrame()

    for idx in df_p.index:
        row = df_p.loc[idx]
        nome_p = str(row['Procedimento'])
        
        # 1. Custo Materiais
        custo_materiais_total = 0.0
        if not df_m_ativos.empty:
            for _, mat in df_m_ativos.iterrows():
                vincs = [x.strip() for x in str(mat['Procedimentos_Vinculados']).split(',')]
                if nome_p in vincs or "Geral" in vincs:
                    custo_materiais_total += float(mat['Custo_Por_Paciente'])

        # 2. Consultas e Aluguel
        try:
            qtd_consultas = int(row['Qtd_Consultas'])
        except Exception:
            qtd_consultas = 1
        if qtd_consultas < 1:
            qtd_consultas = 1

        custo_aluguel_total = qtd_consultas * aluguel_cons
        custo_base = custo_materiais_total + custo_aluguel_total

        # 3. Lucro (Percentual Geral, Percentual Específico ou Valor Fixo)
        tipo_lucro = str(row.get('Tipo_Lucro', 'Percentual Geral'))
        try:
            val_lucro_input = float(row.get('Lucro_Valor', 0.0))
        except Exception:
            val_lucro_input = 0.0

        if tipo_lucro == "Percentual Geral":
            valor_lucro = custo_base * (lucro_g / 100.0)
        elif tipo_lucro == "Percentual Específico":
            valor_lucro = custo_base * (val_lucro_input / 100.0)
        else:  # Valor Fixo
            valor_lucro = val_lucro_input

        # 4. Imposto e PIX
        subtotal = custo_base + valor_lucro
        valor_imposto = subtotal * (imposto_g / 100.0)
        total_pix = subtotal + valor_imposto

        # 5. Parcelamento e Cartão
        parc_str = str(row.get('Parcelas', '1x'))
        try:
            parcelas_sel = int(re.sub(r'\D', '', parc_str))
        except Exception:
            parcelas_sel = 1
        if parcelas_sel < 1: parcelas_sel = 1
        if parcelas_sel > 12: parcelas_sel = 12

        taxa_cartao_pct = taxas_c.get(parcelas_sel, 3.0)
        total_cartao = total_pix / (1 - (taxa_cartao_pct / 100.0)) if taxa_cartao_pct < 100 else total_pix
        custo_cartao = total_cartao - total_pix

        # Atualiza os valores calculados
        df_p.loc[idx, 'Custo_Materiais'] = round(custo_materiais_total, 2)
        df_p.loc[idx, 'Qtd_Consultas'] = qtd_consultas
        df_p.loc[idx, 'Custo_Aluguel'] = round(custo_aluguel_total, 2)
        df_p.loc[idx, 'Tipo_Lucro'] = tipo_lucro
        df_p.loc[idx, 'Lucro_Valor'] = round(val_lucro_input, 2)
        df_p.loc[idx, 'Imposto_Valor'] = round(valor_imposto, 2)
        df_p.loc[idx, 'Parcelas'] = f"{parcelas_sel}x"
        df_p.loc[idx, 'Taxa_Cartao_Pct'] = f"{taxa_cartao_pct}%"
        df_p.loc[idx, 'Custo_Cartao'] = round(custo_cartao, 2)
        df_p.loc[idx, 'Total_PIX'] = round(total_pix, 2)
        df_p.loc[idx, 'Total_Cartao'] = round(total_cartao, 2)

    return df_p

# DECLARAÇÃO DE TODAS AS ABAS
tab_resumo, tab_mat, tab_proc, tab_ag, tab_pac, tab_caixa, tab_cfg, tab_trash = st.tabs([
    "📊 1. Resumo", "📦 2. Materiais", "⚖️ 3. Precificação", "📅 4. Agenda & Prontuário",
    "👥 5. Pacientes", "💵 6. Livro Caixa", "⚙️ 7. Configurações", "🗑️ 8. Lixeira"
])

# COLS DE BANCO DE DADOS
MAT_COLS = ['ID', 'Material', 'Preco_Compra', 'Procedimentos_Vinculados', 'Rendimento_Pacientes', 'Custo_Por_Paciente', 'Status']
PROC_COLS = ['ID', 'Procedimento', 'Custo_Materiais', 'Qtd_Consultas', 'Custo_Aluguel', 'Tipo_Lucro', 'Lucro_Valor', 'Imposto_Valor', 'Parcelas', 'Taxa_Cartao_Pct', 'Custo_Cartao', 'Total_PIX', 'Total_Cartao', 'Status']
AG_COLS = ['ID', 'Data', 'Horario_Inicio', 'Duracao_Min', 'Horario_Fim', 'Paciente', 'Telefone', 'Email', 'Procedimento', 'Status_Atendimento', 'Anotacoes_Clinicas', 'Status']
PAC_COLS = ['ID', 'Paciente', 'Telefone', 'Email', 'Historico_Procedimentos', 'Ultima_Ida', 'Recorrencia', 'Status']
CAIXA_COLS = ['ID', 'Data', 'Tipo', 'Categoria', 'Descricao', 'Valor', 'Forma_Pagamento', 'Link_Nota', 'Status']

# ------------------------------------------
# TAB 1: RESUMO / DASHBOARD
# ------------------------------------------
with tab_resumo:
    st.subheader("📊 Painel de Resumo Mensal")
    df_ag = read_data("Agenda", AG_COLS)
    df_ag_active = df_ag[df_ag['Status'] == 'Ativo'] if not df_ag.empty else pd.DataFrame()

    c_m1, c_m2 = st.columns(2)
    mes_nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_resumo = c_m1.selectbox("Mês de Análise", options=range(1, 13), format_func=lambda x: mes_nomes[x-1], index=datetime.now().month - 1)
    ano_resumo = c_m2.number_input("Ano de Análise", min_value=2024, max_value=2030, value=datetime.now().year)

    df_mes = pd.DataFrame()
    total_pac_mes = 0
    total_concluidos = 0
    total_marcados = 0

    if not df_ag_active.empty:
        df_ag_active['dt_obj'] = pd.to_datetime(df_ag_active['Data'], format='%d/%m/%Y', errors='coerce')
        df_mes = df_ag_active[(df_ag_active['dt_obj'].dt.month == mes_resumo) & (df_ag_active['dt_obj'].dt.year == ano_resumo)]
        
        total_pac_mes = len(df_mes)
        total_concluidos = len(df_mes[df_mes['Status_Atendimento'] == 'Concluído'])
        total_marcados = len(df_mes[df_mes['Status_Atendimento'] != 'Concluído'])

    m1, m2, m3 = st.columns(3)
    m1.metric("👥 Total Pacientes no Mês", total_pac_mes)
    m2.metric("✅ Consultas Concluídas", total_concluidos)
    m3.metric("📅 Pacientes Marcados/Pendentes", total_marcados)

    st.markdown("---")
    st.write("### 📆 Distribuição Diária de Pacientes")
    
    if df_mes.empty:
        st.info("Nenhum agendamento registrado para este mês.")
    else:
        dias_mes = df_mes['Data'].unique()
        resumo_diario = []
        for d in sorted(dias_mes):
            sub = df_mes[df_mes['Data'] == d]
            conc = len(sub[sub['Status_Atendimento'] == 'Concluído'])
            marc = len(sub[sub['Status_Atendimento'] != 'Concluído'])
            resumo_diario.append({
                'Data': d,
                'Total Pacientes': len(sub),
                '🟢 Concluídos': conc,
                '🟠 Marcados': marc
            })
        st.dataframe(pd.DataFrame(resumo_diario), use_container_width=True)

    st.markdown("---")
    st.write("### 📋 Resumo da Agenda Recente / Próximos Atendimentos")
    if not df_ag_active.empty:
        st.dataframe(df_ag_active[['Data', 'Horario_Inicio', 'Paciente', 'Procedimento', 'Status_Atendimento']].tail(10), use_container_width=True)

# ------------------------------------------
# TAB 2: MATERIAIS
# ------------------------------------------
with tab_mat:
    st.subheader("📦 Cadastro e Custo de Materiais")
    df_mat = read_data("Materiais", MAT_COLS)
    df_proc_ref = read_data("Procedimentos", PROC_COLS)
    procs_validos = df_proc_ref[df_proc_ref['Status'] == 'Ativo']['Procedimento'].tolist() if not df_proc_ref.empty else []
    
    with st.expander("➕ Cadastrar Novo Material", expanded=False):
        with st.form("form_mat", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nome_m = c1.text_input("Nome do Material*")
            preco_c = c2.number_input("Preço de Compra (R$)*", min_value=0.01, step=10.0)
            procs_sel = c1.multiselect("Procedimentos em que é usado", options=procs_validos if procs_validos else ["Geral"])
            rendimento = c2.number_input("Rendimento (Pessoas atendidas)*", min_value=1, value=1)
            
            if st.form_submit_button("Salvar Material"):
                custo_p_paciente = preco_c / rendimento
                novo_id = len(df_mat) + 1
                novo_reg = {
                    'ID': novo_id, 'Material': nome_m, 'Preco_Compra': preco_c,
                    'Procedimentos_Vinculados': ", ".join(procs_sel),
                    'Rendimento_Pacientes': rendimento,
                    'Custo_Por_Paciente': round(custo_p_paciente, 2), 'Status': 'Ativo'
                }
                df_mat = pd.concat([df_mat, pd.DataFrame([novo_reg])], ignore_index=True)
                write_data("Materiais", df_mat)

                df_proc_ref = recalcular_procedimentos_df(df_proc_ref, df_mat, aluguel_consulta, imposto_geral, lucro_geral, taxas_cartao)
                write_data("Procedimentos", df_proc_ref)

                st.success("Material cadastrado e procedimentos recalculados!")
                st.rerun()

    st.markdown("---")
    df_mat_active = df_mat[df_mat['Status'] == 'Ativo'] if not df_mat.empty else pd.DataFrame()
    if not df_mat_active.empty:
        col_f, col_d = st.columns([3, 1])
        busca_m = col_f.text_input("🔍 Filtrar Materiais:", placeholder="Digite o nome do material...")
        df_display = df_mat_active[df_mat_active['Material'].str.contains(busca_m, case=False, na=False)] if busca_m else df_mat_active
        col_d.download_button("📊 Baixar Excel", data=export_to_excel(df_display), file_name="materiais.xlsx", use_container_width=True)

        edited_mat = st.data_editor(df_display.drop(columns=['Status'], errors='ignore'), use_container_width=True, key="editor_mat")
        if st.button("💾 Salvar Alterações na Planilha (Materiais)"):
            for idx, row in edited_mat.iterrows():
                mat_id = str(row['ID']).strip()
                mask = df_mat['ID'].astype(str).str.strip() == mat_id
                df_mat.loc[mask, ['Material', 'Preco_Compra', 'Procedimentos_Vinculados', 'Rendimento_Pacientes', 'Custo_Por_Paciente']] = [
                    row['Material'], row['Preco_Compra'], row['Procedimentos_Vinculados'], row['Rendimento_Pacientes'], row['Custo_Por_Paciente']
                ]
            write_data("Materiais", df_mat)
            
            df_proc_ref = recalcular_procedimentos_df(df_proc_ref, df_mat, aluguel_consulta, imposto_geral, lucro_geral, taxas_cartao)
            write_data("Procedimentos", df_proc_ref)

            st.success("Alterações salvas e procedimentos recalculados!")
            st.rerun()

        st.markdown("---")
        c_del1, c_del2 = st.columns([3, 1])
        mat_del = c_del1.selectbox("Remover Material:", options=df_mat_active['Material'].tolist(), key="sel_del_mat")
        if c_del2.button("🗑️ Mover Material para Lixeira"):
            mask = df_mat['Material'].astype(str).str.strip() == str(mat_del).strip()
            df_mat.loc[mask, 'Status'] = 'Excluido'
            write_data("Materiais", df_mat)
            st.warning("Material movido para a lixeira!")
            st.rerun()

# ------------------------------------------
# TAB 3: PROCEDIMENTOS & PRECIFICAÇÃO
# ------------------------------------------
with tab_proc:
    st.subheader("⚖️ Cálculo e Precificação de Procedimentos")
    df_proc = read_data("Procedimentos", PROC_COLS)
    df_mat_ref = read_data("Materiais", MAT_COLS)
    
    with st.expander("➕ Precificar Novo Procedimento", expanded=False):
        with st.form("form_proc"):
            c1, c2, c3 = st.columns(3)
            nome_p = c1.text_input("Nome do Procedimento*")
            qtd_consultas = c2.number_input("Qtd. de Consultas/Idas*", min_value=1, value=1)
            tipo_lucro = c3.selectbox("Tipo de Lucro", ["Percentual Geral", "Percentual Específico", "Valor Fixo"])
            
            val_lucro_input = 0.0
            if tipo_lucro == "Percentual Específico":
                val_lucro_input = c3.number_input("Lucro Específico (%)", min_value=0.0, value=30.0)
            elif tipo_lucro == "Valor Fixo":
                val_lucro_input = c3.number_input("Lucro Fixo (R$)", min_value=0.0, value=150.0)
                
            imposto_pct = c1.number_input("Imposto (%)", value=imposto_geral)
            parcelas_sel = c2.selectbox("Parcelamento Cartão", options=list(range(1, 13)), format_func=lambda x: f"{x}x")
            
            if st.form_submit_button("Calcular e Salvar Procedimento"):
                novo_id = len(df_proc) + 1
                novo_p = {
                    'ID': novo_id, 'Procedimento': nome_p, 'Custo_Materiais': 0.0,
                    'Qtd_Consultas': qtd_consultas, 'Custo_Aluguel': 0.0,
                    'Tipo_Lucro': tipo_lucro, 'Lucro_Valor': round(val_lucro_input, 2),
                    'Imposto_Valor': 0.0, 'Parcelas': f"{parcelas_sel}x",
                    'Taxa_Cartao_Pct': '0%', 'Custo_Cartao': 0.0,
                    'Total_PIX': 0.0, 'Total_Cartao': 0.0, 'Status': 'Ativo'
                }
                df_proc = pd.concat([df_proc, pd.DataFrame([novo_p])], ignore_index=True)
                df_proc = recalcular_procedimentos_df(df_proc, df_mat_ref, aluguel_consulta, imposto_geral, lucro_geral, taxas_cartao)
                write_data("Procedimentos", df_proc)
                st.success("Procedimento cadastrado e calculado!")
                st.rerun()

    st.markdown("---")
    df_proc_active = df_proc[df_proc['Status'] == 'Ativo'] if not df_proc.empty else pd.DataFrame()
    if not df_proc_active.empty:
        col_fp, col_dp = st.columns([3, 1])
        busca_p = col_fp.text_input("🔍 Filtrar Procedimentos:", placeholder="Digite o nome do procedimento...")
        df_p_disp = df_proc_active[df_proc_active['Procedimento'].str.contains(busca_p, case=False, na=False)] if busca_p else df_proc_active
        col_dp.download_button("📊 Baixar Excel", data=export_to_excel(df_p_disp), file_name="procedimentos.xlsx", use_container_width=True)

        edited_proc = st.data_editor(
            df_p_disp.drop(columns=['Status'], errors='ignore'),
            column_config={
                "Tipo_Lucro": st.column_config.SelectboxColumn(
                    "Tipo de Lucro",
                    options=["Percentual Geral", "Percentual Específico", "Valor Fixo"],
                    required=True
                ),
                "Lucro_Valor": st.column_config.NumberColumn(
                    "Lucro (Valor em R$ ou %)",
                    help="Se Percentual Específico coloque a %. Se Valor Fixo coloque o R$."
                )
            },
            use_container_width=True,
            key="editor_proc"
        )

        if st.button("💾 Salvar Alterações e Recalcular Preços"):
            for idx, row in edited_proc.iterrows():
                p_id = str(row['ID']).strip()
                mask = df_proc['ID'].astype(str).str.strip() == p_id
                df_proc.loc[mask, 'Procedimento'] = row['Procedimento']
                df_proc.loc[mask, 'Qtd_Consultas'] = row['Qtd_Consultas']
                df_proc.loc[mask, 'Tipo_Lucro'] = row['Tipo_Lucro']
                df_proc.loc[mask, 'Lucro_Valor'] = row['Lucro_Valor']
                df_proc.loc[mask, 'Parcelas'] = row['Parcelas']

            df_proc = recalcular_procedimentos_df(df_proc, df_mat_ref, aluguel_consulta, imposto_geral, lucro_geral, taxas_cartao)
            write_data("Procedimentos", df_proc)
            st.success("Alterações salvas e precificação recalculada com sucesso!")
            st.rerun()

        st.markdown("---")
        cp_del1, cp_del2 = st.columns([3, 1])
        proc_del = cp_del1.selectbox("Remover Procedimento:", options=df_proc_active['Procedimento'].tolist(), key="sel_del_proc")
        if cp_del2.button("🗑️ Mover Procedimento para Lixeira"):
            mask = df_proc['Procedimento'].astype(str).str.strip() == str(proc_del).strip()
            df_proc.loc[mask, 'Status'] = 'Excluido'
            write_data("Procedimentos", df_proc)
            st.warning("Procedimento movido para a lixeira!")
            st.rerun()

# ------------------------------------------
# TAB 4: AGENDA & PRONTUÁRIO
# ------------------------------------------
def salvar_agendamento(novo_reg, df_ag, df_pac):
    df_ag = pd.concat([df_ag, pd.DataFrame([novo_reg])], ignore_index=True)
    write_data("Agenda", df_ag)

    data_str = novo_reg['Data']
    nome_pac = novo_reg['Paciente']
    proc_ag = novo_reg['Procedimento']
    tel_pac = novo_reg['Telefone']
    email_pac = novo_reg['Email']

    novo_item_hist = f"[{data_str}] {proc_ag} (Agendado)"
    if not df_pac.empty and nome_pac in df_pac['Paciente'].values:
        idx = df_pac[df_pac['Paciente'] == nome_pac].index[0]
        hist_atual = str(df_pac.loc[idx, 'Historico_Procedimentos'])
        df_pac.loc[idx, 'Historico_Procedimentos'] = hist_atual + " | " + novo_item_hist
        df_pac.loc[idx, 'Ultima_Ida'] = data_str
        try:
            df_pac.loc[idx, 'Recorrencia'] = int(df_pac.loc[idx, 'Recorrencia']) + 1
        except Exception:
            df_pac.loc[idx, 'Recorrencia'] = 1
    else:
        reg_pac = {
            'ID': len(df_pac) + 1, 'Paciente': nome_pac, 'Telefone': tel_pac,
            'Email': email_pac, 'Historico_Procedimentos': novo_item_hist,
            'Ultima_Ida': data_str, 'Recorrencia': 1, 'Status': 'Ativo'
        }
        df_pac = pd.concat([df_pac, pd.DataFrame([reg_pac])], ignore_index=True)

    write_data("Pacientes", df_pac)

with tab_ag:
    st.subheader("📅 Agenda & Prontuário Clínico")
    df_ag = read_data("Agenda", AG_COLS)
    df_pac = read_data("Pacientes", PAC_COLS)
    df_proc_ref = read_data("Procedimentos", PROC_COLS)
    procs_disponiveis = df_proc_ref[df_proc_ref['Status'] == 'Ativo']['Procedimento'].tolist() if not df_proc_ref.empty else ["Consulta Geral"]

    if 'agenda_date' not in st.session_state:
        st.session_state.agenda_date = datetime.now().date()
    if 'conflito_pendente' not in st.session_state:
        st.session_state.conflito_pendente = None

    col_ag_form, col_ag_cal = st.columns([1.1, 1.9])

    with col_ag_form:
        st.write("### ➕ Agendar Consulta")
        with st.form("form_novo_agendamento"):
            dt_c = st.date_input("Data da Consulta*", value=st.session_state.agenda_date)
            c_h1, c_h2 = st.columns(2)
            hr_inicio = c_h1.time_input("Horário de Início*", value=time(9, 0))
            duracao = c_h2.number_input("Duração (minutos)*", min_value=10, max_value=480, value=60, step=10)
            
            dt_dummy = datetime.combine(datetime.today(), hr_inicio)
            dt_fim = dt_dummy + timedelta(minutes=duracao)
            hr_fim = dt_fim.time()
            
            st.caption(f"⏱️ Horário Estimado: **{hr_inicio.strftime('%H:%M')}** até **{hr_fim.strftime('%H:%M')}**")
            
            nome_pac = st.text_input("Nome do Paciente*")
            tel_pac = st.text_input("Telefone")
            email_pac = st.text_input("E-mail")
            proc_ag = st.selectbox("Procedimento*", options=procs_disponiveis)
            
            btn_sub = st.form_submit_button("Verificar & Agendar", use_container_width=True)

            if btn_sub:
                if not nome_pac:
                    st.error("Por favor, preencha o nome do paciente.")
                else:
                    data_str = dt_c.strftime("%d/%m/%Y")
                    str_inc = hr_inicio.strftime("%H:%M")
                    str_fim = hr_fim.strftime("%H:%M")
                    
                    df_ag_active = df_ag[df_ag['Status'] == 'Ativo'] if not df_ag.empty else pd.DataFrame()
                    choques = []

                    if not df_ag_active.empty:
                        df_dia_check = df_ag_active[df_ag_active['Data'] == data_str]
                        for _, item in df_dia_check.iterrows():
                            try:
                                ex_inc = datetime.strptime(str(item['Horario_Inicio']), "%H:%M").time()
                            except Exception:
                                ex_inc = time(9, 0)
                            try:
                                ex_dur = int(item['Duracao_Min'])
                            except Exception:
                                ex_dur = 60
                            
                            ex_dt_inc = datetime.combine(dt_c, ex_inc)
                            ex_dt_fim = ex_dt_inc + timedelta(minutes=ex_dur)
                            ex_fim = ex_dt_fim.time()

                            new_dt_inc = datetime.combine(dt_c, hr_inicio)
                            new_dt_fim = datetime.combine(dt_c, hr_fim)

                            if new_dt_inc < ex_dt_fim and new_dt_fim > ex_dt_inc:
                                choques.append({
                                    'paciente': item['Paciente'],
                                    'procedimento': item['Procedimento'],
                                    'inicio': ex_inc.strftime("%H:%M"),
                                    'fim': ex_fim.strftime("%H:%M")
                                })

                    novo_reg = {
                        'ID': len(df_ag) + 1, 'Data': data_str,
                        'Horario_Inicio': str_inc, 'Duracao_Min': duracao,
                        'Horario_Fim': str_fim, 'Paciente': nome_pac,
                        'Telefone': tel_pac, 'Email': email_pac,
                        'Procedimento': proc_ag, 'Status_Atendimento': 'Marcado',
                        'Anotacoes_Clinicas': '', 'Status': 'Ativo'
                    }

                    if choques:
                        st.session_state.conflito_pendente = {
                            'novo_reg': novo_reg,
                            'choques': choques
                        }
                    else:
                        salvar_agendamento(novo_reg, df_ag, df_pac)
                        st.session_state.agenda_date = dt_c
                        st.success("Agendado com sucesso!")
                        st.rerun()

        if st.session_state.conflito_pendente:
            conf = st.session_state.conflito_pendente
            st.error("⚠️ **AVISO DE CHOQUE DE HORÁRIO!**")
            for ch in conf['choques']:
                st.warning(f"O(A) paciente **{ch['paciente']}** já está marcado(a) para **{ch['procedimento']}** das **{ch['inicio']}** às **{ch['fim']}**.")
            
            c_b1, c_b2, c_b3 = st.columns(3)
            if c_b1.button("❌ Cancelar"):
                st.session_state.conflito_pendente = None
                st.rerun()
            if c_b2.button("✏️ Ajustar"):
                st.session_state.conflito_pendente = None
            if c_b3.button("⚠️ Marcar mesmo assim"):
                salvar_agendamento(conf['novo_reg'], df_ag, df_pac)
                st.session_state.conflito_pendente = None
                st.success("Agendado!")
                st.rerun()

    with col_ag_cal:
        st.write("### 📆 Calendário do Mês")
        c_m1, c_m2 = st.columns(2)
        mes_sel = c_m1.selectbox("Mês", options=range(1, 13), format_func=lambda x: mes_nomes[x-1], index=st.session_state.agenda_date.month - 1, key="ag_m")
        ano_sel = c_m2.number_input("Ano", min_value=2024, max_value=2030, value=st.session_state.agenda_date.year, key="ag_a")

        df_ag_active = df_ag[df_ag['Status'] == 'Ativo'] if not df_ag.empty else pd.DataFrame()
        contagem_dias = {}

        if not df_ag_active.empty:
            for _, row in df_ag_active.iterrows():
                try:
                    dt_obj = datetime.strptime(str(row['Data']), "%d/%m/%Y").date()
                    if dt_obj.month == mes_sel and dt_obj.year == ano_sel:
                        contagem_dias[dt_obj.day] = contagem_dias.get(dt_obj.day, 0) + 1
                except Exception:
                    pass

        cal = calendar.monthcalendar(ano_sel, mes_sel)
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        
        cols_hdr = st.columns(7)
        for idx, d_nome in enumerate(dias_semana):
            cols_hdr[idx].markdown(f"<div class='cal-header'>{d_nome}</div>", unsafe_allow_html=True)

        for semana in cal:
            cols_dia = st.columns(7)
            for idx, dia in enumerate(semana):
                if dia == 0:
                    cols_dia[idx].write("")
                else:
                    n_pacientes = contagem_dias.get(dia, 0)
                    badge = f"({n_pacientes} pac)" if n_pacientes > 0 else "•"
                    dt_btn = datetime(ano_sel, mes_sel, dia).date()
                    is_selected = (dt_btn == st.session_state.agenda_date)
                    label_btn = f"{'📍' if is_selected else ''}{dia}\n{badge}"
                    
                    if cols_dia[idx].button(label_btn, key=f"cal_btn_{ano_sel}_{mes_sel}_{dia}", use_container_width=True):
                        st.session_state.agenda_date = dt_btn
                        st.rerun()

        st.markdown("---")
        data_sel_str = st.session_state.agenda_date.strftime("%d/%m/%Y")
        st.write(f"### 📋 Atendimentos para **{data_sel_str}**")

        df_dia = df_ag_active[df_ag_active['Data'] == data_sel_str] if not df_ag_active.empty else pd.DataFrame()

        if df_dia.empty:
            st.info(f"Nenhum paciente agendado para {data_sel_str}.")
        else:
            for idx_row, ag_item in df_dia.iterrows():
                inc = ag_item.get('Horario_Inicio', '09:00')
                fim = ag_item.get('Horario_Fim', '10:00')
                st_atend = ag_item.get('Status_Atendimento', 'Marcado')
                color_tag = "green" if st_atend == "Concluído" else ROSE_PRIMARY

                st.markdown(f"""
                    <div class="agenda-card" style="border-left-color: {color_tag};">
                        <strong style="color: {color_tag}; font-size: 16px;">⏰ {inc} às {fim} - {ag_item['Paciente']} [{st_atend}]</strong><br/>
                        <b>Procedimento:</b> {ag_item['Procedimento']} | <b>Telefone:</b> {ag_item.get('Telefone', 'N/A')}
                    </div>
                """, unsafe_allow_html=True)

                with st.expander(f"📝 Atender / Prontuário de {ag_item['Paciente']}"):
                    anot_atual = str(ag_item.get('Anotacoes_Clinicas', ''))
                    if anot_atual == 'nan':
                        anot_atual = ""
                    
                    nova_anot = st.text_area("Evolução / Observações:", value=anot_atual, key=f"anot_{ag_item['ID']}")
                    c_status, c_save = st.columns([1, 1])
                    novo_status_atend = c_status.selectbox("Status:", ["Marcado", "Concluído", "Cancelado"], index=1 if st_atend == "Concluído" else 0, key=f"st_{ag_item['ID']}")
                    
                    if c_save.button("💾 Salvar Prontuário", key=f"btn_save_pront_{ag_item['ID']}"):
                        ag_id = str(ag_item['ID']).strip()
                        mask_ag = df_ag['ID'].astype(str).str.strip() == ag_id
                        df_ag.loc[mask_ag, 'Anotacoes_Clinicas'] = nova_anot
                        df_ag.loc[mask_ag, 'Status_Atendimento'] = novo_status_atend
                        write_data("Agenda", df_ag)

                        p_nome = ag_item['Paciente']
                        if not df_pac.empty and p_nome in df_pac['Paciente'].values:
                            p_idx = df_pac[df_pac['Paciente'] == p_nome].index[0]
                            hist_antigo = str(df_pac.loc[p_idx, 'Historico_Procedimentos'])
                            registro_prontuario = f"[{data_sel_str}] {ag_item['Procedimento']}: {nova_anot}"
                            
                            if registro_prontuario not in hist_antigo:
                                df_pac.loc[p_idx, 'Historico_Procedimentos'] = hist_antigo + " | " + registro_prontuario
                                write_data("Pacientes", df_pac)

                        st.success("Prontuário salvo!")
                        st.rerun()

# ------------------------------------------
# TAB 5: PACIENTES & PRONTUÁRIO COMPLETO
# ------------------------------------------
with tab_pac:
    st.subheader("👥 Base de Pacientes e Histórico Clínico")
    df_pac = read_data("Pacientes", PAC_COLS)
    df_pac_active = df_pac[df_pac['Status'] == 'Ativo'] if not df_pac.empty else pd.DataFrame()

    if df_pac_active.empty:
        st.info("Nenhum paciente cadastrado.")
    else:
        col_fpac, col_dpac = st.columns([3, 1])
        busca_pac = col_fpac.text_input("🔍 Buscar Paciente:", placeholder="Digite o nome do paciente...")
        df_p_show = df_pac_active[df_pac_active['Paciente'].str.contains(busca_pac, case=False, na=False)] if busca_pac else df_pac_active
        col_dpac.download_button("📊 Baixar Excel", data=export_to_excel(df_p_show), file_name="pacientes.xlsx", use_container_width=True)

        st.dataframe(df_p_show[['Paciente', 'Telefone', 'Email', 'Ultima_Ida', 'Recorrencia']], use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Prontuário / Histórico Completo do Paciente")
        pac_sel = st.selectbox("Selecione o Paciente para visualizar todas as consultas:", options=df_pac_active['Paciente'].tolist())
        
        if pac_sel:
            row_p = df_pac_active[df_pac_active['Paciente'] == pac_sel].iloc[0]
            st.write(f"**Paciente:** {row_p['Paciente']} | **Telefone:** {row_p.get('Telefone', 'N/A')} | **Última Ida:** {row_p.get('Ultima_Ida', 'N/A')}")
            
            st.write("#### Linha do Tempo de Atendimentos:")
            historico_raw = str(row_p['Historico_Procedimentos']).split(" | ")
            for item in historico_raw:
                if item and item != 'nan':
                    st.info(f"📌 {item}")

# ------------------------------------------
# TAB 6: LIVRO CAIXA (FLUXO FINANCEIRO & COMPROVANTES)
# ------------------------------------------
with tab_caixa:
    st.subheader("💵 Livro Caixa (Comprovantes & Fluxo Financeiro)")
    df_caixa = read_data("LivroCaixa", CAIXA_COLS)
    
    with st.expander("➕ Lançar Nova Entrada / Saída com Comprovante", expanded=False):
        with st.form("form_caixa", clear_on_submit=True):
            c_cx1, c_cx2, c_cx3 = st.columns(3)
            dt_trans = c_cx1.date_input("Data*", value=datetime.now())
            tipo_trans = c_cx2.selectbox("Tipo*", ["Entrada", "Saida"])
            categoria = c_cx3.selectbox("Categoria*", [
                "Atendimento-Consulta", "Procedimento-Estetico", "Compra-de-Materiais",
                "Aluguel-Custos-Fixos", "Impostos", "Marketing", "Outros"
            ])
            
            c_cx4, c_cx5, c_cx6 = st.columns(3)
            desc_trans = c_cx4.text_input("Descrição*", placeholder="Ex: Paciente Maria PIX")
            val_trans = c_cx5.number_input("Valor (R$)*", min_value=0.01, step=50.0)
            forma_pag = c_cx6.selectbox("Forma de Pagamento", ["PIX", "Cartao-Credito", "Cartao-Debito", "Dinheiro", "Transferencia"])

            st.markdown("---")
            file_anexo = st.file_uploader("📎 Anexar Nota / Comprovante (PDF, PNG, JPG)", type=["pdf", "png", "jpg", "jpeg"])

            if st.form_submit_button("💾 Gravar Lançamento no Caixa"):
                link_drive = ""
                
                if file_anexo is not None:
                    data_formatada = dt_trans.strftime("%d_%m_%Y")
                    ano_str = str(dt_trans.year)
                    ext = file_anexo.name.split('.')[-1]
                    
                    nome_arquivo = f"{data_formatada}_{tipo_trans}_{sanitize_str(categoria)}_{sanitize_str(forma_pag)}.{ext}"
                    
                    with st.spinner("Enviando comprovante para o Google Drive..."):
                        link_drive = upload_nota_to_drive(file_anexo, nome_arquivo, ano_str)

                novo_lc = {
                    'ID': len(df_caixa) + 1,
                    'Data': dt_trans.strftime("%d/%m/%Y"),
                    'Tipo': tipo_trans,
                    'Categoria': categoria,
                    'Descricao': desc_trans,
                    'Valor': round(val_trans, 2),
                    'Forma_Pagamento': forma_pag,
                    'Link_Nota': link_drive,
                    'Status': 'Ativo'
                }
                df_caixa = pd.concat([df_caixa, pd.DataFrame([novo_lc])], ignore_index=True)
                write_data("LivroCaixa", df_caixa)
                st.success("Lançamento salvo com nota organizada no Drive!")
                st.rerun()

    st.markdown("---")
    df_cx_active = df_caixa[df_caixa['Status'] == 'Ativo'] if not df_caixa.empty else pd.DataFrame()

    if not df_cx_active.empty:
        entradas = df_cx_active[df_cx_active['Tipo'] == 'Entrada']['Valor'].astype(float).sum()
        saidas = df_cx_active[df_cx_active['Tipo'] == 'Saida']['Valor'].astype(float).sum()
        saldo = entradas - saidas

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("🟢 Total Entradas", f"R$ {entradas:,.2f}")
        mc2.metric("🔴 Total Saídas", f"R$ {saidas:,.2f}")
        mc3.metric("⚖️ Saldo do Período", f"R$ {saldo:,.2f}")

        st.markdown("---")
        st.write("### 📋 Extrato de Lançamentos")
        st.dataframe(
            df_cx_active.drop(columns=['Status'], errors='ignore'),
            column_config={
                "Link_Nota": st.column_config.LinkColumn(
                    "Nota Anexada",
                    help="Clique para ver o arquivo no Google Drive",
                    validate="^https://",
                    display_text="📄 Ver Nota no Drive"
                )
            },
            use_container_width=True
        )

# ------------------------------------------
# TAB 7: CONFIGURAÇÕES & TAXAS
# ------------------------------------------
with tab_cfg:
    st.subheader("⚙️ Configurações do Consultório & Taxas de Cartão")
    st.caption("Altere os parâmetros abaixo. Eles são aplicados automaticamente em toda a precificação.")

    with st.form("form_config"):
        st.write("### 1. Custos Fixos & Margens da Clínica")
        c_c1, c_c2 = st.columns(2)
        novo_aluguel = c_c1.number_input("Custo de Aluguel por Consulta (R$)", value=aluguel_consulta, step=5.0)
        novo_imposto = c_c2.number_input("Imposto Geral Padrão (%)", value=imposto_geral, step=0.5)
        novo_lucro = c_c1.number_input("Margem de Lucro Geral (%)", value=lucro_geral, step=1.0)

        st.markdown("---")
        st.write("### 2. Taxas da Maquininha de Cartão (1x até 12x)")
        
        novas_taxas = {}
        cols_tx = st.columns(4)
        for i in range(1, 13):
            col_idx = (i - 1) % 4
            novas_taxas[i] = cols_tx[col_idx].number_input(f"Taxa {i}x (%)", value=taxas_cartao[i], step=0.1)

        if st.form_submit_button("💾 Salvar Parâmetros no Banco de Dados"):
            novas_configs = [
                {'Chave': 'aluguel_consulta', 'Valor': novo_aluguel},
                {'Chave': 'imposto_geral', 'Valor': novo_imposto},
                {'Chave': 'lucro_geral', 'Valor': novo_lucro}
            ]
            for i in range(1, 13):
                novas_configs.append({'Chave': f'taxa_{i}x', 'Valor': novas_taxas[i]})

            write_data("Configuracoes", pd.DataFrame(novas_configs))
            
            df_proc_ref = read_data("Procedimentos", PROC_COLS)
            df_mat_ref = read_data("Materiais", MAT_COLS)
            df_proc_ref = recalcular_procedimentos_df(df_proc_ref, df_mat_ref, novo_aluguel, novo_imposto, novo_lucro, novas_taxas)
            write_data("Procedimentos", df_proc_ref)

            st.success("Configurações salvas e precificações atualizadas!")
            st.rerun()

# ------------------------------------------
# TAB 8: LIXEIRA / SEGURANÇA
# ------------------------------------------
with tab_trash:
    st.subheader("🗑️ Lixeira do Sistema & Restauração")
    cat_del = st.selectbox("Categoria para restaurar:", ["Materiais", "Procedimentos", "Agenda", "Pacientes", "LivroCaixa"])

    if cat_del == "Materiais":
        df_t = read_data("Materiais", MAT_COLS)
        k_col = "Material"
    elif cat_del == "Procedimentos":
        df_t = read_data("Procedimentos", PROC_COLS)
        k_col = "Procedimento"
    elif cat_del == "Agenda":
        df_t = read_data("Agenda", AG_COLS)
        k_col = "Paciente"
    elif cat_del == "LivroCaixa":
        df_t = read_data("LivroCaixa", CAIXA_COLS)
        k_col = "Descricao"
    else:
        df_t = read_data("Pacientes", PAC_COLS)
        k_col = "Paciente"

    if not df_t.empty:
        df_ex = df_t[df_t['Status'] == 'Excluido']
        if df_ex.empty:
            st.info(f"Nenhum item na lixeira de {cat_del}.")
        else:
            st.dataframe(df_ex, use_container_width=True)
            res_item = st.selectbox(f"Restaurar de {cat_del}:", options=df_ex[k_col].tolist())
            if st.button("🔄 Restaurar Item"):
                mask_t = df_t[k_col].astype(str).str.strip() == str(res_item).strip()
                df_t.loc[mask_t, 'Status'] = 'Ativo'
                write_data(cat_del, df_t)
                st.success("Item restaurado!")
                st.rerun()
