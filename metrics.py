import pandas as pd
from typing import Callable
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
    ground_truth: pd.DataFrame, search_func: Callable[[str], list[dict]]
) -> tuple[float, float, pd.DataFrame]:
    """
    Evaluates search performance across ground_truth queries in parallel.

    Returns:
        (hit rate, mean reciprocal rank, relevance matrix DataFrame)
    """
    x = []

    with ThreadPoolExecutor(max_workers=3) as executor:
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
            doc_id = future_to_doc[future]
            try:
                search_res = future.result()
                hits = search_res.get("hits", {}).get("hits", [])
                r = [1 if (str(hit["_id"]) == doc_id) else 0 for hit in hits]
            except Exception as e:
                print(f"Error during search query: {e}")
                r = []

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