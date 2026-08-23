import streamlit as st
import pandas as pd
import hashlib
import io
from datetime import datetime
from difflib import SequenceMatcher
from streamlit_gsheets import GSheetsConnection

# ==========================================
# CONFIGURAÇÃO DE PÁGINA E DESIGN ROSÉ
# ==========================================
st.set_page_config(
    page_title="Gestão & Precificação - Dra. Rachel Leal",
    page_icon="🦷",
    layout="wide"
)

ROSE_PRIMARY = "#d19496"
ROSE_SECONDARY = "#e8b9b3"

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Comfortaa:wght@400;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Comfortaa', cursive, sans-serif;
    }}
    
    .stApp {{
        background-color: #faf7f7;
    }}
    
    .stButton > button {{
        background-color: {ROSE_PRIMARY} !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
    }}
    
    .stButton > button:hover {{
        background-color: {ROSE_SECONDARY} !important;
        color: white !important;
    }}
    
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background-color: #f0e4e5;
        border-radius: 6px 6px 0 0;
        color: #555;
        font-weight: 600;
    }}

    .stTabs [aria-selected="true"] {{
        background-color: {ROSE_PRIMARY} !important;
        color: white !important;
    }}

    .header-title {{
        color: {ROSE_PRIMARY};
        font-family: 'Comfortaa', cursive, sans-serif;
        font-weight: 700;
        text-align: center;
        margin-bottom: 20px;
    }}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# CONEXÃO COM O GOOGLE SHEETS
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

def read_data(worksheet_name, default_columns):
    try:
        df = conn.read(worksheet=worksheet_name, ttl=2)
        if df.empty:
            return pd.DataFrame(columns=default_columns)
        return df
    except Exception:
        return pd.DataFrame(columns=default_columns)

def write_data(worksheet_name, df):
    conn.update(worksheet=worksheet_name, data=df)

# ==========================================
# AUTENTICAÇÃO SEGURA (HASH SHA-256)
# ==========================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Hashing seguro para as senhas fornecidas
USER_DATABASE = {
    "vinicius.pereira": hash_password("vin%tr2019"),
    "rachel": hash_password("1lindinha2")
}

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

def login_screen():
    st.markdown("<h1 class='header-title'>Dra. Rachel Leal</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: #777;'>Sistema de Precificação & Gestão Odontológica</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username_input = st.text_input("Usuário").strip().lower()
            password_input = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar no Sistema")
            
            if submit:
                hashed_input = hash_password(password_input)
                if username_input in USER_DATABASE and USER_DATABASE[username_input] == hashed_input:
                    st.session_state.authenticated = True
                    st.session_state.current_user = username_input
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

if not st.session_state.authenticated:
    login_screen()
    st.stop()

# ==========================================
# ESTRUTURA GERAL DO PROGRAMA
# ==========================================
st.markdown(f"<h2 class='header-title'>Dra. Rachel Leal | Painel de Gestão</h2>", unsafe_allow_html=True)

# Configurações de Custos Fixos na Barra Lateral
with st.sidebar:
    st.write(f"👤 **Usuário:** `{st.session_state.current_user}`")
    st.header("⚙️ Parâmetros Globais")
    
    aluguel_consulta = st.number_input("Custo Aluguel por Consulta (R$)", value=60.0, step=5.0)
    imposto_geral = st.number_input("Imposto Geral Padrão (%)", value=6.0, step=0.5)
    lucro_geral = st.number_input("Margem de Lucro Geral (%)", value=40.0, step=1.0)
    
    st.subheader("Taxas de Cartão (%)")
    taxas_cartao = {
        1: st.number_input("À Vista (1x) (%)", value=2.5, step=0.1),
        2: st.number_input("2x (%)", value=4.0, step=0.1),
        3: st.number_input("3x (%)", value=5.5, step=0.1),
        6: st.number_input("6x (%)", value=8.0, step=0.1),
        12: st.number_input("12x (%)", value=12.0, step=0.1)
    }

    if st.button("Sair do Sistema"):
        st.session_state.authenticated = False
        st.session_state.current_user = None
        st.rerun()

# Auxiliares
def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Dados')
    return output.getvalue()

def similarity(a, b):
    return SequenceMatcher(None, str(a).lower().strip(), str(b).lower().strip()).ratio()

# Abas do Programa
tab_mat, tab_proc, tab_ag, tab_pac, tab_trash = st.tabs([
    "📦 1. Materiais", "⚖️ 2. Procedimentos & Precificação", "📅 3. Agenda", "👥 4. Pacientes", "🗑️ 5. Lixeira / Segurança"
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
    
    with st.form("form_mat", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome_m = c1.text_input("Nome do Material*")
        preco_c = c2.number_input("Preço de Compra (R$)*", min_value=0.01, step=10.0)
        
        procs_sel = c1.multiselect("Procedimentos em que é usado", options=procs_validos if procs_validos else ["Geral"])
        rendimento = c2.number_input("Rendimento (Quantas pessoas atende?)*", min_value=1, value=1)
        
        btn_salvar_m = st.form_submit_button("Cadastrar Material")
        
        if btn_salvar_m and nome_m:
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
            st.success(f"Material '{nome_m}' gravado no banco de dados!")
            st.rerun()

    st.markdown("---")
    df_mat_active = df_mat[df_mat['Status'] == 'Ativo'] if not df_mat.empty else df_mat
    st.dataframe(df_mat_active.drop(columns=['Status'], errors='ignore'), use_container_width=True)
    
    if not df_mat_active.empty:
        col_m1, col_m2 = st.columns([3, 1])
        mat_del = col_m1.selectbox("Selecione um material para mover para a lixeira:", options=df_mat_active['Material'].tolist())
        if col_m2.button("Mover para Lixeira (Material)"):
            df_mat.loc[df_mat['Material'] == mat_del, 'Status'] = 'Excluido'
            write_data("Materiais", df_mat)
            st.warning(f"Material '{mat_del}' movido para a lixeira.")
            st.rerun()
            
        st.download_button("📊 Exportar Tabela em Excel", data=export_to_excel(df_mat_active), file_name="materiais.xlsx")

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
    
    with st.form("form_proc"):
        c1, c2, c3 = st.columns(3)
        nome_p = c1.text_input("Nome do Procedimento*")
        qtd_consultas = c2.number_input("Quantidade de Idas/Consultas*", min_value=1, value=1)
        
        tipo_lucro = c3.selectbox("Tipo de Lucro", ["Percentual Geral", "Percentual Específico", "Valor Fixo"])
        val_lucro_input = 0.0
        if tipo_lucro == "Percentual Específico":
            val_lucro_input = c3.number_input("Lucro Específico (%)", min_value=0.0, value=30.0)
        elif tipo_lucro == "Valor Fixo":
            val_lucro_input = c3.number_input("Lucro Fixo (R$)", min_value=0.0, value=150.0)
            
        imposto_pct = c1.number_input("Imposto Aplicável (%)", value=imposto_geral)
        parcelas_sel = c2.selectbox("Divisão do Cartão", options=[1, 2, 3, 6, 12])
        
        btn_calc_p = st.form_submit_button("Calcular e Cadastrar Procedimento")

    if btn_calc_p and nome_p:
        # Somatório automático dos custos de materiais vinculados
        custo_materiais_total = 0.0
        if not df_mat_ref.empty:
            df_m_ativos = df_mat_ref[df_mat_ref['Status'] == 'Ativo']
            for _, mat in df_m_ativos.iterrows():
                vincs = [x.strip() for x in str(mat['Procedimentos_Vinculados']).split(',')]
                if nome_p in vincs or "Geral" in vincs:
                    custo_materiais_total += float(mat['Custo_Por_Paciente'])

        custo_aluguel_total = qtd_consultas * aluguel_consulta
        custo_base = custo_materiais_total + custo_aluguel_total

        # Cálculo do Lucro
        if tipo_lucro == "Percentual Geral":
            valor_lucro = custo_base * (lucro_geral / 100.0)
        elif tipo_lucro == "Percentual Específico":
            valor_lucro = custo_base * (val_lucro_input / 100.0)
        else:
            valor_lucro = val_lucro_input

        subtotal = custo_base + valor_lucro
        valor_imposto = subtotal * (imposto_pct / 100.0)
        total_pix = subtotal + valor_imposto

        # Taxas do Cartão
        taxa_cartao_pct = taxas_cartao.get(parcelas_sel, 3.0)
        total_cartao = total_pix / (1 - (taxa_cartao_pct / 100.0))
        custo_cartao = total_cartao - total_pix

        novo_id = len(df_proc) + 1
        novo_p = {
            'ID': novo_id,
            'Procedimento': nome_p,
            'Custo_Materiais': round(custo_materiais_total, 2),
            'Qtd_Consultas': qtd_consultas,
            'Custo_Aluguel': round(custo_aluguel_total, 2),
            'Tipo_Lucro': tipo_lucro,
            'Lucro_Valor': round(valor_lucro, 2),
            'Imposto_Valor': round(valor_imposto, 2),
            'Parcelas': f"{parcelas_sel}x",
            'Taxa_Cartao_Pct': f"{taxa_cartao_pct}%",
            'Custo_Cartao': round(custo_cartao, 2),
            'Total_PIX': round(total_pix, 2),
            'Total_Cartao': round(total_cartao, 2),
            'Status': 'Ativo'
        }

        df_proc = pd.concat([df_proc, pd.DataFrame([novo_p])], ignore_index=True)
        write_data("Procedimentos", df_proc)
        st.success(f"Procedimento '{nome_p}' precificado e salvo!")
        st.rerun()

    st.markdown("---")
    df_proc_active = df_proc[df_proc['Status'] == 'Ativo'] if not df_proc.empty else df_proc
    st.dataframe(df_proc_active.drop(columns=['Status'], errors='ignore'), use_container_width=True)

    if not df_proc_active.empty:
        col_p1, col_p2 = st.columns([3, 1])
        proc_del = col_p1.selectbox("Selecione um procedimento para mover para a lixeira:", options=df_proc_active['Procedimento'].tolist())
        if col_p2.button("Mover para Lixeira (Procedimento)"):
            df_proc.loc[df_proc['Procedimento'] == proc_del, 'Status'] = 'Excluido'
            write_data("Procedimentos", df_proc)
            st.warning(f"Procedimento '{proc_del}' movido para a lixeira.")
            st.rerun()

        st.download_button("📊 Exportar Tabela em Excel", data=export_to_excel(df_proc_active), file_name="procedimentos_precificados.xlsx")

# ------------------------------------------
# TAB 3: AGENDA
# ------------------------------------------
AG_COLS = ['ID', 'Data', 'Horario', 'Paciente', 'Telefone', 'Email', 'Procedimento', 'Status']
PAC_COLS = ['ID', 'Paciente', 'Telefone', 'Email', 'Historico_Procedimentos', 'Ultima_Ida', 'Recorrencia', 'Status']

with tab_ag:
    st.subheader("Agendamento de Consultas")
    df_ag = read_data("Agenda", AG_COLS)
    df_pac = read_data("Pacientes", PAC_COLS)
    df_proc_ref = read_data("Procedimentos", PROC_COLS)

    procs_disponiveis = df_proc_ref[df_proc_ref['Status'] == 'Ativo']['Procedimento'].tolist() if not df_proc_ref.empty else ["Consulta Geral"]

    with st.form("form_agenda"):
        c1, c2 = st.columns(2)
        dt_c = c1.date_input("Data da Consulta*", value=datetime.now())
        hr_c = c2.time_input("Horário*", value=datetime.now().time())

        nome_pac = c1.text_input("Nome do Paciente*")
        tel_pac = c2.text_input("Telefone")
        email_pac = c1.text_input("E-mail")
        proc_ag = c2.selectbox("Tipo de Procedimento", options=procs_disponiveis)

        btn_agendar = st.form_submit_button("Confirmar Agendamento")

    if btn_agendar and nome_pac:
        # Verificação de nome similar/duplicado em Pacientes
        pacientes_existentes = df_pac[df_pac['Status'] == 'Ativo']['Paciente'].tolist() if not df_pac.empty else []
        nome_final = nome_pac
        
        for p_exist in pacientes_existentes:
            sim = similarity(nome_pac, p_exist)
            if 0.8 <= sim < 1.0:
                st.info(f"💡 Encontrado paciente similar cadastrado: '{p_exist}'. O agendamento foi vinculado a este cadastro.")
                nome_final = p_exist
                break
            elif sim == 1.0:
                nome_final = p_exist
                break

        # 1. Salva na Agenda
        novo_id_ag = len(df_ag) + 1
        reg_ag = {
            'ID': novo_id_ag,
            'Data': dt_c.strftime("%d/%m/%Y"),
            'Horario': hr_c.strftime("%H:%M"),
            'Paciente': nome_final,
            'Telefone': tel_pac,
            'Email': email_pac,
            'Procedimento': proc_ag,
            'Status': 'Ativo'
        }
        df_ag = pd.concat([df_ag, pd.DataFrame([reg_ag])], ignore_index=True)
        write_data("Agenda", df_ag)

        # 2. Atualiza ou cria em Pacientes
        data_str = dt_c.strftime("%d/%m/%Y")
        novo_item_hist = f"[{data_str}] {proc_ag}"

        if not df_pac.empty and nome_final in df_pac['Paciente'].values:
            idx = df_pac[df_pac['Paciente'] == nome_final].index[0]
            hist_atual = str(df_pac.loc[idx, 'Historico_Procedimentos'])
            novo_hist = hist_atual + " | " + novo_item_hist if hist_atual and hist_atual != 'nan' else novo_item_hist
            
            df_pac.loc[idx, 'Historico_Procedimentos'] = novo_hist
            df_pac.loc[idx, 'Ultima_Ida'] = data_str
            df_pac.loc[idx, 'Recorrencia'] = int(df_pac.loc[idx, 'Recorrencia']) + 1
            if tel_pac: df_pac.loc[idx, 'Telefone'] = tel_pac
            if email_pac: df_pac.loc[idx, 'Email'] = email_pac
        else:
            novo_id_pac = len(df_pac) + 1
            reg_pac = {
                'ID': novo_id_pac,
                'Paciente': nome_final,
                'Telefone': tel_pac,
                'Email': email_pac,
                'Historico_Procedimentos': novo_item_hist,
                'Ultima_Ida': data_str,
                'Recorrencia': 1,
                'Status': 'Ativo'
            }
            df_pac = pd.concat([df_pac, pd.DataFrame([reg_pac])], ignore_index=True)

        write_data("Pacientes", df_pac)
        st.success(f"Consulta agendada com sucesso para '{nome_final}'!")
        st.rerun()

    st.markdown("---")
    df_ag_active = df_ag[df_ag['Status'] == 'Ativo'] if not df_ag.empty else df_ag
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
        st.dataframe(
            df_pac_active[['Paciente', 'Telefone', 'Email', 'Ultima_Ida', 'Recorrencia']],
            use_container_width=True
        )

        st.subheader("📋 Histórico Clínico / Procedimentos")
        pac_sel = st.selectbox("Selecione o Paciente para visualizar o histórico:", options=df_pac_active['Paciente'].tolist())

        if pac_sel:
            row_p = df_pac_active[df_pac_active['Paciente'] == pac_sel].iloc[0]
            historico_raw = str(row_p['Historico_Procedimentos']).split(" | ")
            
            with st.expander(f"Ver histórico completo de {pac_sel}", expanded=True):
                for item in historico_raw:
                    if item and item != 'nan':
                        st.write(f"• {item}")

# ------------------------------------------
# TAB 5: LIXEIRA / RESTAURAÇÃO (SEGURANÇA)
# ------------------------------------------
with tab_trash:
    st.subheader("🗑️ Lixeira do Sistema & Restauração de Dados")
    st.caption("Esta área permite recuperar registros desativados em até semanas ou meses sem perda de dados.")

    categoria = st.selectbox("Selecione a categoria para verificar a lixeira:", ["Materiais", "Procedimentos", "Agenda", "Pacientes"])

    if categoria == "Materiais":
        df_t = read_data("Materiais", MAT_COLS)
        col_key = "Material"
    elif categoria == "Procedimentos":
        df_t = read_data("Procedimentos", PROC_COLS)
        col_key = "Procedimento"
    elif categoria == "Agenda":
        df_t = read_data("Agenda", AG_COLS)
        col_key = "Paciente"
    else:
        df_t = read_data("Pacientes", PAC_COLS)
        col_key = "Paciente"

    if not df_t.empty:
        df_excluidos = df_t[df_t['Status'] == 'Excluido']
        if df_excluidos.empty:
            st.success(f"Nenhum item excluído na categoria **{categoria}**.")
        else:
            st.dataframe(df_excluidos, use_container_width=True)
            item_restore = st.selectbox(f"Selecione um item da categoria {categoria} para restaurar:", options=df_excluidos[col_key].tolist())

            if st.button("🔄 Restaurar Item Selecionado"):
                df_t.loc[df_t[col_key] == item_restore, 'Status'] = 'Ativo'
                write_data(categoria, df_t)
                st.success(f"'{item_restore}' foi restaurado para o sistema ativo!")
                st.rerun()