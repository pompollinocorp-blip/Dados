import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import hashlib
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="MES Industrial", page_icon="🏭", layout="wide")

# Configurações
SHIFTS = {"1º Turno": 455, "2º Turno": 440, "3º Turno": 415}

# Inicializar session state
if 'usuarios' not in st.session_state:
    pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
    st.session_state.usuarios = pd.DataFrame([{
        "usuario": "admin", 
        "senha_hash": pwd_hash, 
        "nivel": "Admin", 
        "ativo": True
    }])
    st.session_state.maquinas = pd.DataFrame([
        {"codigo": "MAQ001", "nome": "CNC 1", "setor": "Usinagem", "capacidade_h": 100, "status": "Ativa"},
        {"codigo": "MAQ002", "nome": "CNC 2", "setor": "Usinagem", "capacidade_h": 100, "status": "Ativa"},
        {"codigo": "MAQ003", "nome": "Injetora", "setor": "Injeção", "capacidade_h": 200, "status": "Ativa"}
    ])
    st.session_state.produtos = pd.DataFrame([
        {"codigo": "PROD001", "descricao": "Peça A", "status": "Ativo"},
        {"codigo": "PROD002", "descricao": "Peça B", "status": "Ativo"},
        {"codigo": "PROD003", "descricao": "Peça C", "status": "Ativo"}
    ])
    st.session_state.producao = pd.DataFrame(columns=[
        "data", "turno", "maquina", "produto", "op", "pecas_boas", 
        "pecas_refugo", "tempo_setup", "horas_extras", "usuario"
    ])
    st.session_state.logged = False
    st.session_state.user = None
    st.session_state.role = None

# Autenticação
def authenticate(user, pwd):
    h = hashlib.sha256(pwd.encode()).hexdigest()
    match = st.session_state.usuarios[
        (st.session_state.usuarios["usuario"] == user) & 
        (st.session_state.usuarios["senha_hash"] == h)
    ]
    return (match.iloc[0]["usuario"], match.iloc[0]["nivel"]) if not match.empty else (None, None)

# Interface de Login
if not st.session_state.logged:
    st.title("🏭 Sistema MES Industrial")
    st.markdown("### 🔐 Acesso ao Sistema")
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        
        if st.button("Entrar", type="primary", use_container_width=True):
            user, role = authenticate(usuario, senha)
            if user:
                st.session_state.logged = True
                st.session_state.user = user
                st.session_state.role = role
                st.rerun()
            else:
                st.error("❌ Usuário ou senha inválidos!")
        
        st.info("💡 **Acesso:** admin / admin123")
    st.stop()

# Menu Sidebar
with st.sidebar:
    st.header(f"👤 {st.session_state.user}")
    st.caption(f"Nível: {st.session_state.role}")
    st.divider()
    
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.logged = False
        st.rerun()
    
    st.divider()
    menu = st.radio("📋 Navegação", ["📊 Dashboard", "🏭 Produção", "⚙️ Cadastros"])

# ==================== DASHBOARD ====================
if menu == "📊 Dashboard":
    st.header("📊 Dashboard Operacional")
    
    if st.session_state.producao.empty:
        st.info("ℹ️ Nenhum dado de produção cadastrado.")
    else:
        df = st.session_state.producao
        col1, col2, col3, col4 = st.columns(4)
        
        total_boas = df["pecas_boas"].sum()
        total_refugo = df["pecas_refugo"].sum()
        eficiencia = (total_boas / (total_boas + total_refugo) * 100) if (total_boas + total_refugo) > 0 else 0
        
        col1.metric("✅ Peças Boas", f"{total_boas:,.0f}")
        col2.metric("❌ Refugo", f"{total_refugo:,.0f}")
        col3.metric("📊 Eficiência", f"{eficiencia:.1f}%")
        col4.metric("🎯 Registros", len(df))
        
        # Gráfico
        st.subheader("📈 Produção")
        prod_maquina = df.groupby("maquina")["pecas_boas"].sum().reset_index()
        fig = px.bar(prod_maquina, x="maquina", y="pecas_boas", title="Produção por Máquina")
        st.plotly_chart(fig, use_container_width=True)

# ==================== PRODUÇÃO ====================
elif menu == "🏭 Produção":
    st.header("🏭 Apontamento de Produção")
    
    if st.session_state.maquinas.empty:
        st.warning("⚠️ Cadastre máquinas primeiro!")
    elif st.session_state.produtos.empty:
        st.warning("⚠️ Cadastre produtos primeiro!")
    else:
        col1, col2, col3, col4 = st.columns(4)
        data = col1.date_input("Data")
        turno = col2.selectbox("Turno", list(SHIFTS.keys()))
        maquina = col3.selectbox("Máquina", st.session_state.maquinas["nome"].tolist())
        produto = col4.selectbox("Produto", st.session_state.produtos["descricao"].tolist())
        
        col5, col6, col7, col8 = st.columns(4)
        op = col5.text_input("Ordem de Produção (OP)")
        boas = col6.number_input("Peças Boas", min_value=0, step=10)
        refugo = col7.number_input("Refugo", min_value=0, step=1)
        setup = col8.number_input("Setup (min)", min_value=0, max_value=455)
        
        horas_extras = st.number_input("Horas Extras (min)", min_value=0, max_value=120)
        
        if st.button("📝 Registrar Produção", type="primary"):
            if not op:
                st.error("⚠️ OP é obrigatória!")
            else:
                novo = pd.DataFrame([{
                    "data": data.isoformat(),
                    "turno": turno,
                    "maquina": maquina,
                    "produto": produto,
                    "op": op,
                    "pecas_boas": boas,
                    "pecas_refugo": refugo,
                    "tempo_setup": setup,
                    "horas_extras": horas_extras,
                    "usuario": st.session_state.user
                }])
                st.session_state.producao = pd.concat([st.session_state.producao, novo], ignore_index=True)
                st.success("✅ Produção registrada!")
                st.balloons()
                st.rerun()

# ==================== CADASTROS ====================
elif menu == "⚙️ Cadastros":
    st.header("⚙️ Cadastros Base")
    
    if st.session_state.role != "Admin":
        st.error("⛔ Acesso restrito a Administradores!")
    else:
        tab1, tab2 = st.tabs(["🖥️ Máquinas", "📦 Produtos"])
        
        with tab1:
            st.subheader("Nova Máquina")
            col1, col2, col3 = st.columns(3)
            codigo = col1.text_input("Código", key="maq_cod")
            nome = col2.text_input("Nome", key="maq_nome")
            setor = col3.text_input("Setor", key="maq_setor")
            capacidade = st.number_input("Capacidade (peças/h)", min_value=0, step=10, key="maq_cap")
            
            if st.button("💾 Salvar Máquina", key="save_maq"):
                if codigo and nome:
                    nova = pd.DataFrame([{
                        "codigo": codigo, "nome": nome, "setor": setor,
                        "capacidade_h": capacidade, "status": "Ativa"
                    }])
                    st.session_state.maquinas = pd.concat([st.session_state.maquinas, nova], ignore_index=True)
                    st.success(f"✅ Máquina {nome} cadastrada!")
                    st.rerun()
                else:
                    st.error("❌ Código e Nome são obrigatórios!")
            
            st.subheader("Máquinas Cadastradas")
            st.dataframe(st.session_state.maquinas, use_container_width=True)
        
        with tab2:
            st.subheader("Novo Produto")
            col1, col2 = st.columns(2)
            cod_prod = col1.text_input("Código", key="prod_cod")
            desc = col2.text_input("Descrição", key="prod_desc")
            
            if st.button("💾 Salvar Produto", key="save_prod"):
                if cod_prod and desc:
                    novo = pd.DataFrame([{"codigo": cod_prod, "descricao": desc, "status": "Ativo"}])
                    st.session_state.produtos = pd.concat([st.session_state.produtos, novo], ignore_index=True)
                    st.success(f"✅ Produto {desc} cadastrado!")
                    st.rerun()
                else:
                    st.error("❌ Código e Descrição são obrigatórios!")
            
            st.subheader("Produtos Cadastrados")
            st.dataframe(st.session_state.produtos, use_container_width=True)
