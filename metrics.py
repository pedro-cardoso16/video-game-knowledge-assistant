from typing import Callable
import pandas as pd


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
    
    Returns:
        (hit rate, mean reciprocal rank, relevance matrix)
    """
    x = []

    for i in range(len(ground_truth)):
        r = []

        row = ground_truth.iloc[i, :]

        query = row["question"]
        doc_id = row["doc_id"]

        results = search_func(query)
        r = [1 if (result["_id"] == str(doc_id)) else 0 for result in results['hits']['hits']]

        x.append(r.copy())

    # Hit rate: Percentage of queries where the target document appeared in results.
    hr_score = sum(1 for row in x if 1 in row) / len(x)

    # Mean reciprocal rank: Average of 1/rank for the first correct document found.
    mrr_score = sum(1 / (i.index(1) + 1) if 1 in i else 0 for i in x) / len(x)

    return hr_score, mrr_score, pd.DataFrame(x)
