import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# Configuração da página do Streamlit
st.set_page_config(page_title="Régua de Inativos - Jumbo CDP", page_icon="📦", layout="wide")

st.title("🔄 Disparador de Régua de Inativos")
st.markdown("Arraste o relatório de exportação do painel abaixo para segmentar e disparar os webhooks.")

# URLs dos Webhooks do seu n8n (Substitua pelas suas URLs oficiais de produção)
WEBHOOK_21_DIAS = "https://n8n.corcaqui.com.br/webhook/seu_gatilho_21_dias"
WEBHOOK_28_DIAS = "https://n8n.corcaqui.com.br/webhook/seu_gatilho_28_dias"

# Componente de Arrastar e Soltar o Arquivo CSV
uploaded_file = st.file_uploader("Arraste e solte o arquivo CSV de exportação aqui", type=["csv"])

if uploaded_file is not None:
    try:
        # Lendo o arquivo arrastado
        df = pd.read_csv(uploaded_file)
        
        # Garante que a coluna de Data está no formato correto
        df['Data'] = pd.to_datetime(df['Data'])
        
        # Define a data de referência como o dia de hoje
        today = pd.to_datetime(datetime.now().date())
        
        # Calcula a diferença de dias
        df['Days_Since'] = (today - df['Data']).dt.days
        
        # Segmentação dos grupos (Regra de corte)
        df_21 = df[df['Days_Since'] <= 24].drop(columns=['Days_Since'])
        df_28 = df[df['Days_Since'] >= 25].drop(columns=['Days_Since'])
        
        # Exibe as métricas na tela para validação
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="📊 Grupo 21 Dias (21 a 24 dias inativo)", value=f"{len(df_21)} clientes")
        with col2:
            st.metric(label="📊 Grupo 28 Dias (25 a 28 dias inativo)", value=f"{len(df_28)} clientes")
            
        st.divider()
        
        # Botão de Ação para Disparar os Webhooks
        if st.button("🚀 Iniciar Disparo para o n8n", type="primary"):
            
            sucesso = True
            
            # Envio do Grupo 21 Dias
            if len(df_21) > 0:
                payload_21 = df_21.to_dict(orient='records')
                try:
                    res_21 = requests.post(WEBHOOK_21_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_21))
                    if res_21.status_code in [200, 201]:
                        st.success(f"✅ {len(df_21)} contatos enviados com sucesso para a régua de 21 dias!")
                    else:
                        st.error(f"❌ Erro na régua de 21 dias. Status: {res_21.status_code}")
                        sucesso = False
                except Exception as e:
                    st.error(f"❌ Falha de conexão com o webhook de 21 dias: {e}")
                    sucesso = False
            
            # Envio do Grupo 28 Dias
            if len(df_28) > 0:
                payload_28 = df_28.to_dict(orient='records')
                try:
                    res_28 = requests.post(WEBHOOK_28_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_28))
                    if res_28.status_code in [200, 201]:
                        st.success(f"✅ {len(df_28)} contatos enviados com sucesso para a régua de 28 dias!")
                    else:
                        st.error(f"❌ Erro na régua de 28 dias. Status: {res_28.status_code}")
                        sucesso = False
                except Exception as e:
                    st.error(f"❌ Falha de conexão com o webhook de 28 dias: {e}")
                    sucesso = False
            
            if sucesso:
                st.balloons()
                st.success("🎉 Processamento concluído com sucesso em ambas as réguas!")

    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o arquivo: {e}")
