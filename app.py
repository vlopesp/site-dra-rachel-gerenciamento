import streamlit as st
import pandas as pd
import hashlib
import io
import os
from datetime import datetime
from difflib import SequenceMatcher
from streamlit_gsheets import GSheetsConnection

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

# Injeção de CSS para garantir visibilidade no Tema Escuro e aplicar a identidade da marca
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Allura&family=Comfortaa:wght@400;600;700&display=swap');

    /* Força fundo claro e texto legível em qualquer tema */
    .stApp {{
        background-color: #fdfbfb !important;
        color: {DARK_TEXT} !important;
    }}
    
    /* Corrige textos que somem no tema escuro */
    p, span, label, h1, h2, h3, h4, h5, h6, div, td, th {{
        color: {DARK_TEXT} !important;
        font-family: 'Comfortaa', cursive, sans-serif;
    }}

    /* Inputs e Seletores */
    .stTextInput input, .stNumberInput input, .stSelectbox div, .stDateInput input, .stTimeInput input {{
        background-color: #ffffff !important;
        color: {DARK_TEXT} !important;
        border: 1px solid {ROSE_PRIMARY} !important;
        border-radius: 6px !important;
    }}
    
    /* Botões estilizados em Rosé */
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
    
    /* Abas estilizadas */
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

    /* Cards da Agenda */
    .agenda-card {{
        background-color: #ffffff;
        border-left: 5px solid {ROSE_PRIMARY};
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}
    </style>
""", unsafe_allow_html=True)

# Function para exibir o Logo da Dra. Rachel
def render_logo():
    if os.path.exists("logo.png"):
        st.image("logo.png", width=240)
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
# 2. CONEXÃO COM O GOOGLE SHEETS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def read_data(worksheet_name, default_columns):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=2)
        if df is None or df.empty:
            return pd.DataFrame(columns=default_columns)
        return df
    except Exception:
        return pd.DataFrame(columns=default_columns)

def write_data(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

# ==========================================
# 3. AUTENTICAÇÃO SEGURA (HASH SHA-256)
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

def login_screen():
    col1, col2, col3 = st.columns([1, 1.8, 1])
    with col2:
        st.write("")
        render_logo()
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
                    st.success("Acesso liberado!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

if not st.session_state.authenticated:
    login_screen()
    st.stop()

# ==========================================
# 4. CABEÇALHO DO PAINEL PRINCIPAL
# ==========================================
c_logo, c_user = st.columns([4, 1])
with c_logo:
    render_logo()
with c_user:
    st.write(f"👤 `{st.session_state.current_user}`")
    if st.button("Sair / Logout"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()

def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    return output.getvalue()

def similarity(a, b):
    return SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()

# CARREGAR CONFIGURAÇÕES PERMANENTES
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
taxas_cartao = {
    1: get_cfg_val('taxa_1x', 2.5),
    2: get_cfg_val('taxa_2x', 4.0),
    3: get_cfg_val('taxa_3x', 5.5),
    6: get_cfg_val('taxa_6x', 8.0),
    12: get_cfg_val('taxa_12x', 12.0)
}

# ABAS DO PROGRAMA
tab_mat, tab_proc, tab_ag, tab_pac, tab_cfg, tab_trash = st.tabs([
    "📦 1. Materiais", "⚖️ 2. Precificação", "📅 3. Agenda (Calendário)",
    "👥 4. Pacientes", "⚙️ 5. Configurações & Taxas", "🗑️ 6. Lixeira / Segurança"
])

# ------------------------------------------
# TAB 1: MATERIAIS
# ------------------------------------------
MAT_COLS = ['ID', 'Material', 'Preco_Compra', 'Procedimentos_Vinculados', 'Rendimento_Pacientes', 'Custo_Por_Paciente', 'Status']

with tab_mat:
    st.subheader("Cadastro e Custo de Materiais")
    df_mat = read_data("Materiais", MAT_COLS)
    df_proc_ref = read_data("Procedimentos", ['Procedimento', 'Status'])
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
                    'ID': novo_id,
                    'Material': nome_m,
                    'Preco_Compra': preco_c,
                    'Procedimentos_Vinculados': ", ".join(procs_sel),
                    'Rendimento_Pacientes': rendimento,
                    'Custo_Por_Paciente': round(custo_p_paciente, 2),
                    'Status': 'Ativo'
                }
                df_mat = pd.concat([df_mat, pd.DataFrame([novo_reg])], ignore_index=True)
                write_data("Materiais", df_mat)
                st.success("Material cadastrado!")
                st.rerun()

    st.markdown("---")
    df_mat_active = df_mat[df_mat['Status'] == 'Ativo'] if not df_mat.empty else df_mat
    
    if not df_mat_active.empty:
        col_f, col_d = st.columns([3, 1])
        busca_m = col_f.text_input("🔍 Filtrar Materiais:", placeholder="Digite o nome do material...")
        
        if busca_m:
            df_display = df_mat_active[df_mat_active['Material'].str.contains(busca_m, case=False, na=False)]
        else:
            df_display = df_mat_active

        col_d.download_button("📊 Baixar Excel", data=export_to_excel(df_display), file_name="materiais.xlsx", use_container_width=True)

        st.info("💡 Você pode editar as células diretamente abaixo e clicar em **Salvar Alterações**.")
        edited_mat = st.data_editor(df_display.drop(columns=['Status'], errors='ignore'), use_container_width=True, key="editor_mat")

        if st.button("💾 Salvar Alterações na Planilha (Materiais)"):
            for idx, row in edited_mat.iterrows():
                mat_id = row['ID']
                df_mat.loc[df_mat['ID'] == mat_id, ['Material', 'Preco_Compra', 'Procedimentos_Vinculados', 'Rendimento_Pacientes', 'Custo_Por_Paciente']] = [
                    row['Material'], row['Preco_Compra'], row['Procedimentos_Vinculados'], row['Rendimento_Pacientes'], row['Custo_Por_Paciente']
                ]
            write_data("Materiais", df_mat)
            st.success("Alterações salvas no Google Sheets!")
            st.rerun()

        st.markdown("---")
        c_del1, c_del2 = st.columns([3, 1])
        mat_del = c_del1.selectbox("Remover Material:", options=df_mat_active['Material'].tolist())
        if c_del2.button("🗑️ Mover para Lixeira"):
            df_mat.loc[df_mat['Material'] == mat_del, 'Status'] = 'Excluido'
            write_data("Materiais", df_mat)
            st.warning("Material movido para a lixeira!")
            st.rerun()

# ------------------------------------------
# TAB 2: PROCEDIMENTOS & PRECIFICAÇÃO
# ------------------------------------------
PROC_COLS = [
    'ID', 'Procedimento', 'Custo_Materiais', 'Qtd_Consultas', 'Custo_Aluguel',
    'Tipo_Lucro', 'Lucro_Valor', 'Imposto_Valor', 'Parcelas', 'Taxa_Cartao_Pct',
    'Custo_Cartao', 'Total_PIX', 'Total_Cartao', 'Status'
]

with tab_proc:
    st.subheader("Cálculo e Precificação de Procedimentos")
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
            parcelas_sel = c2.selectbox("Parcelamento Cartão", options=[1, 2, 3, 6, 12])
            
            if st.form_submit_button("Calcular e Salvar"):
                custo_materiais_total = 0.0
                if not df_mat_ref.empty:
                    df_m_ativos = df_mat_ref[df_mat_ref['Status'] == 'Ativo']
                    for _, mat in df_m_ativos.iterrows():
                        vincs = [x.strip() for x in str(mat['Procedimentos_Vinculados']).split(',')]
                        if nome_p in vincs or "Geral" in vincs:
                            custo_materiais_total += float(mat['Custo_Por_Paciente'])

                custo_aluguel_total = qtd_consultas * aluguel_consulta
                custo_base = custo_materiais_total + custo_aluguel_total

                if tipo_lucro == "Percentual Geral":
                    valor_lucro = custo_base * (lucro_geral / 100.0)
                elif tipo_lucro == "Percentual Específico":
                    valor_lucro = custo_base * (val_lucro_input / 100.0)
                else:
                    valor_lucro = val_lucro_input

                subtotal = custo_base + valor_lucro
                valor_imposto = subtotal * (imposto_pct / 100.0)
                total_pix = subtotal + valor_imposto

                taxa_cartao_pct = taxas_cartao.get(parcelas_sel, 3.0)
                total_cartao = total_pix / (1 - (taxa_cartao_pct / 100.0))
                custo_cartao = total_cartao - total_pix

                novo_id = len(df_proc) + 1
                novo_p = {
                    'ID': novo_id, 'Procedimento': nome_p, 'Custo_Materiais': round(custo_materiais_total, 2),
                    'Qtd_Consultas': qtd_consultas, 'Custo_Aluguel': round(custo_aluguel_total, 2),
                    'Tipo_Lucro': tipo_lucro, 'Lucro_Valor': round(valor_lucro, 2),
                    'Imposto_Valor': round(valor_imposto, 2), 'Parcelas': f"{parcelas_sel}x",
                    'Taxa_Cartao_Pct': f"{taxa_cartao_pct}%", 'Custo_Cartao': round(custo_cartao, 2),
                    'Total_PIX': round(total_pix, 2), 'Total_Cartao': round(total_cartao, 2), 'Status': 'Ativo'
                }
                df_proc = pd.concat([df_proc, pd.DataFrame([novo_p])], ignore_index=True)
                write_data("Procedimentos", df_proc)
                st.success("Procedimento gravado!")
                st.rerun()

    st.markdown("---")
    df_proc_active = df_proc[df_proc['Status'] == 'Ativo'] if not df_proc.empty else df_proc

    if not df_proc_active.empty:
        col_fp, col_dp = st.columns([3, 1])
        busca_p = col_fp.text_input("🔍 Filtrar Procedimentos:", placeholder="Digite o nome do procedimento...")
        
        df_p_disp = df_proc_active[df_proc_active['Procedimento'].str.contains(busca_p, case=False, na=False)] if busca_p else df_proc_active
        col_dp.download_button("📊 Baixar Excel", data=export_to_excel(df_p_disp), file_name="procedimentos.xlsx", use_container_width=True)

        edited_proc = st.data_editor(df_p_disp.drop(columns=['Status'], errors='ignore'), use_container_width=True, key="editor_proc")

        if st.button("💾 Salvar Alterações na Planilha (Procedimentos)"):
            for idx, row in edited_proc.iterrows():
                p_id = row['ID']
                df_proc.loc[df_proc['ID'] == p_id, ['Procedimento', 'Qtd_Consultas', 'Total_PIX', 'Total_Cartao']] = [
                    row['Procedimento'], row['Qtd_Consultas'], row['Total_PIX'], row['Total_Cartao']
                ]
            write_data("Procedimentos", df_proc)
            st.success("Salvo no Google Sheets!")
            st.rerun()

# ------------------------------------------
# TAB 3: AGENDA (CALENDÁRIO VISUAL)
# ------------------------------------------
AG_COLS = ['ID', 'Data', 'Horario', 'Paciente', 'Telefone', 'Email', 'Procedimento', 'Status']
PAC_COLS = ['ID', 'Paciente', 'Telefone', 'Email', 'Historico_Procedimentos', 'Ultima_Ida', 'Recorrencia', 'Status']

with tab_ag:
    st.subheader("📅 Agenda da Clínica")
    df_ag = read_data("Agenda", AG_COLS)
    df_pac = read_data("Pacientes", PAC_COLS)
    df_proc_ref = read_data("Procedimentos", PROC_COLS)
    procs_disponiveis = df_proc_ref[df_proc_ref['Status'] == 'Ativo']['Procedimento'].tolist() if not df_proc_ref.empty else ["Consulta Geral"]

    col_ag1, col_ag2 = st.columns([1, 2])

    with col_ag1:
        st.write("### ➕ Novo Agendamento")
        with st.form("form_ag_cal"):
            dt_c = st.date_input("Data*", value=datetime.now())
            hr_c = st.time_input("Horário*", value=datetime.now().time())
            nome_pac = st.text_input("Nome do Paciente*")
            tel_pac = st.text_input("Telefone")
            email_pac = st.text_input("E-mail")
            proc_ag = st.selectbox("Procedimento", options=procs_disponiveis)
            
            if st.form_submit_button("Agendar Consulta", use_container_width=True):
                if nome_pac:
                    data_str = dt_c.strftime("%d/%m/%Y")
                    novo_id_ag = len(df_ag) + 1
                    reg_ag = {
                        'ID': novo_id_ag, 'Data': data_str, 'Horario': hr_c.strftime("%H:%M"),
                        'Paciente': nome_pac, 'Telefone': tel_pac, 'Email': email_pac,
                        'Procedimento': proc_ag, 'Status': 'Ativo'
                    }
                    df_ag = pd.concat([df_ag, pd.DataFrame([reg_ag])], ignore_index=True)
                    write_data("Agenda", df_ag)

                    # Atualização do cadastro de Pacientes
                    novo_item_hist = f"[{data_str}] {proc_ag}"
                    if not df_pac.empty and nome_pac in df_pac['Paciente'].values:
                        idx = df_pac[df_pac['Paciente'] == nome_pac].index[0]
                        hist_atual = str(df_pac.loc[idx, 'Historico_Procedimentos'])
                        df_pac.loc[idx, 'Historico_Procedimentos'] = hist_atual + " | " + novo_item_hist
                        df_pac.loc[idx, 'Ultima_Ida'] = data_str
                        df_pac.loc[idx, 'Recorrencia'] = int(df_pac.loc[idx, 'Recorrencia']) + 1
                    else:
                        reg_pac = {
                            'ID': len(df_pac) + 1, 'Paciente': nome_pac, 'Telefone': tel_pac,
                            'Email': email_pac, 'Historico_Procedimentos': novo_item_hist,
                            'Ultima_Ida': data_str, 'Recorrencia': 1, 'Status': 'Ativo'
                        }
                        df_pac = pd.concat([df_pac, pd.DataFrame([reg_pac])], ignore_index=True)

                    write_data("Pacientes", df_pac)
                    st.success("Agendado!")
                    st.rerun()

    with col_ag2:
        st.write("### 📆 Visualização Diária")
        data_filtro = st.date_input("Escolha a data para ver os compromissos:", value=datetime.now())
        data_filtro_str = data_filtro.strftime("%d/%m/%Y")

        df_ag_active = df_ag[df_ag['Status'] == 'Ativo'] if not df_ag.empty else df_ag
        df_dia = df_ag_active[df_ag_active['Data'] == data_filtro_str] if not df_ag_active.empty else pd.DataFrame()

        if df_dia.empty:
            st.info(f"Nenhuma consulta agendada para o dia {data_filtro_str}.")
        else:
            for _, ag_item in df_dia.sort_values(by='Horario').iterrows():
                st.markdown(f"""
                    <div class="agenda-card">
                        <strong style="color: {ROSE_PRIMARY}; font-size: 16px;">⏰ {ag_item['Horario']} - {ag_item['Paciente']}</strong><br/>
                        <b>Procedimento:</b> {ag_item['Procedimento']} | <b>Telefone:</b> {ag_item['Telefone']}
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.write("### 📋 Todas as Consultas")
        st.dataframe(df_ag_active.drop(columns=['Status'], errors='ignore'), use_container_width=True)

# ------------------------------------------
# TAB 4: PACIENTES
# ------------------------------------------
with tab_pac:
    st.subheader("Base de Pacientes")
    df_pac = read_data("Pacientes", PAC_COLS)
    df_pac_active = df_pac[df_pac['Status'] == 'Ativo'] if not df_pac.empty else df_pac

    if df_pac_active.empty:
        st.info("Nenhum paciente cadastrado.")
    else:
        col_fpac, col_dpac = st.columns([3, 1])
        busca_pac = col_fpac.text_input("🔍 Buscar Paciente:", placeholder="Digite o nome do paciente...")
        
        df_p_show = df_pac_active[df_pac_active['Paciente'].str.contains(busca_pac, case=False, na=False)] if busca_pac else df_pac_active
        col_dpac.download_button("📊 Baixar Excel", data=export_to_excel(df_p_show), file_name="pacientes.xlsx", use_container_width=True)

        st.dataframe(df_p_show[['Paciente', 'Telefone', 'Email', 'Ultima_Ida', 'Recorrencia']], use_container_width=True)

        st.subheader("📋 Histórico Clínico do Paciente")
        pac_sel = st.selectbox("Selecione o Paciente para ver o histórico:", options=df_pac_active['Paciente'].tolist())
        if pac_sel:
            row_p = df_pac_active[df_pac_active['Paciente'] == pac_sel].iloc[0]
            historico_raw = str(row_p['Historico_Procedimentos']).split(" | ")
            for item in historico_raw:
                if item and item != 'nan':
                    st.write(f"• {item}")

# ------------------------------------------
# TAB 5: CONFIGURAÇÕES & TAXAS (NOVA GUIA)
# ------------------------------------------
with tab_cfg:
    st.subheader("⚙️ Configurações do Consultório e Taxas de Cartão")
    st.caption("Altere os custos fixos e taxas abaixo. Eles serão gravados permanentemente no banco de dados.")

    with st.form("form_config"):
        c_c1, c_c2 = st.columns(2)
        novo_aluguel = c_c1.number_input("Custo de Aluguel por Consulta (R$)", value=aluguel_consulta, step=5.0)
        novo_imposto = c_c2.number_input("Imposto Geral Padrão (%)", value=imposto_geral, step=0.5)
        novo_lucro = c_c1.number_input("Margem de Lucro Geral (%)", value=lucro_geral, step=1.0)

        st.markdown("---")
        st.write("#### Taxas da Maquininha de Cartão (%)")
        t1 = c_c1.number_input("Taxa Cartão 1x / À Vista (%)", value=taxas_cartao[1], step=0.1)
        t2 = c_c2.number_input("Taxa Cartão 2x (%)", value=taxas_cartao[2], step=0.1)
        t3 = c_c1.number_input("Taxa Cartão 3x (%)", value=taxas_cartao[3], step=0.1)
        t6 = c_c2.number_input("Taxa Cartão 6x (%)", value=taxas_cartao[6], step=0.1)
        t12 = c_c1.number_input("Taxa Cartão 12x (%)", value=taxas_cartao[12], step=0.1)

        if st.form_submit_button("💾 Salvar Parâmetros no Banco de Dados"):
            novas_configs = [
                {'Chave': 'aluguel_consulta', 'Valor': novo_aluguel},
                {'Chave': 'imposto_geral', 'Valor': novo_imposto},
                {'Chave': 'lucro_geral', 'Valor': novo_lucro},
                {'Chave': 'taxa_1x', 'Valor': t1},
                {'Chave': 'taxa_2x', 'Valor': t2},
                {'Chave': 'taxa_3x', 'Valor': t3},
                {'Chave': 'taxa_6x', 'Valor': t6},
                {'Chave': 'taxa_12x', 'Valor': t12}
            ]
            write_data("Configuracoes", pd.DataFrame(novas_configs))
            st.success("Configurações atualizadas com sucesso!")
            st.rerun()

# ------------------------------------------
# TAB 6: LIXEIRA / SEGURANÇA
# ------------------------------------------
with tab_trash:
    st.subheader("🗑️ Lixeira do Sistema & Restauração")
    cat_del = st.selectbox("Categoria:", ["Materiais", "Procedimentos", "Agenda", "Pacientes"])

    if cat_del == "Materiais":
        df_t = read_data("Materiais", MAT_COLS)
        k_col = "Material"
    elif cat_del == "Procedimentos":
        df_t = read_data("Procedimentos", PROC_COLS)
        k_col = "Procedimento"
    elif cat_del == "Agenda":
        df_t = read_data("Agenda", AG_COLS)
        k_col = "Paciente"
    else:
        df_t = read_data("Pacientes", PAC_COLS)
        k_col = "Paciente"

    if not df_t.empty:
        df_ex = df_t[df_t['Status'] == 'Excluido']
        if df_ex.empty:
            st.success(f"Nenhum item na lixeira de {cat_del}.")
        else:
            st.dataframe(df_ex, use_container_width=True)
            res_item = st.selectbox(f"Restaurar de {cat_del}:", options=df_ex[k_col].tolist())
            if st.button("🔄 Restaurar Item"):
                df_t.loc[df_t[k_col] == res_item, 'Status'] = 'Ativo'
                write_data(cat_del, df_t)
                st.success("Item restaurado!")
                st.rerun()
