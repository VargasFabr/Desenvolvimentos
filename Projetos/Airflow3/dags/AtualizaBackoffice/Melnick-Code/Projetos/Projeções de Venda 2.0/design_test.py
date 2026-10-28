import streamlit as st

# Configuração da página
st.set_page_config(layout="wide", page_title="Funil de Vendas")

# CSS customizado para os cards e colunas
st.markdown("""
<style>
    .kanban-column {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        min-height: 80vh;
    }
    .column-header {
        text-align: center;
        font-weight: bold;
        padding: 10px;
        margin-bottom: 20px;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .card {
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 15px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .card-title { font-weight: bold; font-size: 14px; margin-bottom: 5px; }
    .card-sub { font-size: 12px; opacity: 0.9; }
    
    /* Cores baseadas na imagem */
    .purple-card { background-color: #b388ff; }
    .red-card { background-color: #eb716d; }
    .blue-card { background-color: #74b3ff; }
    .green-card { background-color: #9ccc65; }
    .orange-card { background-color: #f3b688; }
</style>
""", unsafe_allow_html=True)

# Estrutura de colunas do Streamlit
cols = st.columns(4)
titles = ["Qualificação", "Apresentação", "Maturação", "Fechamento"]

# Renderização do Funil
for i, col in enumerate(cols):
    with col:
        st.markdown(f'<div class="column-header">{titles[i]}</div>', unsafe_allow_html=True)
        
        if i == 0: # Qualificação
            st.markdown('''
                <div class="card purple-card">
                    <div class="card-title">✓ Criar uma sequência de e-mails</div>
                    <div class="card-sub">Mensagem criada com Smart AI</div>
                </div>
            ''', unsafe_allow_html=True)
            
        elif i == 1: # Apresentação
            st.markdown('''
                <div class="card red-card">
                    <div class="card-title">✓ Preencher campos obrigatórios</div>
                    <div class="card-sub">Valor: 15.200,00<br>Gestão com Easy Flow</div>
                </div>
                <div class="card orange-card">
                    <div class="card-title">✓ Distribuir entre equipe</div>
                    <div class="card-sub">Automação do funil</div>
                </div>
            ''', unsafe_allow_html=True)

        elif i == 2: # Maturação
            st.markdown('''
                <div class="card blue-card">
                    <div class="card-title">✓ Acompanhar Cliente no Whatsapp</div>
                    <div class="card-sub">Conversa sincronizada</div>
                </div>
            ''', unsafe_allow_html=True)

        elif i == 3: # Fechamento
            st.markdown('''
                <div class="card green-card">
                    <div class="card-title">✓ Notificar quando fechar</div>
                    <div class="card-sub">Automação de notificação</div>
                </div>
            ''', unsafe_allow_html=True)