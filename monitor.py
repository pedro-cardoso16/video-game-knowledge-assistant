import streamlit as st
import pandas as pd
import psycopg as pg

def get_connection():
    return pg.connect(
        host=st.secrets["postgres"]["host"],
        port=st.secrets["postgres"]["port"],
        dbname=st.secrets["postgres"]["database"],
        user=st.secrets["postgres"]["user"],
        password=st.secrets["postgres"]["password"],
    )

conn = get_connection()

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

    with conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

        if cursor.description is None:
            return None

        columns = [desc[0] for desc in cursor.description]
    return pd.DataFrame(rows, columns=columns)

print(load_usage_data())
# GROUP BY 1, 2, 3, 4
# SUM(prompt_token_count) AS total_prompt_tokens,
#             SUM(candidates_token_count) AS total_candidates_tokens,
#             SUM(total_token_count) AS total_tokens,
#             SUM(cost_usd) AS cost