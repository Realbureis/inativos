import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# Configuração da página do Streamlit
st.set_page_config(page_title="Régua de Inativos exatos - Jumbo CDP", page_icon="📦", layout="wide")

st.title("🔄 Disparador de Régua de Inativos (Dia Exato)")
st.markdown("Arraste o relatório de 1 mês para disparar apenas para os clientes com **exatos 21 ou 28 dias** de inatividade.")

# URLs dos Webhooks do seu n8n
WEBHOOK_21_DIAS = "https://n8n.corcaqui.com.br/webhook/seu_gatilho_21_dias"
WEBHOOK_28_DIAS = "https://n8n.corcaqui.com.br/webhook/seu_gatilho_28_dias"

# Aceita tanto extensão .csv quanto .xlsx para garantir
uploaded_file = st.file_uploader("Arraste e solte o arquivo aqui (Aceita CSV ou Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        df = None
        
        # 1️⃣ TENTATIVA: Ler como arquivo Excel (Trata o erro do seu print)
        try:
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file)
        except Exception:
            pass
            
        # 2️⃣ TENTATIVA: Se falhar como Excel, lê como CSV tradicional (ponto e vírgula ou vírgula)
        if df is None or df.shape[1] <= 1:
            combinacoes = [
                (';', 'utf-8-sig'),
                (';', 'iso-8859-1'),
                (',', 'utf-8'),
                (';', 'utf-8'),
                (',', 'iso-8859-1')
            ]
            for sep, enc in combinacoes:
                try:
                    uploaded_file.seek(0)
                    temp_df = pd.read_csv(uploaded_file, sep=sep, encoding=enc, on_bad_lines='skip')
                    if temp_df.shape[1] > 1:
                        df = temp_df
                        break
                except Exception:
                    continue

        # Validação final da estrutura
        if df is None or 'Data' not in df.columns:
            st.error("❌ Não foi possível ler o arquivo. Verifique se a planilha possui a coluna chamada 'Data'.")
        else:
            # Força a conversão da coluna de data removendo horas/fuso se houver
            df['Data'] = pd.to_datetime(df['Data']).dt.tz_localize(None)
            
            # Data de referência (Hoje)
            today = pd.to_datetime(datetime.now().date())
            
            # Calcula a diferença exata de dias
            df['Days_Since'] = (today - df['Data']).dt.days
            
            # FILTRO DE PRECISÃO: Pega apenas o dia exato
            df_21 = df[df['Days_Since'] == 21].drop(columns=['Days_Since'])
            df_28 = df[df['Days_Since'] == 28].drop(columns=['Days_Since'])
            
            # Exibe as métricas na tela
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="🎯 Exatos 21 Dias Hoje", value=f"{len(df_21)} clientes")
            with col2:
                st.metric(label="🎯 Exatos 28 Dias Hoje", value=f"{len(df_28)} clientes")
                
            st.divider()
            
            if st.button("🚀 Iniciar Disparo para o n8n", type="primary"):
                sucesso = True
                
                # Envio exatos 21 dias
                if len(df_21) > 0:
                    payload_21 = df_21.to_dict(orient='records')
                    try:
                        res_21 = requests.post(WEBHOOK_21_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_21, default=str))
                        if res_21.status_code in [200, 201]:
                            st.success(f"✅ {len(df_21)} contatos de exatos 21 dias enviados!")
                        else:
                            st.error(f"❌ Erro no webhook de 21 dias. Status: {res_21.status_code}")
                            sucesso = False
                    except Exception as e:
                        st.error(f"❌ Falha de conexão (21 dias): {e}")
                        sucesso = False
                
                # Envio exatos 28 dias
                if len(df_28) > 0:
                    payload_28 = df_28.to_dict(orient='records')
                    try:
                        res_28 = requests.post(WEBHOOK_28_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_28, default=str))
                        if res_28.status_code in [200, 201]:
                            st.success(f"✅ {len(df_28)} contatos de exatos 28 dias enviados!")
                        else:
                            st.error(f"❌ Erro no webhook de 28 dias. Status: {res_28.status_code}")
                            sucesso = False
                    except Exception as e:
                        st.error(f"❌ Falha de conexão (28 dias): {e}")
                        sucesso = False
                
                if sucesso:
                    st.balloons()
                    st.success("🎉 Processamento de precisão concluído!")

    except Exception as e:
        st.error(f"Erro crítico ao processar o arquivo: {e}")
