"""
This module is responsible for creating the ground_truth for the database

"""

import random
from dataclasses import dataclass
from query import ops_client
from llm import RAGClient
from pydantic import BaseModel
import pandas as pd
from typing import cast
from tqdm import tqdm
import time
from opensearchpy import OpenSearch

INSTRUCTION = """
You should create {count} questions based on the providade information.

Avoid using exact match words. Try to make very different questions that would 
have as a search result the provided document CONTEXT. On top of that, the 
questions should be similar to how people ask things on the internet, not too 
long and not too short. 

Your answer has to be a python `list[str]` with {count} elements

CONTEXT:
{context}
""".strip()


class GTOutput(BaseModel):
    """Ground truth output"""
    questions: list[str]


def generate_ground_truth(
    ai: RAGClient, index_name: str, count: int = 5, n: int = 100
) -> pd.DataFrame:
    """Generate ground truth.

    Args:
        ai (RAGClient): RAGClient client instance.
        index_name (str): Name of the OpenSearch index.
        count (int, optional): Number of questions to generate per document. Defaults to `5`.
        n (int, optional): Number of randomly selected documents. Defaults to `100`.

    Returns:
        pd.DataFrame: DataFrame with columns ``question`` and ``doc_id``.
    """
    questions = []
    doc_id = []

    body = { 
        "size": 10000,
        "query": {
            "match_all": {},
        },
    }

    results = ops_client.search(body=body, index=index_name)["hits"]["hits"]

    print(len(results))
    results = random.sample(results, n)

    for result in tqdm(results):
        context = result["_source"]

        doc_id.extend([result["_id"]] * count)

        answer = ai.llm(
            str(result["_source"]),
            config={
                "system_instruction": INSTRUCTION.format(count=count, context=context),
                "response_schema": GTOutput,
                "response_mime_type": "application/json",
            },
        )
        time.sleep(4)
        parsed = cast(GTOutput, answer.parsed)

        questions.extend(parsed.questions)

    return pd.DataFrame({"question": questions, "doc_id": doc_id})


if __name__ == "__main__":
    pass
    # print(ops_client.cat.indices())
    # index_name = "igdb_2026-07-14-162716"

    # ops_client = OpenSearch(
    #     hosts=[{"host": "localhost", "port": 9200}],
    #     http_auth=("admin", "Opensearch16admin#"),
    #     use_ssl=True,
    #     verify_certs=False,  # Set to True if using valid certificates
    #     ssl_show_warn=False,
    # )
    # gt = generate_ground_truth(AI(ops_client), index_name=index_name, count=5)

    # print(ops_client.count(index=index_name))

    # gt.to_csv("data/ground_truth_2.csv")
