import streamlit as st
from models.hybrid_search_retreiver import HybridSearchRetriever
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain.schema import HumanMessage
from pathlib import Path

path = Path(__file__).parent.resolve()
hybrid_search_retriever = HybridSearchRetriever()
st.set_page_config(page_title='Netec Bot', layout='wide')
st.subheader("Netec Chatbot")

# Asegúrate de que los estados necesarios están inicializados
if "generated" not in st.session_state:
    st.session_state["generated"] = []
if "past" not in st.session_state:
    st.session_state["past"] = []
if "input" not in st.session_state:
    st.session_state["input"] = ""
if "stored_session" not in st.session_state:
    st.session_state["stored_session"] = []
if "conversation_history" not in st.session_state:  # Historial de conversación
    st.session_state["conversation_history"] = []

def handle_user_input(user_input):
    human_message = HumanMessage(content=user_input)
    
    # Añade el mensaje del usuario al historial de conversación
    st.session_state.conversation_history.append(human_message)
    
    # Genera una respuesta utilizando el historial de conversación
    response_content = hybrid_search_retriever.rag(human_message, conversation_history=st.session_state.conversation_history)
    return response_content

def get_text():
    input_text = st.text_input(":female-technologist: Tú:", st.session_state["input"], key="input",
                               placeholder="¿En qué puedo ayudarte hoy?",
                               label_visibility='visible')
    return input_text

user_input = get_text()
if user_input:
    with st.spinner(":robot_face: escribiendo..."):
        output = handle_user_input(user_input)
    st.session_state.past.append(user_input)
    st.session_state.generated.append(output)
    

    for i in range(len(st.session_state['generated']) - 1, -1, -1):
        st.write(f"Tú: {st.session_state['past'][i]}")
        st.write(f"Bot: {st.session_state['generated'][i]}")