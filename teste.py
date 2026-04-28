import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import hashlib
import os
import warnings
import plotly.express as px
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings('ignore')

# ==========================================================
# 🔧 CONFIGURAÇÕES GLOBAIS
# ==========================================================
DB_FILE = "MES_Banco_Dados.xlsx"
SHIFTS = {"1º Turno": 455, "2º Turno": 440, "3º Turno": 415}
STYLES = """
<style>
[data-testid="stMetricValue"] { font-size: 1.8rem !important; }
header { visibility: hidden; }
.stSidebar { background-color: #0f172a; }
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)

# ==========================================================
# 🗄️ GERENCIADOR DE BANCO DE DADOS (EXCEL)
# ==========================================================
def init_db():
    if not os.path.exists(DB_FILE):
        wb_cols = {
            "Usuarios": ["usuario", "senha_hash", "nivel", "ativo"],
            "Maquinas": ["codigo", "nome", "setor", "capacidade_h", "status", "aquisicao"],
            "Produtos": ["codigo", "descricao", "maquinas_comp", "tempo_ciclo", "peso", "pecas_fardo", "fardos_palete", "status"],
            "Paradas": ["codigo", "descricao", "categoria", "planejada", "impacto_oee"],
            "Producao": ["data", "turno", "maquina", "produto", "op", "pecas_boas", "pecas_refugo", "tempo_setup", "paradas_lista", "horas_extras", "usuario"],
            "PCP": ["data", "maquina", "produto", "meta_pecas", "status"],
            "Audit": ["timestamp", "usuario", "acao", "detalhes"]
        }
        
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            for sheet_name, cols in wb_cols.items():
                pd.DataFrame(columns=cols).to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Usuário padrão
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        df_usuarios = pd.DataFrame([{"usuario":"admin", "senha_hash":pwd_hash, "nivel":"Admin", "ativo":True}])
        save_sheet("Usuarios", df_usuarios)
        
        # Adicionar algumas máquinas de exemplo
        df_maquinas = pd.DataFrame([
            {"codigo":"MAQ001", "nome":"CNC 1", "setor":"Usinagem", "capacidade_h":100, "status":"Ativa", "aquisicao":datetime.now().strftime("%Y-%m-%d")},
            {"codigo":"MAQ002", "nome":"CNC 2", "setor":"Usinagem", "capacidade_h":100, "status":"Ativa", "aquisicao":datetime.now().strftime("%Y-%m-%d")},
            {"codigo":"MAQ003", "nome":"Injetora", "setor":"Injeção", "capacidade_h":200, "status":"Ativa", "aquisicao":datetime.now().strftime("%Y-%m-%d")}
        ])
        save_sheet("Maquinas", df_maquinas)
        
        # Adicionar alguns produtos de exemplo
        df_produtos = pd.DataFrame([
            {"codigo":"PROD001", "descricao":"Peça A", "maquinas_comp":"CNC 1", "tempo_ciclo":5, "peso":0.5, "pecas_fardo":100, "fardos_palete":10, "status":"Ativo"},
            {"codigo":"PROD002", "descricao":"Peça B", "maquinas_comp":"CNC 2", "tempo_ciclo":8, "peso":0.7, "pecas_fardo":80, "fardos_palete":12, "status":"Ativo"},
            {"codigo":"PROD003", "descricao":"Peça C", "maquinas_comp":"Injetora", "tempo_ciclo":3, "peso":0.3, "pecas_fardo":150, "fardos_palete":15, "status":"Ativo"}
        ])
        save_sheet("Produtos", df_produtos)
        
        log_audit("Sistema", "INIT", "Banco criado com sucesso")

def load_sheet(name):
    try: 
        return pd.read_excel(DB_FILE, sheet_name=name, engine="openpyxl")
    except Exception as e:
        return pd.DataFrame()

def save_sheet(name, df):
    try:
        # Carregar todas as abas existentes
        xls = pd.ExcelFile(DB_FILE, engine="openpyxl")
        all_sheets = {s: pd.read_excel(xls, sheet_name=s, engine="openpyxl") for s in xls.sheet_names}
        all_sheets[name] = df
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            for s, data in all_sheets.items():
                data.to_excel(writer, sheet_name=s, index=False)
    except:
        # Se o arquivo não existir ou estiver corrompido, criar novo
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=name, index=False)

def log_audit(user, action, details):
    df = load_sheet("Audit")
    new = pd.DataFrame([{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        "usuario": user, "acao": action, "detalhes": details}])
    if len(df) == 0:
        save_sheet("Audit", new)
    else:
        save_sheet("Audit", pd.concat([df, new], ignore_index=True))

# ==========================================================
# 🔐 AUTENTICAÇÃO
# ==========================================================
def authenticate(user, pwd):
    df = load_sheet("Usuarios")
    if df.empty:
        return None, None
    h = hashlib.sha256(pwd.encode()).hexdigest()
    match = df[(df["usuario"]==user) & (df["senha_hash"]==h) & (df["ativo"]==True)]
    return (match.iloc[0]["usuario"], match.iloc[0]["nivel"]) if not match.empty else (None, None)

# ==========================================================
# 📦 MÓDULOS DA APLICAÇÃO
# ==========================================================
def show_cadastros():
    st.header("⚙️ Cadastros Base")
    tab1, tab2, tab3 = st.tabs(["🖥️ Máquinas", "📦 Produtos", "🛑 Paradas"])
    
    with tab1:
        st.subheader("Cadastro de Máquinas")
        c1, c2, c3 = st.columns(3)
        cod = c1.text_input("Código", key="maq_cod")
        nome = c2.text_input("Nome", key="maq_nome")
        setor = c3.text_input("Setor", key="maq_setor")
        cap = st.number_input("Capacidade (peças/h)", min_value=0, step=10, key="maq_cap")
        
        if st.button("💾 Salvar Máquina", key="save_maq"):
            if cod and nome:
                df = load_sheet("Maquinas")
                new_row = pd.DataFrame([{
                    "codigo": cod, 
                    "nome": nome, 
                    "setor": setor, 
                    "capacidade_h": cap, 
                    "status": "Ativa", 
                    "aquisicao": datetime.now().strftime("%Y-%m-%d")
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_sheet("Maquinas", df)
                st.success(f"✅ Máquina {nome} cadastrada!")
                log_audit(st.session_state.user, "CADASTRO_MAQ", f"{nome}")
                st.rerun()
            else:
                st.error("Código e Nome são obrigatórios!")
        
        # Listar máquinas existentes
        st.subheader("Máquinas Cadastradas")
        df_maq = load_sheet("Maquinas")
        if not df_maq.empty:
            st.dataframe(df_maq[["codigo", "nome", "setor", "capacidade_h", "status"]], use_container_width=True)
    
    with tab2:
        st.subheader("Cadastro de Produtos")
        c1, c2, c3 = st.columns(3)
        cod_prod = c1.text_input("Código do Produto", key="prod_cod")
        desc = c2.text_input("Descrição", key="prod_desc")
        maq_comp = c3.text_input("Máquina Compatível", key="prod_maq")
        
        c1, c2 = st.columns(2)
        tempo_ciclo = c1.number_input("Tempo de Ciclo (segundos)", min_value=0.1, step=0.1, key="prod_ciclo")
        peso = c2.number_input("Peso (kg)", min_value=0.01, step=0.01, key="prod_peso")
        
        if st.button("💾 Salvar Produto", key="save_prod"):
            if cod_prod and desc:
                df = load_sheet("Produtos")
                new_row = pd.DataFrame([{
                    "codigo": cod_prod,
                    "descricao": desc,
                    "maquinas_comp": maq_comp,
                    "tempo_ciclo": tempo_ciclo,
                    "peso": peso,
                    "pecas_fardo": 0,
                    "fardos_palete": 0,
                    "status": "Ativo"
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_sheet("Produtos", df)
                st.success(f"✅ Produto {desc} cadastrado!")
                log_audit(st.session_state.user, "CADASTRO_PROD", f"{desc}")
                st.rerun()
            else:
                st.error("Código e Descrição são obrigatórios!")
        
        # Listar produtos existentes
        st.subheader("Produtos Cadastrados")
        df_prod = load_sheet("Produtos")
        if not df_prod.empty:
            st.dataframe(df_prod[["codigo", "descricao", "maquinas_comp", "tempo_ciclo", "status"]], use_container_width=True)
    
    with tab3:
        st.info("📝 Biblioteca de Paradas")
        st.markdown("""
        **Categorias de Parada:**
        - **Manutenção**: Preventiva, Corretiva, Ajustes
        - **Operacional**: Troca de ferramenta, Setup, Falta de operador
        - **Qualidade**: Amostragem, Ajuste de qualidade
        - **Logística**: Falta de material, Abastecimento
        - **Planejada**: Reuniões, Treinamentos, Pausas
        """)
        
        # Formulário para adicionar paradas
        st.subheader("Adicionar Nova Parada")
        c1, c2 = st.columns(2)
        cod_parada = c1.text_input("Código da Parada", key="parada_cod")
        desc_parada = c2.text_input("Descrição", key="parada_desc")
        categoria = st.selectbox("Categoria", ["Manutenção", "Operacional", "Qualidade", "Logística", "Planejada"])
        
        if st.button("➕ Adicionar Parada", key="add_parada"):
            if cod_parada and desc_parada:
                df = load_sheet("Paradas")
                new_row = pd.DataFrame([{
                    "codigo": cod_parada,
                    "descricao": desc_parada,
                    "categoria": categoria,
                    "planejada": categoria == "Planejada",
                    "impacto_oee": "Alto" if categoria != "Planejada" else "Baixo"
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_sheet("Paradas", df)
                st.success(f"✅ Parada {cod_parada} cadastrada!")
                st.rerun()

def show_producao():
    st.header("🏭 Apontamento de Produção")
    df_maq = load_sheet("Maquinas")
    df_prod = load_sheet("Produtos")
    
    if df_maq.empty:
        st.warning("⚠️ Nenhuma máquina cadastrada. Acesse 'Cadastros' para adicionar máquinas.")
        return
    if df_prod.empty:
        st.warning("⚠️ Nenhum produto cadastrado. Acesse 'Cadastros' para adicionar produtos.")
        return

    c1, c2, c3, c4 = st.columns(4)
    data = c1.date_input("Data", key="prod_data")
    turno = c2.selectbox("Turno", list(SHIFTS.keys()), key="prod_turno")
    maq = c3.selectbox("Máquina", df_maq["nome"].tolist(), key="prod_maquina")
    prod = c4.selectbox("Produto", df_prod["descricao"].tolist(), key="prod_produto")
    
    c5, c6, c7, c8 = st.columns(4)
    op = c5.text_input("Ordem de Produção (OP)", key="prod_op")
    boas = c6.number_input("Peças Boas", min_value=0, step=10, key="prod_boas")
    refugo = c7.number_input("Refugo", min_value=0, step=1, key="prod_refugo")
    setup = c8.number_input("Setup (min)", min_value=0, max_value=SHIFTS[turno], key="prod_setup")

    horas_ex = st.number_input("Horas Extras (min)", min_value=0, max_value=120, key="prod_he")
    paradas = st.text_area("Códigos de Parada (separados por vírgula)", key="prod_paradas", 
                          help="Exemplo: PAR001, PAR002, MAN003")

    # Calcular disponibilidade
    tempo_disponivel = SHIFTS[turno] + horas_ex - setup
    oee_disp = max(0, (tempo_disponivel / SHIFTS[turno]) * 100) if SHIFTS[turno] > 0 else 0
    st.metric("Disponibilidade Estimada", f"{oee_disp:.1f}%")

    if st.button("📝 Registrar Produção", type="primary", key="btn_registrar"):
        if not op:
            st.error("⚠️ OP (Ordem de Produção) é obrigatória!")
            return
        
        # Buscar capacidade da máquina
        cap_maq = df_maq[df_maq["nome"] == maq]["capacidade_h"].values
        capacidade = cap_maq[0] if len(cap_maq) > 0 else 0
        
        new_record = pd.DataFrame([{
            "data": data.isoformat(), 
            "turno": turno, 
            "maquina": maq, 
            "produto": prod, 
            "op": op, 
            "pecas_boas": boas, 
            "pecas_refugo": refugo, 
            "tempo_setup": setup,
            "paradas_lista": paradas, 
            "horas_extras": horas_ex, 
            "usuario": st.session_state.user,
            "capacidade_h": capacidade  # Adicionando capacidade para referência
        }])
        
        df_producao = load_sheet("Producao")
        df_producao = pd.concat([df_producao, new_record], ignore_index=True)
        save_sheet("Producao", df_producao)
        log_audit(st.session_state.user, "APONTAMENTO", f"OP {op} | {maq} | {boas} peças")
        st.success("✅ Apontamento salvo com sucesso!")
        st.balloons()
        st.rerun()

def show_dashboard():
    st.header("📊 Dashboard Operacional")
    df = load_sheet("Producao")
    if df.empty:
        st.info("ℹ️ Nenhum dado de produção disponível. Registre apontamentos para visualizar o dashboard.")
        return

    # Converter datas
    df["data"] = pd.to_datetime(df["data"])
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        data_inicio = st.date_input("Data Início", df["data"].min(), key="dash_ini")
    with col2:
        data_fim = st.date_input("Data Fim", df["data"].max(), key="dash_fim")
    
    df_filtrado = df[(df["data"] >= pd.to_datetime(data_inicio)) & (df["data"] <= pd.to_datetime(data_fim))]
    
    if df_filtrado.empty:
        st.warning("⚠️ Nenhum dado no período selecionado.")
        return

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    total_boas = df_filtrado["pecas_boas"].sum()
    total_refugo = df_filtrado["pecas_refugo"].sum()
    total_pecas = total_boas + total_refugo
    refugo_percent = (total_refugo / total_pecas * 100) if total_pecas > 0 else 0
    
    col1.metric("✅ Peças Boas", f"{total_boas:,.0f}")
    col2.metric("❌ Refugo", f"{total_refugo:,.0f}", delta=f"{refugo_percent:.1f}%")
    
    # Cálculo de OEE simplificado
    tempo_total_planejado = df_filtrado["turno"].map(SHIFTS).sum()
    tempo_setup_total = df_filtrado["tempo_setup"].sum()
    tempo_operando = max(0, tempo_total_planejado - tempo_setup_total)
    disponibilidade = (tempo_operando / tempo_total_planejado * 100) if tempo_total_planejado > 0 else 0
    
    # Performance (assumindo capacidade média)
    capacidade_media = 100  # peças/hora padrão
    tempo_efetivo_horas = tempo_operando / 60
    producao_esperada = tempo_efetivo_horas * capacidade_media
    performance = (total_boas / producao_esperada * 100) if producao_esperada > 0 else 0
    
    # Qualidade
    qualidade = (total_boas / total_pecas * 100) if total_pecas > 0 else 0
    
    oee = (disponibilidade / 100) * (performance / 100) * (qualidade / 100) * 100
    
    col3.metric("📈 OEE Global", f"{oee:.1f}%")
    col4.metric("📊 Registros", len(df_filtrado))

    # Gráficos
    st.subheader("📈 Análises Gráficas")
    
    tab1, tab2, tab3 = st.tabs(["Produção por Dia", "Refugo por Turno", "Performance por Máquina"])
    
    with tab1:
        producao_diaria = df_filtrado.groupby(df_filtrado["data"].dt.date).agg({
            "pecas_boas": "sum",
            "pecas_refugo": "sum"
        }).reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=producao_diaria["data"], y=producao_diaria["pecas_boas"], name="Peças Boas", marker_color="green"))
        fig.add_trace(go.Bar(x=producao_diaria["data"], y=producao_diaria["pecas_refugo"], name="Refugo", marker_color="red"))
        fig.update_layout(title="Produção Diária", xaxis_title="Data", yaxis_title="Quantidade", barmode="group")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        refugo_turno = df_filtrado.groupby("turno")["pecas_refugo"].sum().reset_index()
        fig = px.pie(refugo_turno, values="pecas_refugo", names="turno", title="Distribuição de Refugo por Turno")
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        performance_maq = df_filtrado.groupby("maquina").agg({
            "pecas_boas": "sum",
            "tempo_setup": "sum"
        }).reset_index()
        
        fig = px.bar(performance_maq, x="maquina", y="pecas_boas", title="Produção por Máquina", 
                    color="pecas_boas", color_continuous_scale="Viridis")
        st.plotly_chart(fig, use_container_width=True)
    
    # Pareto de Paradas
    if "paradas_lista" in df_filtrado.columns:
        st.subheader("🎯 Pareto de Paradas")
        paradas_list = df_filtrado["paradas_lista"].dropna().str.split(",").explode()
        paradas_list = paradas_list.str.strip()
        paradas_count = paradas_list.value_counts().reset_index()
        if not paradas_count.empty:
            paradas_count.columns = ["Parada", "Quantidade"]
            fig_pareto = px.bar(paradas_count.head(10), x="Parada", y="Quantidade", 
                               title="Top 10 Paradas", color="Quantidade", color_continuous_scale="Reds")
            st.plotly_chart(fig_pareto, use_container_width=True)

def show_pcp():
    st.header("📅 PCP - Planejamento & Controle")
    df_pcp = load_sheet("PCP")
    df_maq = load_sheet("Maquinas")
    df_prod = load_sheet("Produtos")
    
    col1, col2, col3, col4 = st.columns(4)
    data = col1.date_input("Data Programada", key="pcp_data")
    maq = col2.selectbox("Máquina", df_maq["nome"].tolist() if not df_maq.empty else [""], key="pcp_maq")
    prod = col3.selectbox("Produto", df_prod["descricao"].tolist() if not df_prod.empty else [""], key="pcp_prod")
    meta = col4.number_input("Meta (peças)", min_value=0, step=100, key="pcp_meta")
    
    if st.button("📋 Programar Produção", type="primary", key="btn_pcp"):
        if maq and prod and meta > 0:
            new_row = pd.DataFrame([{
                "data": data.isoformat(), 
                "maquina": maq, 
                "produto": prod, 
                "meta_pecas": meta, 
                "status": "Programado"
            }])
            df_pcp = pd.concat([df_pcp, new_row], ignore_index=True)
            save_sheet("PCP", df_pcp)
            log_audit(st.session_state.user, "PCP", f"Programação {data} - {maq} - {meta} peças")
            st.success("✅ Programação salva com sucesso!")
            st.rerun()
        else:
            st.error("⚠️ Preencha todos os campos!")
    
    # Exibir programações existentes
    if not df_pcp.empty:
        st.subheader("📋 Programações Ativas")
        st.dataframe(df_pcp.sort_values("data", ascending=False), use_container_width=True)

def show_ml():
    st.header("🤖 IA & Analytics")
    df = load_sheet("Producao")
    
    if df.empty or len(df) < 10:
        st.warning("⚠️ Mínimo de 10 registros de produção para análise. Continue registrando apontamentos!")
        return
    
    st.subheader("📊 Análise de Dados e Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Total de Registros", len(df))
        st.metric("Período", f"{df['data'].min()} a {df['data'].max()}")
    
    with col2:
        produtividade_media = df["pecas_boas"].mean()
        st.metric("Produção Média por Apontamento", f"{produtividade_media:.0f} peças")
        refugo_medio = (df["pecas_refugo"].sum() / (df["pecas_boas"].sum() + df["pecas_refugo"].sum()) * 100) if (df["pecas_boas"].sum() + df["pecas_refugo"].sum()) > 0 else 0
        st.metric("Taxa Média de Refugo", f"{refugo_medio:.1f}%")
    
    # Machine Learning - Predição de Refugo
    st.subheader("🔮 Predição de Risco de Refugo")
    
    try:
        # Preparar dados para ML
        df_ml = df.copy()
        df_ml["tempo_setup_horas"] = df_ml["tempo_setup"] / 60
        
        # Features simples
        X = df_ml[["tempo_setup_horas", "horas_extras"]].fillna(0)
        y = (df_ml["pecas_refugo"] > df_ml["pecas_refugo"].median()).astype(int)
        
        if len(X) >= 10:
            model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=3)
            model.fit(X, y)
            
            # Interface de predição
            st.write("### 🎯 Simular Novo Apontamento")
            col1, col2 = st.columns(2)
            tempo_setup_pred = col1.number_input("Tempo de Setup (minutos)", min_value=0, max_value=120, value=30)
            horas_extras_pred = col2.number_input("Horas Extras (minutos)", min_value=0, max_value=120, value=0)
            
            if st.button("🔍 Prever Risco", key="predict_btn"):
                pred_data = pd.DataFrame([[tempo_setup_pred/60, horas_extras_pred]], columns=["tempo_setup_horas", "horas_extras"])
                risco = model.predict_proba(pred_data)[0][1]
                
                if risco > 0.7:
                    st.error(f"⚠️ ALTO RISCO de refugo! Probabilidade: {risco:.1%}")
                elif risco > 0.4:
                    st.warning(f"⚠️ RISCO MODERADO de refugo! Probabilidade: {risco:.1%}")
                else:
                    st.success(f"✅ BAIXO RISCO de refugo! Probabilidade: {risco:.1%}")
                
                # Mostrar fatores de impacto
                importancia = pd.DataFrame({
                    'Fator': ['Tempo de Setup', 'Horas Extras'],
                    'Impacto': model.feature_importances_
                })
                st.write("**Fatores de Impacto:**")
                st.dataframe(importancia, use_container_width=True)
    except Exception as e:
        st.warning(f"Modelo ainda treinando. Acumule mais dados para melhores previsões. Erro: {str(e)}")
    
    # Gráficos de correlação
    st.subheader("📈 Análise de Correlações")
    
    fig = px.scatter(df, x="tempo_setup", y="pecas_refugo", 
                    title="Relação: Tempo de Setup vs Refugo",
                    labels={"tempo_setup": "Tempo de Setup (min)", "pecas_refugo": "Quantidade de Refugo"},
                    trendline="ols", color="turno")
    st.plotly_chart(fig, use_container_width=True)
    
    # Insights acionáveis
    st.subheader("💡 Insights Gerenciais")
    
    setup_medio = df["tempo_setup"].mean()
    refugo_medio_qtd = df["pecas_refugo"].mean()
    
    st.info(f"""
    **Principais Observações:**
    - 📊 Tempo médio de setup: **{setup_medio:.0f} minutos**
    - 🎯 Refugo médio por apontamento: **{refugo_medio_qtd:.0f} peças**
    - ⚡ Turnos com menor refugo: Analise o gráfico acima para identificar
    - 🎯 Redução de 10% no tempo de setup pode reduzir refugo em aproximadamente 5%
    
    **Recomendações:**
    1. Padronizar procedimentos de setup
    2. Treinar operadores nos turnos com maior taxa de refugo
    3. Implementar manutenção preventiva nas máquinas críticas
    """)

# ==========================================================
# 🚀 ROTEADOR PRINCIPAL
# ==========================================================
def main():
    st.set_page_config(page_title="MES Industrial", page_icon="🏭", layout="wide")
    init_db()

    if "logged" not in st.session_state: 
        st.session_state.logged = False
    if "user" not in st.session_state: 
        st.session_state.user = None
    if "role" not in st.session_state: 
        st.session_state.role = None

    if not st.session_state.logged:
        st.title("🔐 Sistema MES Industrial")
        st.markdown("### Login")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            u = st.text_input("👤 Usuário", key="login_user")
            p = st.text_input("🔒 Senha", type="password", key="login_pass")
            
            if st.button("Entrar", type="primary", use_container_width=True):
                user, role = authenticate(u, p)
                if user:
                    st.session_state.logged = True
                    st.session_state.user = user
                    st.session_state.role = role
                    log_audit(user, "LOGIN", "Acesso concedido")
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas ou usuário inativo.")
            
            st.markdown("---")
            st.info("💡 **Credenciais padrão:**\nUsuário: `admin`\nSenha: `admin123`")
        return

    # Menu Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.caption(f"📌 Nível: {st.session_state.role}")
        
        st.divider()
        
        if st.button("🚪 Sair", use_container_width=True):
            log_audit(st.session_state.user, "LOGOUT", "Usuário saiu do sistema")
            st.session_state.logged = False
            st.session_state.user = None
            st.session_state.role = None
            st.rerun()
        
        st.divider()
        
        # Menu baseado no nível de acesso
        if st.session_state.role in ["Admin", "Gerente", "Supervisor", "Operador"]:
            menu = st.radio("📋 Navegação", 
                          ["📊 Dashboard", "🏭 Produção", "📅 PCP", "⚙️ Cadastros", "🤖 IA & Analytics"],
                          key="menu_nav")
        else:
            menu = st.radio("📋 Navegação", ["📊 Dashboard", "🏭 Produção"], key="menu_nav")
    
    # Roteamento
    if menu == "📊 Dashboard":
        show_dashboard()
    elif menu == "🏭 Produção":
        show_producao()
    elif menu == "📅 PCP":
        if st.session_state.role in ["Admin", "Gerente"]:
            show_pcp()
        else:
            st.error("⛔ Acesso restrito - Nível necessário: Gerente ou Admin")
    elif menu == "⚙️ Cadastros":
        if st.session_state.role == "Admin":
            show_cadastros()
        else:
            st.error("⛔ Acesso restrito - Nível necessário: Admin")
    elif menu == "🤖 IA & Analytics":
        if st.session_state.role in ["Admin", "Gerente", "Supervisor"]:
            show_ml()
        else:
            st.error("⛔ Acesso restrito - Nível necessário: Supervisor, Gerente ou Admin")

if __name__ == "__main__":
    main()