import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime
import os

# Importação da Biblioteca Oficial do Google GenAI
try:
    from google import genai
    GOOGLE_GENAI_DISPONIVEL = True
except ImportError:
    GOOGLE_GENAI_DISPONIVEL = False

try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

st.set_page_config(
    page_title="Construtora Mads - Gestão e Orçamentos", 
    page_icon="🏗️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- SISTEMA DE LOGIN COM SENHA ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center; color: #1E3A8A;'>🏗️ Construtora Mads — Acesso Restrito</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #4B5563;'>Insira suas credenciais para acessar o sistema de gestão.</p>", unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        with st.form("form_login"):
            usuario = st.text_input("Usuário:")
            senha = st.text_input("Senha:", type="password")
            botao_login = st.form_submit_button("Entrar no Sistema")
            
            if botao_login:
                if usuario == "admin" and senha == "mads2026":
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos!")
    st.stop()

# --- ESTILOS VISUAIS ---
st.markdown("""
    <style>
        .main-header { font-size: 28px; font-weight: 700; color: #1E3A8A; margin-bottom: 0px; }
        .sub-header { font-size: 16px; color: #4B5563; margin-bottom: 20px; }
        .stButton>button { width: 100%; background-color: #2563EB; color: white; font-weight: bold; border-radius: 6px; }
        .stButton>button:hover { background-color: #1D4ED8; color: white; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🏗️ Construtora Mads — Gestão Financeira e Orçamentos</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Controle unificado de diárias, fornecedores, histórico, lembretes, reembolsos e Assistente IA com Inteligência Real.</p>', unsafe_allow_html=True)

def inicializar_banco():
    conexao = sqlite3.connect("banco_obras.db")
    cursor = conexao.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            empreendimento TEXT,
            categoria TEXT,
            nome TEXT,
            cargo TEXT,
            valor REAL,
            tipo_pix TEXT,
            chave_pix TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lembretes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_criacao TEXT,
            texto_lembrete TEXT,
            status TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE lancamentos ADD COLUMN categoria TEXT")
    except:
        pass
    conexao.commit()
    conexao.close()

inicializar_banco()

VALORES_PADRAO = {
    "pedreiro": 250.0,
    "pintor": 250.0,
    "meio oficial": 200.0,
    "ajudante": 150.0
}

def processar_e_salvar_lancamentos(texto_mensagem, empreendimento_nome, data_selecionada, tipo_lancamento):
    linhas = texto_mensagem.strip().split("\n")
    registros_inseridos = 0
    dados_processados = []

    conexao = sqlite3.connect("banco_obras.db")
    cursor = conexao.cursor()
    data_str = data_selecionada.strftime("%d/%m/%Y")

    ultima_chave_encontrada = "Não informada"

    for linha in linhas:
        linha = linha.strip()
        if not linha: 
            continue
        
        linha_lower = linha.lower()

        if "equipe" in linha_lower and len(linha.split()) <= 2:
            continue

        if "pix" in linha_lower or "@" in linha_lower or re.match(r'^\d{10,}$', re.sub(r'\D', '', linha)):
            partes_linha = linha.split()
            for p in partes_linha:
                if "@" in p or len(re.sub(r'\D', '', p)) >= 10:
                    ultima_chave_encontrada = p.replace("(", "").replace(")", "").strip()
                    break
            continue

        partes = linha.split()
        if not partes: 
            continue

        nome = partes[0].capitalize()
        if nome.lower() == "equipe":
            continue

        cargo_encontrado = "Ajudante"
        valor = VALORES_PADRAO["ajudante"]

        if tipo_lancamento == "Equipe / Mão de Obra":
            for cargo_chave, val in VALORES_PADRAO.items():
                if cargo_chave in linha_lower:
                    cargo_encontrado = cargo_chave.capitalize()
                    valor = val
                    break

            chave_pix_linha = ultima_chave_encontrada
            for parte in partes[1:]:
                if "@" in parte or re.match(r'^\d{10,}$', re.sub(r'\D', '', parte)):
                    chave_pix_linha = parte.replace("(", "").replace(")", "").strip()
                    ultima_chave_encontrada = chave_pix_linha
                    break

            if chave_pix_linha == "Não informada":
                cursor.execute("SELECT chave_pix FROM lancamentos WHERE nome = ? AND chave_pix != 'Não informada' ORDER BY id DESC LIMIT 1", (nome,))
                resultado_pix = cursor.fetchone()
                if resultado_pix: 
                    chave_pix_linha = resultado_pix[0]
        
        else:  
            cargo_encontrado = "Fornecedor / Material"
            match_valor = re.search(r'(?:R\$)?\s*([\d.]+,\d{2})', linha)
            if match_valor:
                valor_str = match_valor.group(1).replace(".", "").replace(",", ".")
                try: valor = float(valor_str)
                except: valor = 0.0
            
            chave_pix_linha = ultima_chave_encontrada
            for parte in partes[1:]:
                if "@" in parte or re.match(r'^\d{10,}$', re.sub(r'\D', '', parte)):
                    chave_pix_linha = parte.replace("(", "").replace(")", "").strip()
                    ultima_chave_encontrada = chave_pix_linha
                    break

        tipo_pix = "Outro"
        if "@" in chave_pix_linha: 
            tipo_pix = "E-mail"
        elif re.match(r'^\d{11}$|^\d{14}$', re.sub(r'\D', '', chave_pix_linha)): 
            tipo_pix = "CPF/CNPJ"
        elif len(re.sub(r'\D', '', chave_pix_linha)) >= 10: 
            tipo_pix = "Celular"

        if valor > 0:
            cursor.execute("""
                INSERT INTO lancamentos (data, empreendimento, categoria, nome, cargo, valor, tipo_pix, chave_pix)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data_str, empreendimento_nome, tipo_lancamento, nome, cargo_encontrado, valor, tipo_pix, chave_pix_linha))
            
            registros_inseridos += 1
            dados_processados.append({
                "Data": data_str, "Categoria": tipo_lancamento, "Nome / Fornecedor": nome,
                "Detalhe / Cargo": cargo_encontrado, "Valor a Pagar": f"R$ {valor:.2f}", "Chave Pix": chave_pix_linha
            })

    conexao.commit()
    conexao.close()
    return registros_inseridos, pd.DataFrame(dados_processados)

def interpretar_e_executar_correcao(texto):
    texto_lower = texto.lower()
    conexao = sqlite3.connect("banco_obras.db")
    cursor = conexao.cursor()
    
    if "alterar" in texto_lower or "mude" in texto_lower or "mudar" in texto_lower or "atualize" in texto_lower:
        match_valor = re.search(r'(?:para|de)\s*(?:r\$)?\s*([\d.]+,\d{2}|[\d]+)', texto_lower)
        match_nome = re.search(r'(?:do|da|para o|para a)\s+([a-zA-ZÀ-ÿ]+)', texto_lower)
        
        if match_valor and match_nome:
            val_str = match_valor.group(1).replace(".", "").replace(",", ".")
            try:
                novo_valor = float(val_str)
                nome_alvo = match_nome.group(1).capitalize()
                
                cursor.execute("""
                    UPDATE lancamentos 
                    SET valor = ? 
                    WHERE id = (SELECT id FROM lancamentos WHERE nome LIKE ? ORDER BY id DESC LIMIT 1)
                """, (novo_valor, f"%{nome_alvo}%"))
                
                if cursor.rowcount > 0:
                    conexao.commit()
                    conexao.close()
                    return f"Pronto, Joel! Atualizei o valor do lançamento de **{nome_alvo}** para **R$ {novo_valor:,.2f}** com sucesso! ✅"
            except Exception:
                pass

    if "apague" in texto_lower or "exclua" in texto_lower or "remover" in texto_lower or "retire" in texto_lower:
        match_nome = re.search(r'(?:do|da|o|a)\s+([a-zA-ZÀ-ÿ]+)', texto_lower)
        if match_nome:
            nome_alvo = match_nome.group(1).capitalize()
            cursor.execute("""
                DELETE FROM lancamentos 
                WHERE id = (SELECT id FROM lancamentos WHERE nome LIKE ? ORDER BY id DESC LIMIT 1)
            """, (f"%{nome_alvo}%",))
            if cursor.rowcount > 0:
                conexao.commit()
                conexao.close()
                return f"Pronto, Joel! Retirei o **{nome_alvo}** da lista. 🗑️"

    conexao.close()
    return None

def salvar_lembrete(texto):
    conexao = sqlite3.connect("banco_obras.db")
    cursor = conexao.cursor()
    data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute("INSERT INTO lembretes (data_criacao, texto_lembrete, status) VALUES (?, ?, ?)", (data_hoje, texto, "Pendente"))
    conexao.commit()
    conexao.close()

def carregar_todos_dados():
    conexao = sqlite3.connect("banco_obras.db")
    try:
        df = pd.read_sql_query("SELECT id, data, empreendimento, categoria, nome, cargo, valor, tipo_pix, chave_pix FROM lancamentos", conexao)
        df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values(by=['data_dt', 'id'], ascending=[False, False]).drop(columns=['data_dt'])
    except:
        df = pd.DataFrame(columns=["id", "data", "empreendimento", "categoria", "nome", "cargo", "valor", "tipo_pix", "chave_pix"])
    conexao.close()
    return df

def gerar_pdf_reembolso(emitente_nome, emitente_cnpj, emitente_end, destinatario_nome, destinatario_cnpj, destinatario_end, vencimento, referencia, itens_df, banco_info, imagem_path=None):
    pdf_path = "nota_debito_reembolso.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    titulo_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.black)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=colors.black)
    
    story.append(Paragraph("<b>NOTA DÉBITO / RECIBO FATURA</b>", titulo_style))
    story.append(Spacer(1, 5))
    
    data_emissao = datetime.now().strftime('%d/%m/%Y')
    story.append(Paragraph(f"<b>Emissão:</b> {data_emissao} | <b>Vencimento:</b> {vencimento} | <b>Referência:</b> {referencia}", sub_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>Emitente e Destinatário</b>", ParagraphStyle('Sec', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.black)))
    story.append(Spacer(1, 4))
    
    tabela_partes = Table([
        [Paragraph(f"<b>Emitente:</b> {emitente_nome}", sub_style), Paragraph(f"<b>Destinatário:</b> {destinatario_nome}", sub_style)],
        [Paragraph(f"<b>CNPJ:</b> {emitente_cnpj}", sub_style), Paragraph(f"<b>CNPJ:</b> {destinatario_cnpj}", sub_style)],
        [Paragraph(f"{emitente_end}", sub_style), Paragraph(f"{destinatario_end}", sub_style)]
    ], colWidths=[270, 270])
    tabela_partes.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#000000')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(tabela_partes)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("<b>Itens</b>", ParagraphStyle('Sec2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.black)))
    story.append(Spacer(1, 4))
    
    tabela_itens_dados = [["Descrição", "Quant.", "Unit. (R$)", "Total (R$)"]]
    total_geral = 0.0
    for _, row in itens_df.iterrows():
        tot = row['quant'] * row['unit']
        total_geral += tot
        tabela_itens_dados.append([
            str(row['descricao']).upper(),
            str(row['quant']),
            f"{row['unit']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            f"{tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        ])
    
    tabela_itens_dados.append(["VALOR TOTAL A PAGAR:", "", "", f"<b>{total_geral:,.2f}</b>".replace(",", "X").replace(".", ",").replace("X", ".")])
    
    t_itens = Table(tabela_itens_dados, colWidths=[250, 60, 110, 120])
    t_itens.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#000000')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F0F0F0')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F0F0F0')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
    ]))
    story.append(t_itens)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph(f"<b>Dados Bancários ({banco_info})</b>", ParagraphStyle('Sec3', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.black)))
    story.append(Spacer(1, 4))
    
    banco_texto = f"""
    • <b>Agência:</b> 0001<br/>
    • <b>Conta:</b> 5896132-9<br/>
    • <b>Favorecido:</b> {emitente_nome}<br/>
    • <b>CNPJ:</b> {emitente_cnpj}
    """
    story.append(Paragraph(banco_texto, sub_style))
    
    if imagem_path and os.path.exists(imagem_path):
        story.append(Spacer(1, 30))
        story.append(Paragraph("<b>Anexo: Comprovante / Nota Fiscal</b>", titulo_style))
        story.append(Spacer(1, 10))
        img = RLImage(imagem_path, width=450, height=600)
        img.hAlign = 'CENTER'
        story.append(img)

    doc.build(story)
    return pdf_path

def gerar_pdf_orcamento(obra_nome, solicitante, objeto, itens_df, percentual_imposto):
    pdf_path = "orcamento_oficial.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.black)
    sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.black)
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.black)
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.black)
    red_bold = ParagraphStyle('RedBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.red)
    
    story.append(Paragraph("MADS CONSTRUÇÕES", header_style))
    story.append(Paragraph(f"OBRA: {obra_nome.upper()}", sub_style))
    story.append(Paragraph(f"SOLICITANTE: {solicitante.upper()}", sub_style))
    story.append(Paragraph(f"OBJETO: {objeto.upper()}", sub_style))
    story.append(Spacer(1, 8))
    
    tabela_dados = [[
        Paragraph("ITEM", cell_bold), 
        Paragraph("DESCRIÇÃO", cell_bold), 
        Paragraph("UNID.", cell_bold), 
        Paragraph("QUANT.", cell_bold), 
        Paragraph("MATERIAL", cell_bold), 
        Paragraph("MÃO DE OBRA", cell_bold), 
        Paragraph("MAT/MO", cell_bold), 
        Paragraph("PREÇO TOTAL (R$)", cell_bold)
    ]]
    
    total_custo_geral = 0.0
    
    for idx, row in enumerate(itens_df.iterrows(), start=1):
        _, r = row
        mat = float(r['material']) if 'material' in r else 0.0
        mo = float(r['mao_obra']) if 'mao_obra' in r else 0.0
        quant = float(r['quant']) if 'quant' in r else 1.0
        tot_parcial = (mat + mo) * quant
        total_custo_geral += tot_parcial
        
        tabela_dados.append([
            Paragraph(str(idx), cell_style),
            Paragraph(str(r['descricao']).upper(), cell_style),
            Paragraph(str(r['unid']).upper(), cell_style),
            Paragraph(f"{quant:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), cell_style),
            Paragraph(f"R$ {mat:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), cell_style),
            Paragraph(f"R$ {mo:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), cell_style),
            Paragraph("", cell_style),
            Paragraph(f"R$ {tot_parcial:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), cell_style)
        ])
    
    valor_impostos = total_custo_geral * (percentual_imposto / 100.0)
    valor_total_final = total_custo_geral + valor_impostos
    
    tabela_dados.append([
        Paragraph("", cell_style), Paragraph("TOTAL CUSTO", red_bold), Paragraph("", cell_style), Paragraph("", cell_style),
        Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
        Paragraph(f"R$ {total_custo_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), red_bold)
    ])
    
    tabela_dados.append([
        Paragraph("", cell_style), Paragraph(f"TOTAL DE CUSTO + IMPOSTOS E LUCRO ({percentual_imposto:.1f}%)", red_bold), Paragraph("", cell_style), Paragraph("", cell_style),
        Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
        Paragraph(f"R$ {valor_total_final:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), red_bold)
    ])
    
    t_orc = Table(tabela_dados, colWidths=[35, 290, 45, 55, 80, 80, 65, 95])
    t_orc.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-3), 0.5, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('BACKGROUND', (0,-2), (-1,-1), colors.HexColor('#F9FAFB')),
        ('SPAN', (1,-2), (6,-2)),
        ('SPAN', (1,-1), (6,-1)),
    ]))
    
    story.append(t_orc)
    doc.build(story)
    return pdf_path

# --- MENU LATERAL ---
st.sidebar.markdown("### 🧭 Menu Principal")
opcao_menu = st.sidebar.radio("Escolha a opção:", [
    "🤖 Assistente Administrativa & Voz",
    "📥 Cadastrar Lançamentos", 
    "📌 Gerenciar Lembretes",
    "📄 Folha de Rosto Reembolso",
    "📅 Consultar por Data", 
    "🔍 Pesquisar por Profissional/Empresa", 
    "📊 Relatório Geral e Exportação",
    "🗑️ Gerenciar e Limpar Duplicadas",
    "📄 Gerador de Orçamento PDF"
])

if st.sidebar.button("🔒 Sair do Sistema"):
    st.session_state.autenticado = False
    st.rerun()

st.divider()

df_completo = carregar_todos_dados()

# --- ABA 1: ASSISTENTE ADMINISTRATIVA & VOZ ---
if opcao_menu == "🤖 Assistente Administrativa & Voz":
    st.subheader("🤖 Assistente Administrativa Virtual da Construtora Mads")
    st.markdown("Estou pronta para gerenciar sua equipe, organizar pagamentos e exibir tabelas detalhadas direto no chat!")

    if "mensagens_chat" not in st.session_state:
        st.session_state.mensagens_chat = [
            {"role": "assistant", "content": "Olá, Joel! Tudo bem? Estou pronta para te ajudar na Construtora Mads. O que mandas para hoje?"}
        ]

    for msg in st.session_state.mensagens_chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    if prompt_usuario := st.chat_input("Converse livremente com a assistente..."):
        st.session_state.mensagens_chat.append({"role": "user", "content": prompt_usuario})
        with st.chat_message("user"):
            st.markdown(prompt_usuario)

        prompt_lower = prompt_usuario.lower()
        resposta = ""

        resposta_correcao = interpretar_e_executar_correcao(prompt_usuario)

        if resposta_correcao:
            resposta = resposta_correcao
            df_completo = carregar_todos_dados()
        elif "lembre" in prompt_lower or "lembrar" in prompt_lower or "anota aí" in prompt_lower:
            texto_lembrete = prompt_usuario.replace("me lembre de", "").replace("lembre-se de", "").replace("anota aí", "").strip()
            salvar_lembrete(texto_lembrete)
            resposta = f"Lembrete anotado com sucesso: *'{texto_lembrete}'*. Já salvei na sua lista de pendências! 📌"
        elif any(carg in prompt_lower for carg in ["pedreiro", "ajudante", "pintor", "meio oficial"]) and len(prompt_usuario.split()) > 3:
            qtd, df_res = processar_e_salvar_lancamentos(prompt_usuario, "Obra Bragança", datetime.now(), "Equipe / Mão de Obra")
            if qtd > 0:
                resposta = f"Pronto, Joel! Identifiquei **{qtd} profissionais** e já salvei os lançamentos. Aqui está a lista atualizada:<br><br>"
                df_recente = carregar_todos_dados().head(qtd)
                tabela_html = df_recente[['nome', 'cargo', 'valor', 'chave_pix']].rename(
                    columns={'nome': 'Nome', 'cargo': 'Função', 'valor': 'Valor (R$)', 'chave_pix': 'Chave / Dado Pagamento'}
                ).to_html(index=False, classes='table table-striped')
                resposta += tabela_html
            else:
                resposta = "Tentei processar a lista, mas não consegui identificar os registros com clareza."
        elif "lista" in prompt_lower or "pagamento" in prompt_lower or "relatório" in prompt_lower or "quanto" in prompt_lower:
            df_recente = carregar_todos_dados().head(15)
            total_geral = df_completo['valor'].sum() if not df_completo.empty else 0.0
            resposta = f"Aqui está a listagem recente dos registros cadastrados (Total acumulado geral: **R$ {total_geral:,.2f}**):<br><br>"
            tabela_html = df_recente[['nome', 'cargo', 'valor', 'chave_pix']].rename(
                columns={'nome': 'Nome', 'cargo': 'Função', 'valor': 'Valor (R$)', 'chave_pix': 'Chave / Dado Pagamento'}
            ).to_html(index=False, classes='table table-striped')
            resposta += tabela_html
        else:
            if GOOGLE_GENAI_DISPONIVEL:
                try:
                    api_key_val = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else os.environ.get("GEMINI_API_KEY", "")
                    client = genai.Client(api_key=api_key_val) if api_key_val else genai.Client()

                    total_reg = len(df_completo)
                    total_valor = df_completo['valor'].sum() if not df_completo.empty else 0.0
                    dados_resumo = f"Total de lançamentos: {total_reg}. Valor acumulado: R$ {total_valor:.2f}."
                    
                    prompt_sistema = f"""
                    Você é a Assistente Administrativa Virtual experiente da Construtora Mads. O seu chefe é o Joel Japin.
                    Status resumido do banco de dados: {dados_resumo}
                    Responda sempre com naturalidade, presteza, foco profissional em construção civil, amizade e precisão, chamando-o pelo nome (Joel).
                    """
                    
                    response = client.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=f"{prompt_sistema}\n\nMensagem do Joel: {prompt_usuario}"
                    )
                    resposta = response.text
                except Exception as e:
                    resposta = f"Compreendi sua solicitação, Joel: *'{prompt_usuario}'*."
            else:
                resposta = f"Compreendi sua ideia, Joel: *'{prompt_usuario}'*."

        st.session_state.mensagens_chat.append({"role": "assistant", "content": resposta})
        with st.chat_message("assistant"):
            st.markdown(resposta, unsafe_allow_html=True)

# --- ABA 2: CADASTRAR LANÇAMENTOS ---
elif opcao_menu == "📥 Cadastrar Lançamentos":
    st.subheader("📥 Novo Lançamento (Equipe ou Materiais)")
    with st.form("form_cadastro"):
        col1, col2, col3 = st.columns(3)
        with col1: nome_obra = st.text_input("Nome da Obra:", value="Obra Bragança")
        with col2: data_obra = st.date_input("Data do Lançamento:", value=datetime.now())
        with col3: tipo_lancamento = st.selectbox("Tipo de Lançamento:", ["Equipe / Mão de Obra", "Material / Fornecedor"])

        if tipo_lancamento == "Equipe / Mão de Obra":
            placeholder_texto = "Cole sua equipe aqui (ex: Fabiano pedreiro, Paulo pedreiro, etc.)"
            label_texto = "Cole a equipe abaixo (Nome + Cargo + Pix opcional):"
        else:
            placeholder_texto = "Exemplos:\nLoja_do_Gesso R$ 450,00 12345678000199\nDepósito_Sao_Judas R$ 1.200,00 contato@deposito.com"
            label_texto = "Cole as compras / fornecedores (Fornecedor + R$ Valor + Chave Pix):"

        texto_copiado = st.text_area(label_texto, height=220, placeholder=placeholder_texto)
        botao_enviar = st.form_submit_button("Processar e Gerar Relatório de Pagamento")
        
        if botao_enviar:
            if texto_copiado.strip():
                qtd, df_relatorio = processar_e_salvar_lancamentos(texto_copiado, nome_obra, data_obra, tipo_lancamento)
                if qtd > 0:
                    st.success(f"Sucesso, Joel! {qtd} registro(s) processado(s).")
                    st.dataframe(df_relatorio, use_container_width=True)
                else: st.warning("Nenhum lançamento válido identificado.")

# --- ABA 3: GERENCIAR LEMBRETES ---
elif opcao_menu == "📌 Gerenciar Lembretes":
    st.subheader("📌 Seus Lembretes e Tarefas Pendentes")
    
    with st.form("form_novo_lembrete"):
        novo_lembrete_texto = st.text_input("Novo Lembrete:")
        botao_add_lembrete = st.form_submit_button("Salvar Lembrete")
        if botao_add_lembrete and novo_lembrete_texto.strip():
            salvar_lembrete(novo_lembrete_texto)
            st.success("Lembrete salvo com sucesso!")

    conexao = sqlite3.connect("banco_obras.db")
    df_lembretes = pd.read_sql_query("SELECT id, data_criacao, texto_lembrete, status FROM lembretes", conexao)
    conexao.close()

    if not df_lembretes.empty:
        st.dataframe(df_lembretes, use_container_width=True)
        id_apagar = st.number_input("Digite o ID do lembrete concluído para apagar:", min_value=0, step=1)
        if st.button("🗑️ Marcar como Concluído / Apagar Lembrete"):
            if id_apagar > 0:
                conexao = sqlite3.connect("banco_obras.db")
                cursor = conexao.cursor()
                cursor.execute("DELETE FROM lembretes WHERE id = ?", (id_apagar,))
                conexao.commit()
                conexao.close()
                st.success("Lembrete removido com sucesso!")
                st.rerun()
    else:
        st.info("Nenhum lembrete cadastrado no momento.")

# --- ABA 4: FOLHA DE ROSTO REEMBOLSO ---
elif opcao_menu == "📄 Folha de Rosto Reembolso":
    st.subheader("📄 Gerador de Nota de Débito / Recibo Fatura para Reembolso")
    
    if not REPORTLAB_DISPONIVEL:
        st.error("A biblioteca 'reportlab' não está instalada.")
    else:
        if 'df_reembolso' not in st.session_state:
            st.session_state.df_reembolso = pd.DataFrame(columns=["descricao", "quant", "unit"])

        with st.form("form_reembolso_dados"):
            st.markdown("### 🏢 Dados do Emitente (Sua Empresa)")
            c1, c2 = st.columns(2)
            with c1:
                emitente_nome = st.text_input("Nome do Emitente:", value="MADS CONSTRUÇÕES")
                emitente_cnpj = st.text_input("CNPJ do Emitente:", value="60.017.250/0001-66")
            with c2:
                emitente_end = st.text_input("Endereço do Emitente:", value="Rua Jaupaci, 553, Vl Paulistano, SP")
            
            st.markdown("### 🏛️ Dados do Destinatário (Cliente)")
            c3, c4 = st.columns(2)
            with c3:
                destinatario_nome = st.text_input("Nome do Destinatário (Cliente):", value="ADISER COMÉRCIO")
                destinatario_cnpj = st.text_input("CNPJ do Destinatário:", value="11.377.588/0040-20")
            with c4:
                destinatario_end = st.text_input("Endereço do Destinatário:", value="Av. dos Imigrantes, 1427, Bragança Paulista, SP")

            st.markdown("### 📅 Informações do Documento")
            c5, c6, c7 = st.columns(3)
            with c5:
                vencimento = st.text_input("Data de Vencimento:", value="06/07/2026")
            with c6:
                referencia = st.text_input("Referência:", value="Reembolso Nota Fiscal 21256")
            with c7:
                banco_info = st.text_input("Banco / Conta Info:", value="Cora SCFI - 403")

            st.markdown("---")
            st.markdown("### ➕ Adicionar Itens / Despesas")
            t_desc = st.text_input("Descrição do Item:", value="Eucatex tiner 5l")
            c_quant = st.number_input("Quantidade:", value=1.0)
            c_unit = st.number_input("Valor Unitário (R$):", value=84.70)
            botao_add_item_reb = st.form_submit_button("➕ Adicionar Item à Lista")

        if botao_add_item_reb:
            novo_item_df = pd.DataFrame([{"descricao": t_desc, "quant": c_quant, "unit": c_unit}])
            st.session_state.df_reembolso = pd.concat([st.session_state.df_reembolso, novo_item_df], ignore_index=True)
            st.success("Item adicionado com sucesso!")

        st.markdown("### Itens Atuais da Nota")
        st.session_state.df_reembolso = st.data_editor(st.session_state.df_reembolso, num_rows="dynamic", use_container_width=True, key="editor_reembolso")

        st.markdown("### 📸 Anexar Foto da Nota Fiscal")
        foto_nota = st.file_uploader("Faça upload da foto da nota fiscal:", type=["png", "jpg", "jpeg"])
        
        caminho_foto_temp = None
        if foto_nota is not None:
            caminho_foto_temp = "temp_nota_fiscal.png"
            with open(caminho_foto_temp, "wb") as f:
                f.write(foto_nota.getbuffer())
            st.image(foto_nota, caption="Pré-visualização da Nota Anexada", width=300)

        if st.button("📥 Gerar PDF Completo"):
            if not st.session_state.df_reembolso.empty:
                pdf_reb = gerar_pdf_reembolso(
                    emitente_nome, emitente_cnpj, emitente_end,
                    destinatario_nome, destinatario_cnpj, destinatario_end,
                    vencimento, referencia, st.session_state.df_reembolso, banco_info, caminho_foto_temp
                )
                st.success("Nota de Débito gerada com sucesso!")
                with open(pdf_reb, "rb") as f_pdf:
                    st.download_button("⬇️ Baixar PDF Completo", data=f_pdf, file_name="Nota_Debito_Reembolso.pdf", mime="application/pdf")
            else:
                st.warning("Adicione pelo menos um item na nota.")

# --- ABA 5: CONSULTAR POR DATA ---
elif opcao_menu == "📅 Consultar por Data":
    st.subheader("📋 Relatório Diário de Pagamentos")
    if not df_completo.empty:
        datas_unicas = df_completo.copy()
        datas_unicas['data_dt'] = pd.to_datetime(datas_unicas['data'], format='%d/%m/%Y', errors='coerce')
        datas_ordenadas = datas_unicas.sort_values(by='data_dt', ascending=False)['data'].unique()
        data_escolhida = st.selectbox("Selecione a data:", datas_ordenadas)
        df_filtrado = df_completo[df_completo["data"] == data_escolhida]
        st.metric(label="💰 Total Geral Gasto no Dia", value=f"R$ {df_filtrado['valor'].sum():.2f}")
        st.dataframe(df_filtrado[["id", "empreendimento", "categoria", "nome", "cargo", "valor", "chave_pix"]], use_container_width=True)
    else:
        st.info("Nenhum lançamento registrado no banco de dados.")

# --- ABA 6: PESQUISAR POR PROFISSIONAL / EMPRESA ---
elif opcao_menu == "🔍 Pesquisar por Profissional/Empresa":
    st.subheader("🔍 Histórico por Profissional ou Fornecedor")
    if not df_completo.empty:
        termo_busca = st.text_input("Digite o nome do profissional ou fornecedor:")
        if termo_busca:
            df_busca = df_completo[df_completo['nome'].str.contains(termo_busca, case=False, na=False)]
            if not df_busca.empty:
                st.success(f"Encontrados {len(df_busca)} registros para '{termo_busca}'.")
                st.metric(label="💵 Total Pago", value=f"R$ {df_busca['valor'].sum():.2f}")
                st.dataframe(df_busca[["id", "data", "empreendimento", "categoria", "nome", "cargo", "valor", "chave_pix"]], use_container_width=True)
            else:
                st.warning("Nenhum registro encontrado com esse nome.")
    else:
        st.info("Banco de dados vazio.")

# --- ABA 7: RELATÓRIO GERAL E EXPORTAÇÃO ---
elif opcao_menu == "📊 Relatório Geral e Exportação":
    st.subheader("📊 Relatório Geral de Lançamentos e Exportação Excel")
    if not df_completo.empty:
        st.metric(label="💰 Valor Total Acumulado Geral", value=f"R$ {df_completo['valor'].sum():.2f}")
        st.dataframe(df_completo, use_container_width=True)

        output = pd.ExcelWriter("relatorio_geral_mads.xlsx", engine='xlsxwriter')
        df_completo.to_excel(output, sheet_name='Lancamentos', index=False)
        output.close()
        
        with open("relatorio_geral_mads.xlsx", "rb") as f_excel:
            st.download_button("📥 Baixar Relatório em Excel (.xlsx)", data=f_excel, file_name="Relatorio_Construtora_Mads.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhum dado cadastrado para exibir.")

# --- ABA 8: GERENCIAR E LIMPAR DUPLICADAS ---
elif opcao_menu == "🗑️ Gerenciar e Limpar Duplicadas":
    st.subheader("🗑️ Gerenciamento e Remoção de Lançamentos e Duplicadas")
    st.markdown("Aqui você pode visualizar todos os IDs dos lançamentos do banco e excluir facilmente qualquer registro duplicado ou errado.")
    
    if not df_completo.empty:
        st.dataframe(df_completo, use_container_width=True)
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            id_remover = st.number_input("Digite o ID exato do lançamento para excluir:", min_value=0, step=1)
            if st.button("🗑️ Excluir Lançamento Selecionado por ID"):
                if id_remover > 0:
                    conexao = sqlite3.connect("banco_obras.db")
                    cursor = conexao.cursor()
                    cursor.execute("DELETE FROM lancamentos WHERE id = ?", (id_remover,))
                    conexao.commit()
                    conexao.close()
                    st.success(f"Lançamento com ID {id_remover} removido com sucesso!")
                    st.rerun()
        with col_ex2:
            st.markdown("### ⚠️ Limpeza Rápida")
            if st.button("🗑️ Excluir Último Registro Inserido"):
                conexao = sqlite3.connect("banco_obras.db")
                cursor = conexao.cursor()
                cursor.execute("DELETE FROM lancamentos WHERE id = (SELECT MAX(id) FROM lancamentos)")
                conexao.commit()
                conexao.close()
                st.success("Último lançamento removido com sucesso!")
                st.rerun()
    else:
        st.info("O banco de dados está vazio.")

# --- ABA 9: GERADOR DE ORÇAMENTO PDF ---
elif opcao_menu == "📄 Gerador de Orçamento PDF":
    st.subheader("📄 Gerador de Orçamento Oficial da Construtora Mads")
    if not REPORTLAB_DISPONIVEL:
        st.error("A biblioteca 'reportlab' não está instalada.")
    else:
        if 'df_orcamento_itens' not in st.session_state:
            st.session_state.df_orcamento_itens = pd.DataFrame(columns=["descricao", "unid", "quant", "material", "mao_obra"])

        with st.form("form_dados_orcamento"):
            c1, c2 = st.columns(2)
            with c1:
                obra_nome_input = st.text_input("Nome da Obra / Projeto:", value="OBRA BK BRAGANÇA PAULISTA")
                solicitante_input = st.text_input("Cliente / Solicitante:", value="EVERSON")
            with c2:
                objeto_input = st.text_input("Objeto do Orçamento:", value="SERVICOS GERAIS")
                percentual_imposto_input = st.number_input("Percentual BDI / Impostos (%)", value=30.0)

            st.markdown("---")
            st.markdown("### Adicionar Etapa / Item ao Orçamento")
            d_item = st.text_input("Descrição do Serviço / Material:", value="ACM VERMELHO")
            d_unid = st.text_input("Unidade (ex: m2, und, vb):", value="M2")
            d_quant = st.number_input("Quantidade:", value=51.0)
            d_mat = st.number_input("Custo Unitário de Material (R$):", value=510.01)
            d_mo = st.number_input("Custo Unitário de Mão de Obra (R$):", value=0.0)
            
            botao_add_orc = st.form_submit_button("➕ Adicionar Item ao Orçamento")

        if botao_add_orc:
            novo_orc_item = pd.DataFrame([{
                "descricao": d_item, "unid": d_unid, "quant": d_quant, "material": d_mat, "mao_obra": d_mo
            }])
            st.session_state.df_orcamento_itens = pd.concat([st.session_state.df_orcamento_itens, novo_orc_item], ignore_index=True)
            st.success("Item adicionado com sucesso!")

        st.markdown("### Itens Atuais do Orçamento")
        st.session_state.df_orcamento_itens = st.data_editor(st.session_state.df_orcamento_itens, num_rows="dynamic", use_container_width=True, key="editor_orc")

        if st.button("📥 Gerar PDF do Orçamento Oficial"):
            if not st.session_state.df_orcamento_itens.empty:
                pdf_orc_path = gerar_pdf_orcamento(obra_nome_input, solicitante_input, objeto_input, st.session_state.df_orcamento_itens, percentual_imposto_input)
                st.success("Orçamento gerado com sucesso!")
                with open(pdf_orc_path, "rb") as f_orc:
                    st.download_button("⬇️ Baixar Orçamento em PDF", data=f_orc, file_name="Orcamento_Oficial_Mads.pdf", mime="application/pdf")
            else:
                st.warning("Adicione pelo menos um item para gerar o orçamento.")
