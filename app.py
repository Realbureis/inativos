import streamlit as st
import pandas as pd
import io
import requests
import re
from datetime import datetime, timedelta

# 1. Configuração da Página
st.set_page_config(page_title="Jumbo CDP - Recompra de Inativos", layout="wide", page_icon="🔁")

def tratar_primeiro_nome(texto):
    """Extrai apenas o primeiro nome em Title Case"""
    txt = str(texto).strip()
    if not txt or txt.lower() in ["nan", "none", "0", "-"]:
        return "N/A"
    return txt.split()[0].title()

def formatar_data_bq(texto):
    """Converte DD/MM/YYYY para YYYY-MM-DD para o BigQuery entender como DATE"""
    txt = str(texto).strip()
    match = re.search(r'(\d{2})/(\d{2})/(\d{4})', txt)
    if match:
        dia, mes, ano = match.groups()
        return f"{ano}-{mes}-{dia}"
    return txt

def limpar_valor_monetario(valor):
    """Transforma 'R$ 1.250,50' em '1250.50' para o BigQuery entender como número"""
    v = str(valor).replace('R$', '').strip()
    if not v or v.lower() in ["nan", "none"]:
        return "0.00"
    v = v.replace('.', '').replace(',', '.')
    v = re.sub(r'[^0-9.]', '', v)
    return v

def processar_fone_jumbo(row):
    """Fallback Fixo > Celular | Limpa | Adiciona 55"""
    fixo = str(row.get('Fone Fixo', '')).strip()
    cel = str(row.get('Celular', '')).strip()
    bruto = fixo if fixo and fixo.lower() not in ["nan", "none", "0", ""] else cel
    limpo = re.sub(r'\D', '', bruto)
    if limpo and len(limpo) >= 8:
        return '55' + limpo if not limpo.startswith('55') else limpo
    return None

st.title("🔁 Filtro de Recompra (Inativos 21-28 dias) | Jumbo CDP")
st.markdown("---")

# Input de dados em formato de Área de Texto (Copia e Cola do Relatório Consolidado)
st.subheader("1. Relatório de Vendas")
input_vendas = st.text_area("Cole os dados brutos do relatório de vendas aqui (Copie do Excel/Planilha e cole diretamente):", height=250)

if input_vendas:
    try:
        # Lê os dados tabulados colados
        df_bruto = pd.read_csv(io.StringIO(input_vendas), sep='\t', dtype=str).fillna("")
        
        # Garante a filtragem correta apenas para o Jumbo CDP
        if 'Empresa' in df_bruto.columns:
            df_bruto = df_bruto[df_bruto['Empresa'] == 'Jumbo CDP'].copy()
            
        # Converter coluna de Data para objeto datetime para realizar os cálculos matemáticos de intervalo
        df_bruto['Data_Obj'] = pd.to_datetime(df_bruto['Data'], format='%d/%m/%Y', errors='coerce')
        
        # Filtrar apenas compras que geraram receita de fato (Removendo "Pedido Salvo" e "Cancelado" da análise de sucesso)
        # Deixamos apenas o que foi despachado ou aprovado pelo banco
        status_sucesso = ['Enviado', 'Pagamento Efetuado']
        df_sucesso = df_bruto[df_bruto['Status'].isin(status_sucesso)].copy()
        
        if df_sucesso.empty:
            st.warning("⚠️ Nenhum pedido com status 'Enviado' ou 'Pagamento Efetuado' foi encontrado nos dados colados.")
        else:
            # --- REGRA DE OURO DA INATIVIDADE ---
            # Identificar a data exata do ÚLTIMO pedido de sucesso que cada cliente fez na história recente
            df_ultimo_pedido = df_sucesso.sort_values('Data_Obj').groupby('Codigo Cliente').last().reset_index()
            
            # Definir a janela de corte retroativa baseada na data atual de execução do sistema
            hoje = datetime.now().date()
            data_limite_21 = hoje - timedelta(days=21)
            data_limite_28 = hoje - timedelta(days=28)
            
            # Filtrar os clientes cujo ÚLTIMO pedido caiu estritamente entre 21 e 28 dias atrás
            # (Note que "menor ou igual a 21" e "maior ou igual a 28" em termos de datas passadas)
            df_inativos = df_ultimo_pedido[
                (df_ultimo_pedido['Data_Obj'].dt.date <= data_limite_21) & 
                (df_ultimo_pedido['Data_Obj'].dt.date >= data_limite_28)
            ].copy()
            
            if df_inativos.empty:
                st.info("ℹ️ Nenhum cliente elegível encontrado na janela exata de 21 a 28 dias de inatividade para as datas inseridas.")
            else:
                # Mapeamento e limpeza de telefone com fallback
                df_inativos['Fone Fixo'] = df_inativos.apply(processar_fone_jumbo, axis=1)
                df_inativos = df_inativos.dropna(subset=['Fone Fixo']).copy()
                
                # Formatação das colunas para compatibilidade com BigQuery e n8n
                for col in df_inativos.columns:
                    c_up = str(col).upper()
                    if "DATA" in c_up and col != 'Data_Obj':
                        df_inativos[col] = df_inativos[col].apply(formatar_data_bq)
                    if any(x in c_up for x in ["VALOR", "TOTAL", "PRECO", "FRETE"]):
                        df_inativos[col] = df_inativos[col].apply(limpar_valor_monetario)
                
                # Tratamento de primeiro nome para personalização do WhatsApp no n8n
                if 'Cliente' in df_inativos.columns:
                    df_inativos['Cliente'] = df_inativos['Cliente'].apply(tratar_primeiro_nome)
                if 'Ultimo Detento Cadastrado' in df_inativos.columns:
                    df_inativos['Ultimo Detento Cadastrado'] = df_inativos['Ultimo Detento Cadastrado'].apply(tratar_primeiro_nome)
                
                # Isolar apenas as colunas essenciais e limpas que serão transmitidas para o fluxo do n8n
                colunas_envio = [
                    'N. Pedido', 'Data', 'Codigo Cliente', 'Cliente', 'Fone Fixo', 
                    'Ultimo Detento Cadastrado', 'Unidade Prisional', 'Valor Total', 'Status'
                ]
                # Filtrar apenas as colunas que existem no dataframe final por segurança
                colunas_existentes = [c for c in colunas_envio if c in df_inativos.columns]
                df_envio = df_inativos[colunas_existentes].copy()
                
                # Interface Visual do Streamlit
                st.success(f"✅ {len(df_envio)} clientes únicos identificados na janela de recompra (21 a 28 dias)!")
                st.dataframe(df_envio, use_container_width=True)
                
                st.divider()
                
                # Campo para o Webhook do n8n (com a URL padrão da sua estrutura)
                webhook = st.text_input("URL do Webhook do n8n (Fluxo de Recompra):", value="https://n8n.corcaqui.com.br/webhook/recompra-inativos")
                
                # Botão de Disparo
                if st.button("Confirmar Envio para o n8n"):
                    payload = df_envio.to_dict(orient='records')
                    # Dispara o lote completo para o nó de Webhook do n8n
                    res = requests.post(webhook, json=payload, timeout=45)
                    
                    if res.status_code in [200, 201]:
                        st.balloons()
                        st.success("🚀 Lista de inativos transmitida com sucesso para o n8n! O gatilho de mensagens foi ativado.")
                    else:
                        st.error(f"Falha no envio. Erro retornado pelo servidor: {res.status_code}")
                        
    except Exception as e:
        st.error(f"Erro ao processar o relatório: {e}")
