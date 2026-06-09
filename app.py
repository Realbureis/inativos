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

uploaded_file = st.file_uploader("Arraste e solte o arquivo CSV aqui", type=["csv"])

if uploaded_file is not None:
    try:
        # TENTATIVA AUTOMÁTICA DE LEITURA (Encoding + Separadores)
        df = None
        # Lista de combinações comuns para testar (Separador, Encoding)
        combinacoes = [
            (';', 'utf-8-sig'), # UTF-8 com assinatura BOM (Excel comum)
            (';', 'iso-8859-1'), # Padrão Windows/América Latina
            (',', 'utf-8'),
            (';', 'utf-8'),
            (',', 'iso-8859-1')
        ]
        
        for sep, enc in combinacoes:
            try:
                uploaded_file.seek(0) # Reseta o arquivo para o início a cada tentativa
                # on_bad_lines='skip' ignora linhas de rodapé ou sujeiras que quebram o CSV
                temp_df = pd.read_csv(uploaded_file, sep=sep, encoding=enc, on_bad_lines='skip')
                
                # Validação: o arquivo precisa ter mais de 1 coluna para ser considerado válido
                if temp_df.shape[1] > 1 and 'Data' in temp_df.columns:
                    df = temp_df
                    break
            except Exception:
                continue

        # Se passou por todos os testes e não conseguiu ler estruturado
        if df is None:
            st.error("❌ Não foi possível identificar a estrutura do CSV automaticamente. Verifique se a coluna de 'Data' existe no arquivo.")
        else:
            # Força a conversão da coluna de data
            df['Data'] = pd.to_datetime(df['Data'])
            
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
                        res_21 = requests.post(WEBHOOK_21_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_21))
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
                        res_28 = requests.post(WEBHOOK_28_DIAS, headers={"Content-Type": "application/json"}, data=json.dumps(payload_28))
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
