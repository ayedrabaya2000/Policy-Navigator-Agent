from dotenv import load_dotenv
load_dotenv()
import os
import streamlit as st
from regulation_query_facade import PolicyNavigatorFacade
from handlers.uploaded_document_query_handler import UploadedDocumentQueryHandler
try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    class SlackNotifier:
        def __init__(self, token: str, channel: str):
            self.client = WebClient(token=token)
            self.channel = channel
        def send_message(self, text: str):
            try:
                self.client.chat_postMessage(channel=self.channel, text=text)
            except SlackApiError as e:
                print(f"Slack API error: {e.response['error']}")
except ImportError:
    SlackNotifier = None
st.set_page_config(page_title="Policy Navigator", layout="wide")
st.markdown("""
    <style>
    .main {
        background-color: #f7f9fa;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .header-bar {
        background: linear-gradient(90deg, #2b5876 0%, #4e4376 100%);
        color: white;
        padding: 1.5rem 2rem 1rem 2rem;
        border-radius: 0 0 1.5rem 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 2px 8px rgba(44,62,80,0.08);
    }
    .header-title {
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        margin-bottom: 0.2rem;
    }
    .header-desc {
        font-size: 1.1rem;
        font-weight: 400;
        opacity: 0.85;
    }
    .stButton>button {
        border-radius: 0.5rem;
        font-weight: 600;
        background: #2b5876;
        color: white;
        border: none;
        padding: 0.6rem 1.5rem;
        margin-top: 0.5rem;
    }
    .stTextInput>div>input {
        border-radius: 0.5rem;
        border: 1px solid #d1d5db;
        padding: 0.7rem 1rem;
        font-size: 1.1rem;
    }
    .stTextArea>div>textarea {
        border-radius: 0.5rem;
        border: 1px solid #d1d5db;
        padding: 0.7rem 1rem;
        font-size: 1.1rem;
    }
    .stSelectbox>div>div>div>div {
        border-radius: 0.5rem;
        border: 1px solid #d1d5db;
        font-size: 1.1rem;
    }
    .stSidebar {
        background: #0000;
    }
    .stAlert {
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)
slack_token = os.environ.get("SLACK_TOKEN")
slack_channel = os.environ.get("SLACK_CHANNEL")
facade = PolicyNavigatorFacade(slack_token=slack_token, slack_channel=slack_channel)
slack_notifier = None
if SlackNotifier and slack_token and slack_channel:
    slack_notifier = SlackNotifier(slack_token, slack_channel)
st.markdown(
    '<div class="header-bar">'
    '<div class="header-title">Policy Navigator Agent</div>'
    '<div class="header-desc">Multi-Agent RAG System for Government Regulation Search</div>'
    '</div>',
    unsafe_allow_html=True
)
col1, col2 = st.columns([2, 5])
with col1:
    query_type = st.selectbox(
        "Select query type:",
        [
            "Vehicle Code",
            "EPA",
            "Federal Register",
            "Uploaded Documents",
            "CourtListener"
        ],
        key="query_type_top"
    )
with col2:
    st.write("")
st.sidebar.header("Upload Document or Specify URL")
st.sidebar.markdown("---")
uploaded_files = st.sidebar.file_uploader("Choose files (PDF, TXT)", type=["pdf", "txt"], accept_multiple_files=True)
url_input = st.sidebar.text_input("Or enter a public URL")
if st.sidebar.button("Ingest Document/URL"):
    results = []
    if uploaded_files:
        import tempfile
        for uploaded_file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix="." + uploaded_file.name.split('.')[-1]) as tmp_file:
                tmp_file.write(uploaded_file.read())
                tmp_path = tmp_file.name
            result = facade.handle_upload(tmp_path)
            results.append(f"{uploaded_file.name}: {result}")
    if url_input:
        result = facade.handle_upload(url_input)
        results.append(f"URL: {result}")
    if results:
        st.sidebar.success("\n".join(results))
    else:
        st.sidebar.warning("Please upload at least one file or enter a URL.")
st.markdown("---")
st.header(f"Ask a question about {query_type}")
user_query = st.text_area("Enter your question:")
if st.button("Submit Query"):
    result = None
    if query_type == "Vehicle Code":
        result = facade.handle_query("vehicle code: " + user_query)
        st.success(result)
    elif query_type == "EPA":
        result = facade.handle_query("epa: " + user_query)
        st.success(result)
    elif query_type == "Federal Register":
        result = facade.handle_query("federal register: " + user_query)
        st.success(result)
    elif query_type == "Uploaded Documents":
        handler = UploadedDocumentQueryHandler()
        result = handler.run(user_query)
        st.success(result)
    elif query_type == "CourtListener":
        result = facade.handle_query("courtlistener: " + user_query)
        st.success(result)
    if slack_notifier and result is not None:
        try:
            slack_notifier.send_message(f"Query: {user_query}\nResponse: {result}")
        except Exception as e:
            st.warning(f"Warning: Failed to post to Slack: {e}") 