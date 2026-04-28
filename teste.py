import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import hashlib
import os
import warnings
import plotly.express as px
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import io
import base64

warnings.filterwarnings('ignore')

# ==========================================================
# 🔧 CONFIGURAÇÕES GLOBAIS
# ==========================================================
# Usar session_state para armazenar dados (já que não podemos escrever no disco no Streamlit Cloud)
DB_FILE = "MES_Banco_Dados.xlsx"
SHIFTS = {"1º Turno": 455, "2º Turno": 440, "3º Turno": 415}

# ==========================================================
# 🗄️ GERENCIADOR DE BANCO DE DADOS (Memória/Session)
# ==========================================================
def init_db():
    """Inicializa o banco de dados na session_state"""
    if 'db_initialized' not in st.session_state:
        st.session_state.db_initialized = True
        
        # Usuários
        pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
        st.session_state.usuarios = pd.DataFrame([{
            "usuario": "admin", 
            "senha_hash": pwd_hash, 
            "nivel": "Admin", 
            "ativo": True
        }])
        
        # Máquinas
        st.session_state.maquinas = pd.DataFrame([
            {"codigo": "MAQ001", "nome": "CNC 1", "setor": "Usinagem", "capacidade_h": 100, "status": "Ativa", "aquisicao": datetime.now().strftime("%Y-%m-%d")},
            {"codigo": "MAQ002", "nome": "CNC 2", "setor": "Usinagem", "capacidade_h": 100, "status": "Ativa", "aquisicao": datetime.now().strftime("%Y-%m-%d")},
            {"codigo": "MAQ003", "nome": "Injetora", "setor": "Injeção", "capacidade_h": 200, "status": "Ativa", "aquisicao": datetime.now().strftime("%Y-%m-%d")}
        ])
        
        # Produtos
        st.session_state.produtos = pd.DataFrame([
            {"codigo": "PROD001", "descricao": "Peça A", "maquinas_comp": "CNC 1", "tempo_ciclo": 5, "peso": 0.5, "status": "Ativo"},
            {"codigo": "PROD002", "descricao": "Peça B", "maquinas_comp": "CNC 2", "tempo_ciclo": 8, "peso": 0.7, "status": "Ativo"},
            {"codigo": "PROD003", "descricao": "Peça C", "maquinas_comp": "Injetora", "tempo_ciclo": 3, "peso": 0.3, "status": "Ativo"}
        ])
        
        # Paradas
        st.session_state.paradas = pd.DataFrame(columns=["codigo", "descricao", "categoria", "planejada", "impacto_oee"])
        
        # Produção
        st.session_state.producao = pd.DataFrame(columns=[
            "data", "turno", "maquina", "produto", "op", "pecas_boas", 
            "pecas_refugo", "tempo_setup", "paradas_lista", "horas_extras", "usuario"
        ])
        
        # PCP
        st.session_state.pcp = pd.DataFrame(columns=["data", "maquina", "produto", "meta_pecas", "status"])
        
        # Audit
        st.session_state.audit = pd.DataFrame(columns=["timestamp", "usuario", "acao", "detalhes"])
        
        log_audit("Sistema", "INIT", "Sistema inicializado no Streamlit Cloud")

def log_audit(user, action, details):
    """Registra log de auditoria"""
    if 'audit' not in st.session_state:
        st.session_state.audit = pd.DataFrame(columns=["timestamp", "usuario", "acao", "detalhes"])
    
    new_log = pd.DataFrame([{
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "usuario": user,
        "acao": action,
        "detalhes": details
    }])
    st.session_state.audit = pd.concat([st.session_state.audit, new_log], ignore_index=True)

# ==========================================================
# 🔐 AUTENTICAÇÃO
# ==========================================================
def authenticate(user, pwd):
    """Autentica usuário"""
    if 'usuarios' not in st.session_state:
        return None, None
    
    h = hashlib.sha256(pwd.encode()).hexdigest()
    match = st.session_state.usuarios[
        (st.session_state.usuarios["usuario"] == user) & 
        (st.session_state.usuarios["senha_hash"] == h) & 
        (st.session_state.usuarios["ativo"] == True)
    ]
    return (match.iloc[0]["usuario"], match.iloc[0]["nivel"]) if not match.empty else (None, None)

# ==========================================================
# 📦 MÓDULOS DA APLICAÇÃO
# ==========================================================
def show_cadastros():
    st.header("⚙️ Cadastros Base")
    tab1, tab2, tab3 = st.tabs(["🖥️ Máquinas", "📦 Produtos", "🛑 Paradas"])
    
    with tab1:
        st.subheader("Cadastro de Máquinas")
        col1, col2, col3 = st.columns(3)
        codigo = col1.text_input("Código", key="maq_cod")
        nome = col2.text_input("Nome", key="maq_nome")
        setor = col3.text_input("Setor", key="maq_setor")
        capacidade = st.number_input("Capacidade (peças/hora)", min_value=0, step=10, key="maq_cap")
        
        if st.button("➕ Adicionar Máquina", key="add_maq"):
            if codigo and nome:
                nova_maq = pd.DataFrame([{
                    "codigo": codigo,
                    "nome": nome,
                    "setor": setor,
                    "capacidade_h": capacidade,
                    "status": "Ativa",
                    "aquisicao": datetime.now().strftime("%Y-%m-%d")
                }])
                st.session_state.maquinas = pd.concat([st.session_state.maquinas, nova_maq], ignore_index=True)
                log_audit(st.session_state.user, "CADASTRO_MAQ", f"{nome}")
                st.success(f"✅ Máquina {nome} cadastrada!")
                st.rerun()
            else:
                st.error("❌ Código e Nome são obrigatórios!")
        
        st.subheader("Máquinas Cadastradas")
        if not st.session_state.maquinas.empty:
            st.dataframe(st.session_state.maquinas[["codigo", "nome", "setor", "capacidade_h", "status"]], use_container_width=True)
    
    with tab2:
        st.subheader("Cadastro de Produtos")
        col1, col2, col3 = st.columns(3)
        cod_prod = col1.text_input("Código", key="prod_cod")
        desc = col2.text_input("Descrição", key="prod_desc")
        maq_comp = col3.text_input("Máquina Compatível", key="prod_maq")
        tempo_ciclo = st.number_input("Tempo de Ciclo (segundos)", min_value=0.1, step=0.1, key="prod_ciclo")
        
        if st.button("➕ Adicionar Produto", key="add_prod"):
            if cod_prod and desc:
                novo_prod = pd.DataFrame([{
                    "codigo": cod_prod,
                    "descricao": desc,
                    "maquinas_comp": maq_comp,
                    "tempo_ciclo": tempo_ciclo,
                    "peso": 0,
                    "status": "Ativo"
                }])
                st.session_state.produtos = pd.concat([st.session_state.produtos, novo_prod], ignore_index=True)
                log_audit(st.session_state.user, "CADASTRO_PROD", f"{desc}")
                st.success(f"✅ Produto {desc} cadastrado!")
                st.rerun()
            else:
                st.error("❌ Código e Descrição são obrigatórios!")
        
        st.subheader("Produtos Cadastrados")
        if not st.session_state.produtos.empty:
            st.dataframe(st.session_state.produtos[["codigo", "descricao", "maquinas_comp", "status"]], use_container_width=True)

def show_producao():
    st.header("🏭 Apontamento de Produção")
    
    if st.session_state.maquinas.empty:
        st.warning("⚠️ Nenhuma máquina cadastrada. Acesse 'Cadastros' primeiro.")
        return
    if st.session_state.produtos.empty:
        st.warning("⚠️ Nenhum produto cadastrado. Acesse 'Cadastros' primeiro.")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    data = col1.date_input("Data", key="prod_data")
    turno = col2.selectbox("Turno", list(SHIFTS.keys()), key="prod_turno")
    maquina = col3.selectbox("Máquina", st.session_state.maquinas["nome"].tolist(), key="prod_maq")
    produto = col4.selectbox("Produto", st.session_state.produtos["descricao"].tolist(), key="prod_prod")
    
    col5, col6, col7, col8 = st.columns(4)
    op = col5.text_input("Ordem de Produção (OP)", key="prod_op")
    boas = col6.number_input("Peças Boas", min_value=0, step=10, key="prod_boas")
    refugo = col7.number_input("Refugo", min_value=0, step=1, key="prod_ref")
    setup = col8.number_input("Setup (min)", min_value=0, max_value=SHIFTS[turno], key="prod_setup")
    
    horas_extras = st.number_input("Horas Extras (minutos)", min_value=0, max_value=120, key="prod_he")
    paradas = st.text_area("Paradas (códigos separados por vírgula)", key="prod_paradas")
    
    if st.button("📝 Registrar Produção", type="primary", key="reg_prod"):
        if not op:
            st.error("⚠️ OP é obrigatória!")
            return
        
        novo_registro = pd.DataFrame([{
            "data": data.isoformat(),
            "turno": turno,
            "maquina": maquina,
            "produto": produto,
            "op": op,
            "pecas_boas": boas,
            "pecas_refugo": refugo,
            "tempo_setup": setup,
            "paradas_lista": paradas,
            "horas_extras": horas_extras,
            "usuario": st.session_state.user
        }])
        
        st.session_state.producao = pd.concat([st.session_state.producao, novo_registro], ignore_index=True)
        log_audit(st.session_state.user, "PRODUCAO", f"OP {op} - {boas} peças")
        st.success("✅ Produção registrada!")
        st.balloons()
        st.rerun()

def show_dashboard():
    st.header("📊 Dashboard")
    
    if st.session_state.producao.empty:
        st.info("ℹ️ Nenhum dado de produção. Registre apontamentos primeiro.")
        return
    
    df = st.session_state.producao.copy()
    df["data"] = pd.to_datetime(df["data"])
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    total_boas = df["pecas_boas"].sum()
    total_refugo = df["pecas_refugo"].sum()
    total_pecas = total_boas + total_refugo
    refugo_pct = (total_refugo / total_pecas * 100) if total_pecas > 0 else 0
    
    col1.metric("✅ Peças Boas", f"{total_boas:,.0f}")
    col2.metric("❌ Refugo", f"{total_refugo:,.0f}", delta=f"{refugo_pct:.1f}%")
    col3.metric("📊 Total Registros", len(df))
    col4.metric("🎯 Eficiência", f"{100-refugo_pct:.1f}%")
    
    # Gráficos
    st.subheader("📈 Produção por Dia")
    producao_diaria = df.groupby(df["data"].dt.date).agg({
        "pecas_boas": "sum",
        "pecas_refugo": "sum"
    }).reset_index()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=producao_diaria["data"], y=producao_diaria["pecas_boas"], 
                        name="Boas", marker_color="green"))
    fig.add_trace(go.Bar(x=producao_diaria["data"], y=producao_diaria["pecas_refugo"], 
                        name="Refugo", marker_color="red"))
    fig.update_layout(title="Produção Diária", xaxis_title="Data", yaxis_title="Quantidade")
    st.plotly_chart(fig, use_container_width=True)
    
    # Produção por máquina
    st.subheader("🏭 Produção por Máquina")
    prod_maquina = df.groupby("maquina")["pecas_boas"].sum().reset_index()
    fig2 = px.bar(prod_maquina, x="maquina", y="pecas_boas", 
                  title="Peças Boas por Máquina", color="pecas_boas")
    st.plotly_chart(fig2, use_container_width=True)

def show_pcp():
    st.header("📅 PCP - Planejamento")
    
    if st.session_state.maquinas.empty or st.session_state.produtos.empty:
        st.warning("⚠️ Cadastre máquinas e produtos primeiro!")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    data = col1.date_input("Data", key="pcp_data")
    maquina = col2.selectbox("Máquina", st.session_state.maquinas["nome"].tolist(), key="pcp_maq")
    produto = col3.selectbox("Produto", st.session_state.produtos["descricao"].tolist(), key="pcp_prod")
    meta = col4.number_input("Meta (peças)", min_value=0, step=100, key="pcp_meta")
    
    if st.button("📋 Programar", key="prog_pcp"):
        if meta > 0:
            nova_prog = pd.DataFrame([{
                "data": data.isoformat(),
                "maquina": maquina,
                "produto": produto,
                "meta_pecas": meta,
                "status": "Programado"
            }])
            st.session_state.pcp = pd.concat([st.session_state.pcp, nova_prog], ignore_index=True)
            st.success("✅ Programação salva!")
            st.rerun()
    
    if not st.session_state.pcp.empty:
        st.subheader("Programações Ativas")
        st.dataframe(st.session_state.pcp, use_container_width=True)

def show_ml():
    st.header("🤖 IA Analytics")
    
    if len(st.session_state.producao) < 5:
        st.warning("⚠️ Precisa de pelo menos 5 registros para análise")
        return
    
    df = st.session_state.producao
    st.subheader("📊 Estatísticas")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Setup Médio", f"{df['tempo_setup'].mean():.0f} min")
        st.metric("Refugo Médio", f"{df['pecas_refugo'].mean():.0f} peças")
    with col2:
        st.metric("Produção Média", f"{df['pecas_boas'].mean():.0f} peças")
        st.metric("Horas Extras Média", f"{df['horas_extras'].mean():.0f} min")
    
    # Correlação
    fig = px.scatter(df, x="tempo_setup", y="pecas_refugo", 
                     title="Setup vs Refugo", trendline="ols")
    st.plotly_chart(fig, use_container_width=True)

# ==========================================================
# 🚀 MAIN
# ==========================================================
def main():
    st.set_page_config(
        page_title="MES Industrial", 
        page_icon="🏭", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inicializar banco de dados
    init_db()
    
    # Login
    if "logged" not in st.session_state:
        st.session_state.logged = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "role" not in st.session_state:
        st.session_state.role = None
    
    if not st.session_state.logged:
        st.title("🏭 Sistema MES Industrial")
        st.markdown("### 🔐 Login")
        
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            usuario = st.text_input("Usuário", key="login_user")
            senha = st.text_input("Senha", type="password", key="login_pass")
            
            if st.button("Entrar", type="primary", use_container_width=True):
                user, role = authenticate(usuario, senha)
                if user:
                    st.session_state.logged = True
                    st.session_state.user = user
                    st.session_state.role = role
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha inválidos!")
            
            st.info("💡 **Acesso:** `admin` / `admin123`")
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user}")
        st.markdown(f"**Nível:** {st.session_state.role}")
        st.divider()
        
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logged = False
            st.rerun()
        
        st.divider()
        
        # Menu
        menu_options = ["📊 Dashboard", "🏭 Produção", "📅 PCP", "⚙️ Cadastros", "🤖 IA Analytics"]
        if st.session_state.role != "Admin":
            menu_options.remove("⚙️ Cadastros")
        
        page = st.radio("📋 Menu", menu_options)
    
    # Rotas
    if page == "📊 Dashboard":
        show_dashboard()
    elif page == "🏭 Produção":
        show_producao()
    elif page == "📅 PCP":
        show_pcp()
    elif page == "⚙️ Cadastros":
        show_cadastros()
    elif page == "🤖 IA Analytics":
        show_ml()

if __name__ == "__main__":
    main()
