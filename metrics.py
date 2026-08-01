import pandas as pd
import time
import psycopg as pg

from typing import Callable, Any
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed


def hit_rate(ground_truth: pd.DataFrame, results):
    pass


def rrf():
    """Reciprocal Rank Fusion"""
    pass


reciprocal_rank_fusion = rrf


def mrr(relevance_matrix: list[list]):
    """Mean Reciprocal Rank"""
    return sum(1 / (i.index(1) + 1) if 1 in i else 0 for i in relevance_matrix) / len(
        relevance_matrix
    )


mean_reciprocal_rank = mrr


def evaluate_search(
    ground_truth: pd.DataFrame,
    search_func: Callable[[str], Any],
    max_workers: int = 3,
) -> tuple[float, float, pd.DataFrame]:
    """
    Evaluates search performance across ground_truth queries in parallel.

    Returns:
        (hit rate, mean reciprocal rank, relevance matrix DataFrame)
    """
    x = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Step 1: Map each Future object to its expected doc_id
        future_to_doc = {}
        for i in range(len(ground_truth)):
            row = ground_truth.iloc[i, :]
            query = row["question"]
            doc_id = str(row["doc_id"])

            # Submit task asynchronously (DO NOT call .result() here!)
            future = executor.submit(search_func, query)
            future_to_doc[future] = doc_id

        # Step 2: Process results as they complete concurrently
        for future in tqdm(
            as_completed(future_to_doc),
            total=len(future_to_doc),
            desc="Evaluating Search",
        ):
            # Introduce a small delay to avoid hitting OpenSearch memory circuit breakers
            time.sleep(0.1)

            doc_id = future_to_doc[future]

            r = []
            attempts = 0
            max_attempts = 5

            # wait_time = 5
            while attempts < max_attempts:
                try:
                    search_res = future.result()
                    hits = search_res.get("hits", {}).get("hits", [])
                    r = [1 if (str(hit["_id"]) == doc_id) else 0 for hit in hits]
                    break  # Success! Exit the retry loop
                except Exception as e:
                    attempts += 1
                    if (
                        "circuit_breaking_exception" in str(e)
                        and attempts < max_attempts
                    ):
                        print(
                            f"\n ⚠️ Circuit Breaker hit! Attempt {attempts}/{max_attempts}. Waiting 5s to recover..."
                        )
                        time.sleep(5)
                        # Note: The future is already failed. In a real scenario,
                        # the retry would happen inside search_func or by resubmitting the task.
                        # Here we are catching the result of a failed future.
                    else:
                        print(
                            f"Error during search query after {attempts} attempts: {e}"
                        )
                        break

            x.append(r)

    # Hit rate: Percentage of queries where the target document appeared in results
    hr_score = sum(1 for row in x if 1 in row) / len(x) if x else 0.0

    # Mean reciprocal rank: Average of 1/rank for the first correct document found
    mrr_score = (
        sum(1 / (row.index(1) + 1) if 1 in row else 0 for row in x) / len(x)
        if x
        else 0.0
    )

    return hr_score, mrr_score, pd.DataFrame(x)


def get_eval_connection():
    return pg.connect(
        dbname="evaluations",
        user="user",
        password="postgres",
        host="localhost",
        port="5432",
    )


def get_usage_connection():
    return pg.connect(
        dbname="usage",
        user="user",
        password="postgres",
        host="localhost",
        port="5432",
    )


def load_judge_feedback_data():
    query = """
        SELECT question, answer, reasoning, answer_score, tool_score, created_at
        FROM evaluations
        WHERE source = 'judge'
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
