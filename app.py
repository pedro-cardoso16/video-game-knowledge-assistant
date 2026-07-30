import streamlit as st
import os
import altair as alt
from dotenv import load_dotenv
from llm import RAGClient
from opensearchpy import OpenSearch
from ingest import save_usage_metadata, save_user_feedback
import psycopg as pg
import pandas as pd

# Load environment variables
load_dotenv()

# --- Configuration ---
OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "Opensearch16admin#")


# --- Clients Setup ---
def get_usage_connection():
    return pg.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        dbname=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
    )


def get_eval_connection():
    return pg.connect(
        host=st.secrets["postgres_evaluations"]["host"],
        port=st.secrets["postgres_evaluations"]["port"],
        dbname=st.secrets["postgres_evaluations"]["database"],
        user=st.secrets["postgres_evaluations"]["user"],
        password=st.secrets["postgres_evaluations"]["password"],
    )


@st.cache_resource
def get_rag_client(model="gemini-3.1-flash-lite"):
    # Initialize OpenSearch client
    opensearch_client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
        http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        use_ssl=False,
        verify_certs=False,
        # ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    # Initialize RAGClient from llm.py
    return RAGClient(search_engine=opensearch_client, model=model)


# --- Functions ---
@st.cache_data(ttl=600)  # cache results for 10 minutes
def load_usage_data():
    query = """
        SELECT
            date_trunc('second', created_at) AS day,
            model,
            prompt_token_count,
            candidates_token_count,
            total_token_count
        FROM usage
        WHERE created_at >= NOW() - INTERVAL '30 days'
        ORDER BY 1
    """
    
    try:
        with get_usage_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

                if cursor.description is None:
                    return pd.DataFrame() # Return empty DF if no description

                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame(rows, columns=columns)
    except pg.errors.UndefinedTable:
        # This happens the very first time the app is run before any queries are made
        return pd.DataFrame() 
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_feedback_data():
    query = """
        SELECT question, answer, answer_score, created_at
        FROM evaluations
        WHERE source = 'user'
        ORDER BY created_at
    """
    try:
        with get_eval_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
                if cursor.description is None:
                    return pd.DataFrame()
                columns = [desc[0] for desc in cursor.description]
        return pd.DataFrame(rows, columns=columns)
    except pg.errors.UndefinedTable:
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame()

# --- Streamlit UI ---
st.set_page_config(page_title="Video Game Knowledge Assistant", page_icon="🎮")
st.title("🎮 Video Game Knowledge Assistant")


(
    chat_tab,
    analytics_tab,
) = st.tabs(["✨ Chat", "📊 Analytics"])

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "gemini_history" not in st.session_state:
    st.session_state.gemini_history = []

if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = set()

# --- Model Configuration ---
# Define your default list of models here
AVAILABLE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
    "Custom",
]

# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.header("⚙️ Configuration")

    # 1. Model Selection Dropdown
    model_choice = st.selectbox(
        "Choose LLM Model",
        options=AVAILABLE_MODELS,
        index=0,  # Defaults to gemini-3.1-flash-lite
    )

    # 2. Custom Text Field (only shows if "Custom" is selected)
    if model_choice == "Custom":
        selected_model = st.text_input(
            "Enter Custom Model ID",
            value="gemini-3.1-flash-lite",
            help="Enter the exact model string from Google AI Studio",
        )
    else:
        selected_model = model_choice

    st.divider()

    if st.button("🔄 New conversation"):
        st.session_state.messages = []
        st.session_state.gemini_history = []
        st.rerun()

with chat_tab:
    st.header("Chat")
    st.markdown(f"Currently using model: `{selected_model}`")

    chat_container = st.container(height=500)

    # Instantiate the cached client with the selected model
    rag_client = get_rag_client(model=selected_model)

    # --- DISPLAY CHAT HISTORY ---
    with chat_container:
        for idx, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

                # REAL FEEDBACK LOGIC GOES HERE
                if message["role"] == "assistant" and "question" in message:
                    feedback_key = f"feedback_{idx}"
                    score = st.feedback("thumbs", key=feedback_key)

                    if (
                        score is not None
                        and feedback_key not in st.session_state.feedback_submitted
                    ):
                        label = "good" if score == 1 else "bad"
                        save_user_feedback(
                            get_eval_connection(),
                            message["question"],
                            message["content"],
                            label,
                        )
                        st.session_state.feedback_submitted.add(feedback_key)
                        st.toast("Feedback saved!")

    # --- HANDLE NEW INPUT ---
    if prompt := st.chat_input("What would you like to know about video games?"):
        # 1. Add user message to state
        st.session_state.messages.append({"role": "user", "content": prompt})

        # 2. Display user message immediately in the container
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

            # 3. Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("Searching and thinking..."):
                    try:
                        response, st.session_state.gemini_history = rag_client.rag(
                            prompt, history=st.session_state.gemini_history
                        )

                        # Handle usage metadata
                        for usage in rag_client.usage_history:
                            save_usage_metadata(
                                usage, get_usage_connection(), rag_client.model
                            )
                        rag_client.flush_usage_history()

                        st.markdown(response)

                        # Add assistant message to state
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": response,
                                "question": prompt,
                            }
                        )
                        # Force a rerun to show the feedback widget for the new message
                        st.rerun()

                    except Exception as e:
                        st.error(f"An error occurred: {e}")
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": f"Error: {e}",
                                "question": prompt,
                            }
                        )
                        st.rerun()

with analytics_tab:
    st.header("Analytics")
    st.markdown(
        "This is the analytics page, here you can see the usage and performance metrics of the llm agent"
    )

    if st.button("🔄 Refresh"):
        load_usage_data.clear()
        load_feedback_data.clear()

    df = load_usage_data()

    if df is None or df.empty:
        st.info("No usage data available for the last 30 days.")
    else:
        # --- Date range picker ---
        min_date = df["day"].min().date()
        max_date = df["day"].max().date()

        date_range = st.date_input(
            "Date range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        # Guard against a single date being selected before the range is complete
        if len(date_range) == 2:
            start_date, end_date = date_range
            mask = (df["day"].dt.date >= start_date) & (df["day"].dt.date <= end_date)
            filtered = df.loc[mask]

            if filtered.empty:
                st.info("No usage data available for the selected date range.")
            else:
                # --- Bar chart: tokens over time ---
                daily = filtered.groupby("day")[
                    [
                        "total_token_count",
                        "prompt_token_count",
                        "candidates_token_count",
                    ]
                ].sum()

                st.line_chart(
                    daily,
                    x_label="Call time",
                    y_label="Tokens",
                )

                # --- Donut chart: total tokens by model ---
                st.subheader("Total tokens by model")

                by_model = (
                    filtered.groupby("model")["total_token_count"].sum().reset_index()
                )

                donut = (
                    alt.Chart(by_model)
                    .mark_arc(innerRadius=60)
                    .encode(
                        theta=alt.Theta("total_token_count:Q", title="Total tokens"),
                        color=alt.Color("model:N", title="Model"),
                        tooltip=["model:N", "total_token_count:Q"],
                    )
                )

                st.altair_chart(donut, use_container_width=True)
        else:
            st.info("Select both a start and end date to view the charts.")

    st.subheader("User feedback")

    feedback_df = load_feedback_data()

    if feedback_df is None or feedback_df.empty:
        st.info("No user feedback yet.")
    else:
        good_count = (feedback_df["answer_score"] == "good").sum()
        bad_count = (feedback_df["answer_score"] == "bad").sum()
        total = good_count + bad_count

        col1, col2, col3 = st.columns(3)
        col1.metric("👍 Good", good_count)
        col2.metric("👎 Bad", bad_count)
        col3.metric(
            "Satisfaction rate",
            f"{(good_count / total * 100):.1f}%" if total else "N/A",
        )

        counts = feedback_df["answer_score"].value_counts().reset_index()
        counts.columns = ["score", "count"]

        donut = (
            alt.Chart(counts)
            .mark_arc(innerRadius=60)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color(
                    "score:N",
                    scale=alt.Scale(
                        domain=["good", "bad"], range=["#2ecc71", "#e74c3c"]
                    ),
                ),
                tooltip=["score:N", "count:Q"],
            )
        )
        st.altair_chart(donut, use_container_width=True)
