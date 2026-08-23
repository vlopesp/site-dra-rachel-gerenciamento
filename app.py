import io
import re
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# FUNÇÕES DE INTEGRAÇÃO COM GOOGLE DRIVE
# ==========================================
def get_drive_service():
    scopes = ['https://www.googleapis.com/auth/drive']
    # Reutiliza as credenciais que já estão no secrets para o gsheets
    credentials_info = st.secrets["connections"]["gsheets"]
    creds = Credentials.from_service_account_info(credentials_info, scopes=scopes)
    return build('drive', 'v3', credentials=creds)

def get_or_create_year_folder(service, parent_id, year_str):
    """Verifica se a pasta do Ano existe. Se não existir, cria automaticamente."""
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
    """Envia o arquivo para a subpasta do ano no Google Drive e retorna o link."""
    try:
        parent_folder_id = st.secrets.get("DRIVE_PARENT_FOLDER_ID", "")
        if not parent_folder_id:
            st.error("ID da pasta do Google Drive não foi configurado em secrets.toml!")
            return ""

        service = get_drive_service()
        year_folder_id = get_or_create_year_folder(service, parent_folder_id, year_str)
        
        # Prepara o arquivo enviado via Streamlit
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
    """Remove caracteres especiais para criação segura de nome de arquivo."""
    text_clean = re.sub(r'[^\w\s-]', '', str(text))
    return text_clean.strip().replace(' ', '_')

# ==========================================
# NOVO LIVRO CAIXA COM ANEXO DE NOTAS (TAB 6)
# ==========================================
# Atualizamos a estrutura de colunas para incluir a URL da nota anexada
CAIXA_COLS = ['ID', 'Data', 'Tipo', 'Categoria', 'Descricao', 'Valor', 'Forma_Pagamento', 'Link_Nota', 'Status']

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
                
                # Processa o upload do comprovante para o Google Drive
                if file_anexo is not None:
                    data_formatada = dt_trans.strftime("%d_%m_%Y")
                    ano_str = str(dt_trans.year)
                    ext = file_anexo.name.split('.')[-1]
                    
                    # Nome exigido: dd_mm_aaaa_(entrada ou saida)_(Categoria)_(forma de pagamento)
                    nome_arquivo = f"{data_formatada}_{tipo_trans}_{sanitize_str(categoria)}_{sanitize_str(forma_pag)}.{ext}"
                    
                    with st.spinner("Enviando nota para o Google Drive..."):
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
        # Métricas do Caixa
        entradas = df_cx_active[df_cx_active['Tipo'] == 'Entrada']['Valor'].astype(float).sum()
        saidas = df_cx_active[df_cx_active['Tipo'] == 'Saida']['Valor'].astype(float).sum()
        saldo = entradas - saidas

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("🟢 Total Entradas", f"R$ {entradas:,.2f}")
        mc2.metric("🔴 Total Saídas", f"R$ {saidas:,.2f}")
        mc3.metric("⚖️ Saldo do Período", f"R$ {saldo:,.2f}")

        st.markdown("---")
        st.write("### 📋 Extrato de Lançamentos")
        
        # Exibe a tabela de lançamentos com o link clicável da nota
        st.dataframe(
            df_cx_active.drop(columns=['Status'], errors='ignore'),
            column_config={
                "Link_Nota": st.column_config.LinkColumn(
                    "Nota Anexada",
                    help="Clique para visualizar o arquivo no Google Drive",
                    validate="^https://",
                    display_text="📄 Ver Nota no Drive"
                )
            },
            use_container_width=True
        )
