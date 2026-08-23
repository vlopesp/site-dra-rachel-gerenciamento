import io
import re
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ------------------------------------------
# CONFIGURAÇÃO DE COLUNAS DAS PLANILHAS
# ------------------------------------------
CFG_COLS = ["Chave", "Valor"]

MAT_COLS = [
    "ID",
    "Material",
    "Custo_Embalagem",
    "Rendimento",
    "Custo_Por_Paciente",
    "Procedimentos_Vinculados",
    "Status",
]

PROC_COLS = [
    "ID",
    "Procedimento",
    "Custo_Materiais",
    "Qtd_Consultas",
    "Custo_Aluguel",
    "Tipo_Lucro",
    "Lucro_Valor",
    "Lucro_Calculado_RS",
    "Imposto_Valor",
    "Parcelas",
    "Taxa_Cartao_Pct",
    "Custo_Cartao",
    "Total_PIX",
    "Total_Cartao",
    "Status",
]

AGENDA_COLS = [
    "ID",
    "Data",
    "Horario",
    "Paciente",
    "Procedimento",
    "Valor_Cobrado",
    "Forma_Pagamento",
    "Status_Agendamento",
    "Status",
]

PAC_COLS = [
    "ID",
    "Nome",
    "CPF",
    "Telefone",
    "Email",
    "Historico_Procedimentos",
    "Status",
]

CAIXA_COLS = [
    "ID",
    "Data",
    "Tipo",
    "Categoria",
    "Descricao",
    "Valor",
    "Status",
]


# ------------------------------------------
# CONEXÃO COM GOOGLE SHEETS
# ------------------------------------------
@st.cache_resource
def get_gspread_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    return gspread.authorize(creds)


def get_spreadsheet():
    client = get_gspread_client()
    sheet_id = st.secrets["sheets"]["spreadsheet_id"]
    return client.open_by_key(sheet_id)


def read_data(sheet_name, expected_cols):
    try:
        sh = get_spreadsheet()
        try:
            worksheet = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            if sheet_name == "Caixa":
                worksheet = sh.worksheet("LivroCaixa")
            else:
                raise
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        return df[expected_cols]
    except Exception as e:
        st.error(f"Erro ao ler aba '{sheet_name}': {e}")
        return pd.DataFrame(columns=expected_cols)


def write_data(sheet_name, df):
    try:
        sh = get_spreadsheet()
        try:
            worksheet = sh.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            if sheet_name == "Caixa":
                worksheet = sh.worksheet("LivroCaixa")
            else:
                raise
        worksheet.clear()
        df_to_write = df.fillna("")
        worksheet.update(
            [df_to_write.columns.values.tolist()] + df_to_write.values.tolist()
        )
    except Exception as e:
        st.error(f"Erro ao salvar na aba '{sheet_name}': {e}")


def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
    return output.getvalue()


# ------------------------------------------
# REGRAS E FUNÇÕES DE CÁLCULO
# ------------------------------------------
def get_cfg_val(df_cfg, chave, valor_padrao):
    if (
        not df_cfg.empty
        and "Chave" in df_cfg.columns
        and chave in df_cfg["Chave"].values
    ):
        try:
            val_raw = str(df_cfg[df_cfg["Chave"] == chave]["Valor"].values[0])
            val_clean = val_raw.replace(",", ".").strip()
            return float(val_clean)
        except Exception:
            return valor_padrao
    return valor_padrao


def recalcular_procedimentos_df(
    df_p, df_m_ref, aluguel_cons, imposto_g, lucro_g, taxas_c
):
    if df_p.empty:
        return df_p

    df_m_ativos = (
        df_m_ref[df_m_ref["Status"] == "Ativo"]
        if not df_m_ref.empty
        else pd.DataFrame()
    )

    for idx in df_p.index:
        row = df_p.loc[idx]
        nome_p = str(row["Procedimento"]).strip()

        # 1. Custo Materiais
        custo_materiais_total = 0.0
        if not df_m_ativos.empty:
            for _, mat in df_m_ativos.iterrows():
                vincs = [
                    x.strip()
                    for x in str(mat["Procedimentos_Vinculados"]).split(",")
                ]
                if nome_p in vincs or "Geral" in vincs:
                    try:
                        c_m = float(
                            str(mat["Custo_Por_Paciente"]).replace(",", ".")
                        )
                    except Exception:
                        c_m = 0.0
                    custo_materiais_total += c_m

        # 2. Consultas e Aluguel
        try:
            qtd_consultas = int(
                float(str(row["Qtd_Consultas"]).replace(",", "."))
            )
        except Exception:
            qtd_consultas = 1
        if qtd_consultas < 1:
            qtd_consultas = 1

        custo_aluguel_total = qtd_consultas * aluguel_cons
        custo_base = custo_materiais_total + custo_aluguel_total

        # 3. Lógica Dinâmica de Lucro
        tipo_lucro = str(row.get("Tipo_Lucro", "Percentual Geral")).strip()
        try:
            val_lucro_input = float(
                str(row.get("Lucro_Valor", 0.0)).replace(",", ".")
            )
        except Exception:
            val_lucro_input = 0.0

        if tipo_lucro == "Percentual Geral":
            val_exibicao = lucro_g
            valor_lucro_rs = custo_base * (lucro_g / 100.0)
        elif tipo_lucro == "Percentual Específico":
            val_exibicao = val_lucro_input
            valor_lucro_rs = custo_base * (val_lucro_input / 100.0)
        else:  # Valor Fixo
            val_exibicao = val_lucro_input
            valor_lucro_rs = val_lucro_input

        # 4. Imposto e PIX
        subtotal = custo_base + valor_lucro_rs
        valor_imposto = subtotal * (imposto_g / 100.0)
        total_pix = subtotal + valor_imposto

        # 5. Parcelamento e Cartão
        parc_str = str(row.get("Parcelas", "1x"))
        try:
            parcelas_sel = int(re.sub(r"\D", "", parc_str))
        except Exception:
            parcelas_sel = 1
        if parcelas_sel < 1:
            parcelas_sel = 1
        if parcelas_sel > 12:
            parcelas_sel = 12

        taxa_cartao_pct = taxas_c.get(parcelas_sel, 3.0)
        total_cartao = (
            total_pix / (1 - (taxa_cartao_pct / 100.0))
            if taxa_cartao_pct < 100
            else total_pix
        )
        custo_cartao = total_cartao - total_pix

        # Atualiza a tabela
        df_p.loc[idx, "Custo_Materiais"] = round(custo_materiais_total, 2)
        df_p.loc[idx, "Qtd_Consultas"] = qtd_consultas
        df_p.loc[idx, "Custo_Aluguel"] = round(custo_aluguel_total, 2)
        df_p.loc[idx, "Tipo_Lucro"] = tipo_lucro
        df_p.loc[idx, "Lucro_Valor"] = round(val_exibicao, 2)
        df_p.loc[idx, "Lucro_Calculado_RS"] = round(valor_lucro_rs, 2)
        df_p.loc[idx, "Imposto_Valor"] = round(valor_imposto, 2)
        df_p.loc[idx, "Parcelas"] = f"{parcelas_sel}x"
        df_p.loc[idx, "Taxa_Cartao_Pct"] = f"{taxa_cartao_pct}%"
        df_p.loc[idx, "Custo_Cartao"] = round(custo_cartao, 2)
        df_p.loc[idx, "Total_PIX"] = round(total_pix, 2)
        df_p.loc[idx, "Total_Cartao"] = round(total_cartao, 2)

    return df_p


# ------------------------------------------
# LAYOUT PRINCIPAL DO STREAMLIT
# ------------------------------------------
st.set_page_config(
    page_title="Sistema de Precificação & Gestão",
    layout="wide",
    page_icon="⚖️",
)
st.title("🏥 Sistema de Gestão e Precificação")

# Carregar Configurações Globais
df_cfg = read_data("Configuracoes", CFG_COLS)
aluguel_consulta = get_cfg_val(df_cfg, "Aluguel_Consulta", 50.0)
imposto_geral = get_cfg_val(df_cfg, "Imposto_Geral", 6.0)
lucro_geral = get_cfg_val(df_cfg, "Lucro_Geral", 40.0)

taxas_cartao = {}
for i in range(1, 13):
    taxas_cartao[i] = get_cfg_val(
        df_cfg, f"Taxa_Cartao_{i}x", 3.0 + (i - 1) * 0.8
    )

# Navegação por Abas
tab_cfg, tab_mat, tab_proc, tab_agenda, tab_pac, tab_caixa, tab_lixeira = (
    st.tabs([
        "⚙️ Configurações",
        "📦 Materiais",
        "⚖️ Precificação",
        "📅 Agenda",
        "👥 Pacientes",
        "💵 Caixa",
        "🗑️ Lixeira",
    ])
)


# ------------------------------------------
# TAB 1: CONFIGURAÇÕES
# ------------------------------------------
with tab_cfg:
    st.subheader("⚙️ Configurações Gerais da Clínica")
    with st.form("form_cfg"):
        c1, c2, c3 = st.columns(3)
        novo_aluguel = c1.number_input(
            "Custo de Aluguel por Consulta (R$)",
            value=float(aluguel_consulta),
            step=5.0,
        )
        novo_imposto = c2.number_input(
            "Imposto Geral (%)", value=float(imposto_geral), step=0.5
        )
        novo_lucro = c3.number_input(
            "Margem de Lucro Geral (%)", value=float(lucro_geral), step=1.0
        )

        st.markdown("---")
        st.write("💳 **Taxas de Cartão de Crédito por Parcelamento**")
        novas_taxas = {}
        cols_t = st.columns(4)
        for i in range(1, 13):
            col_idx = (i - 1) % 4
            novas_taxas[i] = cols_t[col_idx].number_input(
                f"Taxa {i}x (%)", value=float(taxas_cartao[i]), step=0.1
            )

        if st.form_submit_button("💾 Salvar Configurações Globais"):
            novos_dados = [
                {"Chave": "Aluguel_Consulta", "Valor": novo_aluguel},
                {"Chave": "Imposto_Geral", "Valor": novo_imposto},
                {"Chave": "Lucro_Geral", "Valor": novo_lucro},
            ]
            for i in range(1, 13):
                novos_dados.append(
                    {"Chave": f"Taxa_Cartao_{i}x", "Valor": novas_taxas[i]}
                )

            df_new_cfg = pd.DataFrame(novos_dados)
            write_data("Configuracoes", df_new_cfg)
            st.success("Configurações atualizadas com sucesso!")
            st.rerun()


# ------------------------------------------
# TAB 2: MATERIAIS
# ------------------------------------------
with tab_mat:
    st.subheader("📦 Cadastro e Gestão de Materiais")
    df_mat = read_data("Materiais", MAT_COLS)

    with st.expander("➕ Cadastrar Novo Material", expanded=False):
        with st.form("form_mat"):
            m1, m2, m3, m4 = st.columns(4)
            nome_m = m1.text_input("Nome do Material*")
            custo_emb = m2.number_input(
                "Custo da Embalagem (R$)*", min_value=0.0, step=1.0
            )
            rendimento = m3.number_input(
                "Rendimento (Pacientes/Uso)*", min_value=1, value=1
            )
            vinc_proc = m4.text_input(
                "Vinculado ao Procedimento",
                value="Geral",
                help="Digite 'Geral' ou o nome exato do procedimento.",
            )

            if st.form_submit_button("Salvar Material"):
                custo_pac = (
                    custo_emb / rendimento if rendimento > 0 else custo_emb
                )
                novo_id = len(df_mat) + 1
                novo_m = {
                    "ID": novo_id,
                    "Material": nome_m,
                    "Custo_Embalagem": round(custo_emb, 2),
                    "Rendimento": rendimento,
                    "Custo_Por_Paciente": round(custo_pac, 2),
                    "Procedimentos_Vinculados": vinc_proc,
                    "Status": "Ativo",
                }
                df_mat = pd.concat(
                    [df_mat, pd.DataFrame([novo_m])], ignore_index=True
                )
                write_data("Materiais", df_mat)
                st.success("Material cadastrado com sucesso!")
                st.rerun()

    st.markdown("---")
    df_mat_active = (
        df_mat[df_mat["Status"] == "Ativo"]
        if not df_mat.empty
        else pd.DataFrame()
    )
    if not df_mat_active.empty:
        col_f, col_d = st.columns([3, 1])
        busca = col_f.text_input(
            "🔍 Buscar Material:", placeholder="Digite para filtrar..."
        )
        df_m_disp = (
            df_mat_active[
                df_mat_active["Material"].str.contains(
                    busca, case=False, na=False
                )
            ]
            if busca
            else df_mat_active
        )
        col_d.download_button(
            "📊 Baixar Excel",
            data=export_to_excel(df_m_disp),
            file_name="materiais.xlsx",
            use_container_width=True,
        )

        edited_mat = st.data_editor(
            df_m_disp.drop(columns=["Status"], errors="ignore"),
            use_container_width=True,
            key="editor_mat",
        )

        if st.button("💾 Salvar Alterações em Materiais"):
            for idx, row in edited_mat.iterrows():
                m_id = str(row["ID"]).strip()
                mask = df_mat["ID"].astype(str).str.strip() == m_id
                c_emb = float(row["Custo_Embalagem"])
                rend = int(row["Rendimento"]) if int(row["Rendimento"]) > 0 else 1
                df_mat.loc[mask, "Material"] = row["Material"]
                df_mat.loc[mask, "Custo_Embalagem"] = round(c_emb, 2)
                df_mat.loc[mask, "Rendimento"] = rend
                df_mat.loc[mask, "Custo_Por_Paciente"] = round(c_emb / rend, 2)
                df_mat.loc[mask, "Procedimentos_Vinculados"] = row[
                    "Procedimentos_Vinculados"
                ]

            write_data("Materiais", df_mat)
            st.success("Materiais atualizados!")
            st.rerun()

        st.markdown("---")
        cm_del1, cm_del2 = st.columns([3, 1])
        mat_del = cm_del1.selectbox(
            "Remover Material:",
            options=df_mat_active["Material"].tolist(),
            key="sel_del_mat",
        )
        if cm_del2.button("🗑️ Mover Material para Lixeira"):
            mask = (
                df_mat["Material"].astype(str).str.strip()
                == str(mat_del).strip()
            )
            df_mat.loc[mask, "Status"] = "Excluido"
            write_data("Materiais", df_mat)
            st.warning("Material movido para a lixeira!")
            st.rerun()


# ------------------------------------------
# TAB 3: PRECIFICAÇÃO
# ------------------------------------------
with tab_proc:
    st.subheader("⚖️ Cálculo e Precificação de Procedimentos")
    df_proc = read_data("Procedimentos", PROC_COLS)
    df_mat_ref = read_data("Materiais", MAT_COLS)

    # Recalcula dinamicamente em tempo real ao carregar
    if not df_proc.empty:
        df_proc = recalcular_procedimentos_df(
            df_proc,
            df_mat_ref,
            aluguel_consulta,
            imposto_geral,
            lucro_geral,
            taxas_cartao,
        )

    with st.expander("➕ Precificar Novo Procedimento", expanded=False):
        with st.form("form_proc"):
            c1, c2, c3 = st.columns(3)
            nome_p = c1.text_input("Nome do Procedimento*")
            qtd_consultas = c2.number_input(
                "Qtd. de Consultas/Idas*", min_value=1, value=1
            )
            tipo_lucro = c3.selectbox(
                "Tipo de Lucro",
                ["Percentual Geral", "Percentual Específico", "Valor Fixo"],
            )

            val_lucro_input = 0.0
            if tipo_lucro == "Percentual Específico":
                val_lucro_input = c3.number_input(
                    "Lucro Específico (%)", min_value=0.0, value=30.0
                )
            elif tipo_lucro == "Valor Fixo":
                val_lucro_input = c3.number_input(
                    "Lucro Fixo (R$)", min_value=0.0, value=150.0
                )
            else:
                val_lucro_input = lucro_geral

            parcelas_sel = c2.selectbox(
                "Parcelamento Cartão",
                options=list(range(1, 13)),
                format_func=lambda x: f"{x}x",
            )

            if st.form_submit_button("Calcular e Salvar Procedimento"):
                novo_id = len(df_proc) + 1
                novo_p = {
                    "ID": novo_id,
                    "Procedimento": nome_p,
                    "Custo_Materiais": 0.0,
                    "Qtd_Consultas": qtd_consultas,
                    "Custo_Aluguel": 0.0,
                    "Tipo_Lucro": tipo_lucro,
                    "Lucro_Valor": round(val_lucro_input, 2),
                    "Lucro_Calculado_RS": 0.0,
                    "Imposto_Valor": 0.0,
                    "Parcelas": f"{parcelas_sel}x",
                    "Taxa_Cartao_Pct": "0%",
                    "Custo_Cartao": 0.0,
                    "Total_PIX": 0.0,
                    "Total_Cartao": 0.0,
                    "Status": "Ativo",
                }
                df_proc = pd.concat(
                    [df_proc, pd.DataFrame([novo_p])], ignore_index=True
                )
                df_proc = recalcular_procedimentos_df(
                    df_proc,
                    df_mat_ref,
                    aluguel_consulta,
                    imposto_geral,
                    lucro_geral,
                    taxas_cartao,
                )
                write_data("Procedimentos", df_proc)
                st.success("Procedimento cadastrado e recalculado!")
                st.rerun()

    st.markdown("---")
    df_proc_active = (
        df_proc[df_proc["Status"] == "Ativo"]
        if not df_proc.empty
        else pd.DataFrame()
    )
    if not df_proc_active.empty:
        col_fp, col_dp = st.columns([3, 1])
        busca_p = col_fp.text_input(
            "🔍 Filtrar Procedimentos:",
            placeholder="Digite o nome do procedimento...",
        )
        df_p_disp = (
            df_proc_active[
                df_proc_active["Procedimento"].str.contains(
                    busca_p, case=False, na=False
                )
            ]
            if busca_p
            else df_proc_active
        )
        col_dp.download_button(
            "📊 Baixar Excel",
            data=export_to_excel(df_p_disp),
            file_name="procedimentos.xlsx",
            use_container_width=True,
        )

        edited_proc = st.data_editor(
            df_p_disp.drop(columns=["Status"], errors="ignore"),
            column_config={
                "Tipo_Lucro": st.column_config.SelectboxColumn(
                    "Tipo de Lucro",
                    options=[
                        "Percentual Geral",
                        "Percentual Específico",
                        "Valor Fixo",
                    ],
                    required=True,
                ),
                "Lucro_Valor": st.column_config.NumberColumn(
                    "Lucro (Configuração)",
                    help="Exibe o % Geral dinâmico, o % Específico digitado ou o Valor Fixo em R$.",
                ),
                "Lucro_Calculado_RS": st.column_config.NumberColumn(
                    "Lucro Final (R$)",
                    help="Resultado financeiro em R$ obtido após o cálculo.",
                    disabled=True,
                ),
            },
            use_container_width=True,
            key="editor_proc",
        )

        if st.button("💾 Salvar Alterações e Recalcular Preços"):
            for idx, row in edited_proc.iterrows():
                p_id = str(row["ID"]).strip()
                mask = df_proc["ID"].astype(str).str.strip() == p_id
                df_proc.loc[mask, "Procedimento"] = row["Procedimento"]
                df_proc.loc[mask, "Qtd_Consultas"] = row["Qtd_Consultas"]
                df_proc.loc[mask, "Tipo_Lucro"] = row["Tipo_Lucro"]
                df_proc.loc[mask, "Lucro_Valor"] = row["Lucro_Valor"]
                df_proc.loc[mask, "Parcelas"] = row["Parcelas"]

            df_proc = recalcular_procedimentos_df(
                df_proc,
                df_mat_ref,
                aluguel_consulta,
                imposto_geral,
                lucro_geral,
                taxas_cartao,
            )
            write_data("Procedimentos", df_proc)
            st.success("Alterações salvas e precificação recalculada!")
            st.rerun()

        st.markdown("---")
        cp_del1, cp_del2 = st.columns([3, 1])
        proc_del = cp_del1.selectbox(
            "Remover Procedimento:",
            options=df_proc_active["Procedimento"].tolist(),
            key="sel_del_proc",
        )
        if cp_del2.button("🗑️ Mover Procedimento para Lixeira"):
            mask = (
                df_proc["Procedimento"].astype(str).str.strip()
                == str(proc_del).strip()
            )
            df_proc.loc[mask, "Status"] = "Excluido"
            write_data("Procedimentos", df_proc)
            st.warning("Procedimento movido para a lixeira!")
            st.rerun()


# ------------------------------------------
# TAB 4: AGENDA
# ------------------------------------------
with tab_agenda:
    st.subheader("📅 Agendamentos de Consultas")
    df_agenda = read_data("Agenda", AGENDA_COLS)
    df_pac_ref = read_data("Pacientes", PAC_COLS)
    df_proc_ref = read_data("Procedimentos", PROC_COLS)

    with st.expander("➕ Novo Agendamento", expanded=False):
        with st.form("form_agenda"):
            a1, a2, a3 = st.columns(3)
            data_ag = a1.date_input("Data")
            hora_ag = a2.time_input("Horário")

            pacs_list = (
                df_pac_ref[df_pac_ref["Status"] == "Ativo"]["Nome"].tolist()
                if not df_pac_ref.empty
                else []
            )
            pac_sel = a3.selectbox("Paciente", options=pacs_list or [""])

            a4, a5, a6 = st.columns(3)
            procs_list = (
                df_proc_ref[df_proc_ref["Status"] == "Ativo"][
                    "Procedimento"
                ].tolist()
                if not df_proc_ref.empty
                else []
            )
            proc_sel = a4.selectbox("Procedimento", options=procs_list or [""])

            val_sug = 0.0
            if proc_sel and not df_proc_ref.empty:
                match_p = df_proc_ref[
                    df_proc_ref["Procedimento"] == proc_sel
                ]
                if not match_p.empty:
                    val_sug = float(match_p["Total_PIX"].values[0])

            val_cobrado = a5.number_input(
                "Valor Cobrado (R$)", value=val_sug, step=10.0
            )
            forma_pag = a6.selectbox(
                "Forma de Pagamento", ["PIX", "Cartão de Crédito", "Dinheiro"]
            )

            if st.form_submit_button("Agendar Consulta"):
                novo_id = len(df_agenda) + 1
                novo_ag = {
                    "ID": novo_id,
                    "Data": str(data_ag),
                    "Horario": str(hora_ag),
                    "Paciente": pac_sel,
                    "Procedimento": proc_sel,
                    "Valor_Cobrado": val_cobrado,
                    "Forma_Pagamento": forma_pag,
                    "Status_Agendamento": "Agendado",
                    "Status": "Ativo",
                }
                df_agenda = pd.concat(
                    [df_agenda, pd.DataFrame([novo_ag])], ignore_index=True
                )
                write_data("Agenda", df_agenda)
                st.success("Consulta agendada!")
                st.rerun()

    st.markdown("---")
    df_ag_active = (
        df_agenda[df_agenda["Status"] == "Ativo"]
        if not df_agenda.empty
        else pd.DataFrame()
    )
    if not df_ag_active.empty:
        edited_ag = st.data_editor(
            df_ag_active.drop(columns=["Status"], errors="ignore"),
            column_config={
                "Status_Agendamento": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Agendado", "Concluído", "Cancelado"],
                    required=True,
                )
            },
            use_container_width=True,
            key="editor_ag",
        )

        if st.button("💾 Salvar Alterações na Agenda"):
            for idx, row in edited_ag.iterrows():
                ag_id = str(row["ID"]).strip()
                mask = df_agenda["ID"].astype(str).str.strip() == ag_id
                df_agenda.loc[mask, "Status_Agendamento"] = row[
                    "Status_Agendamento"
                ]
                df_agenda.loc[mask, "Valor_Cobrado"] = row["Valor_Cobrado"]

            write_data("Agenda", df_agenda)
            st.success("Agenda atualizada!")
            st.rerun()


# ------------------------------------------
# TAB 5: PACIENTES
# ------------------------------------------
with tab_pac:
    st.subheader("👥 Cadastro de Pacientes")
    df_pac = read_data("Pacientes", PAC_COLS)

    with st.expander("➕ Cadastrar Novo Paciente", expanded=False):
        with st.form("form_pac"):
            p1, p2 = st.columns(2)
            nome_pac = p1.text_input("Nome Completo*")
            cpf_pac = p2.text_input("CPF")

            p3, p4 = st.columns(2)
            tel_pac = p3.text_input("Telefone / WhatsApp")
            email_pac = p4.text_input("E-mail")

            if st.form_submit_button("Cadastrar Paciente"):
                novo_id = len(df_pac) + 1
                novo_p = {
                    "ID": novo_id,
                    "Nome": nome_pac,
                    "CPF": cpf_pac,
                    "Telefone": tel_pac,
                    "Email": email_pac,
                    "Historico_Procedimentos": "",
                    "Status": "Ativo",
                }
                df_pac = pd.concat(
                    [df_pac, pd.DataFrame([novo_p])], ignore_index=True
                )
                write_data("Pacientes", df_pac)
                st.success("Paciente cadastrado com sucesso!")
                st.rerun()

    st.markdown("---")
    df_pac_active = (
        df_pac[df_pac["Status"] == "Ativo"]
        if not df_pac.empty
        else pd.DataFrame()
    )
    if not df_pac_active.empty:
        edited_pac = st.data_editor(
            df_pac_active.drop(columns=["Status"], errors="ignore"),
            use_container_width=True,
            key="editor_pac",
        )

        if st.button("💾 Salvar Pacientes"):
            for idx, row in edited_pac.iterrows():
                pid = str(row["ID"]).strip()
                mask = df_pac["ID"].astype(str).str.strip() == pid
                df_pac.loc[mask, "Nome"] = row["Nome"]
                df_pac.loc[mask, "CPF"] = row["CPF"]
                df_pac.loc[mask, "Telefone"] = row["Telefone"]
                df_pac.loc[mask, "Email"] = row["Email"]

            write_data("Pacientes", df_pac)
            st.success("Lista de pacientes atualizada!")
            st.rerun()


# ------------------------------------------
# TAB 6: CAIXA / LIVRO CAIXA
# ------------------------------------------
with tab_caixa:
    st.subheader("💵 Livro Caixa e Fluxo Financeiro")
    df_caixa = read_data("Caixa", CAIXA_COLS)

    with st.expander("➕ Lançar Movimentação Financeira", expanded=False):
        with st.form("form_caixa"):
            cx1, cx2, cx3 = st.columns(3)
            data_cx = cx1.date_input("Data")
            tipo_cx = cx2.selectbox("Tipo", ["Entrada", "Saída"])
            cat_cx = cx3.selectbox(
                "Categoria",
                [
                    "Procedimentos",
                    "Materiais",
                    "Aluguel",
                    "Impostos",
                    "Outros",
                ],
            )

            cx4, cx5 = st.columns([2, 1])
            desc_cx = cx4.text_input("Descrição")
            val_cx = cx5.number_input(
                "Valor (R$)", min_value=0.0, step=10.0
            )

            if st.form_submit_button("Lançar no Caixa"):
                novo_id = len(df_caixa) + 1
                novo_cx = {
                    "ID": novo_id,
                    "Data": str(data_cx),
                    "Tipo": tipo_cx,
                    "Categoria": cat_cx,
                    "Descricao": desc_cx,
                    "Valor": val_cx,
                    "Status": "Ativo",
                }
                df_caixa = pd.concat(
                    [df_caixa, pd.DataFrame([novo_cx])], ignore_index=True
                )
                write_data("Caixa", df_caixa)
                st.success("Lançamento efetuado!")
                st.rerun()

    st.markdown("---")
    df_cx_active = (
        df_caixa[df_caixa["Status"] == "Ativo"]
        if not df_caixa.empty
        else pd.DataFrame()
    )

    if not df_cx_active.empty:
        # Métricas resumidas
        entradas = df_cx_active[df_cx_active["Tipo"] == "Entrada"][
            "Valor"
        ].astype(float).sum()
        saidas = df_cx_active[df_cx_active["Tipo"] == "Saída"]["Valor"].astype(
            float
        ).sum()
        saldo = entradas - saidas

        m1, m2, m3 = st.columns(3)
        m1.metric("🟢 Entradas Totais", f"R$ {entradas:,.2f}")
        m2.metric("🔴 Saídas Totais", f"R$ {saidas:,.2f}")
        m3.metric(
            "🔵 Saldo Atual",
            f"R$ {saldo:,.2f}",
            delta=f"R$ {saldo:,.2f}",
        )

        st.markdown("---")
        st.dataframe(
            df_cx_active.drop(columns=["Status"], errors="ignore"),
            use_container_width=True,
        )


# ------------------------------------------
# TAB 7: LIXEIRA (RESTAURAÇÃO DE DADOS)
# ------------------------------------------
with tab_lixeira:
    st.subheader("🗑️ Lixeira do Sistema")
    cat_del = st.selectbox(
        "Selecione o módulo para visualizar ou restaurar:",
        ["Materiais", "Procedimentos", "Agenda", "Pacientes", "Caixa"],
    )

    target_cols = {
        "Materiais": MAT_COLS,
        "Procedimentos": PROC_COLS,
        "Agenda": AGENDA_COLS,
        "Pacientes": PAC_COLS,
        "Caixa": CAIXA_COLS,
    }[cat_del]

    df_trash_full = read_data(cat_del, target_cols)
    df_trash = (
        df_trash_full[df_trash_full["Status"] == "Excluido"]
        if not df_trash_full.empty
        else pd.DataFrame()
    )

    if not df_trash.empty:
        st.dataframe(df_trash, use_container_width=True)

        col_r1, col_r2 = st.columns([3, 1])
        item_col = (
            "Procedimento"
            if cat_del == "Procedimentos"
            else ("Material" if cat_del == "Materiais" else "ID")
        )
        item_rest = col_r1.selectbox(
            "Selecionar item para restaurar:",
            options=df_trash[item_col].tolist(),
        )

        if col_r2.button("♻️ Restaurar Item"):
            mask = (
                df_trash_full[item_col].astype(str).str.strip()
                == str(item_rest).strip()
            )
            df_trash_full.loc[mask, "Status"] = "Ativo"
            write_data(cat_del, df_trash_full)
            st.success("Item restaurado com sucesso!")
            st.rerun()
    else:
        st.info("Nenhum item excluído neste módulo.")
