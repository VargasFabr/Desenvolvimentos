# Chatbot de suporte com documentos da pasta suporte/

import torch
import streamlit as st
from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.ollama import Ollama

# O Streamlit e o PyTorch brigam pelo caminho interno de classes.
torch.classes.__path__ = []

DISPOSITIVO = "cuda" if torch.cuda.is_available() else "cpu"

st.set_page_config(page_title="Suporte", page_icon=":speech_balloon:", layout="centered")
st.title("Suporte ao cliente")
st.caption("Respostas a partir dos documentos em ./suporte. Embeddings em %s." % DISPOSITIVO)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Digite sua pergunta sobre frete, contato, fidelidade ou retirada."}
    ]

# Ollama usa a GPU por conta própria quando o serviço foi instalado com CUDA.
# O parâmetro daqui só coloca o modelo de embeddings na placa.
Settings.llm = Ollama(model="llama3.1", timeout=300)
Settings.embed_model = HuggingFaceEmbedding(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    device=DISPOSITIVO,
)


@st.cache_resource
def indice():
    documentos = SimpleDirectoryReader(input_dir="./suporte", recursive=True).load_data()
    return VectorStoreIndex.from_documents(documentos)


if "chat_engine" not in st.session_state:
    st.session_state.chat_engine = indice().as_chat_engine(chat_mode="condense_question", verbose=True)

pergunta = st.chat_input("Sua pergunta")
if pergunta:
    st.session_state.messages.append({"role": "user", "content": pergunta})

for mensagem in st.session_state.messages:
    with st.chat_message(mensagem["role"]):
        st.write(mensagem["content"])

if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            texto = st.session_state.messages[-1]["content"]
            pedido = (
                "Você é um atendente de suporte. Use os documentos de perguntas e respostas. "
                "Responda em português e recomende o próximo passo quando fizer sentido. Pergunta: %s" % texto
            )
            resposta = st.session_state.chat_engine.chat(pedido).response
            st.write(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})
