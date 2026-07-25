import streamlit as st
import os
from dotenv import load_dotenv
from llm import RAGClient
from opensearchpy import OpenSearch

# Load environment variables
load_dotenv()

# --- Configuration ---
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "Opensearch16admin#")

# --- Clients Setup ---
@st.cache_resource
def get_rag_client():
    # Initialize OpenSearch client
    opensearch_client = OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=False, 
        verify_certs=False,
        # ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    # Initialize RAGClient from llm.py
    return RAGClient(search_engine=opensearch_client)

# --- Streamlit UI ---
st.set_page_config(page_title="Video Game Knowledge Assistant", page_icon="🎮")
st.title("🎮 Video Game Knowledge Assistant")
st.markdown("Ask me anything about video games! I'll use my search tools to find the most accurate information.")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display existing chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("What would you like to know about video games?"):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate assistant response
    with st.chat_message("assistant"):
        with st.spinner("Searching and thinking..."):
            try:
                rag_client = get_rag_client()
                response = rag_client.rag(prompt)
                st.markdown(response)
                # Add assistant response to history
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                error_msg = f"An error occurred: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})