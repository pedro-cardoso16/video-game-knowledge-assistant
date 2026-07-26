"""ingest.py

This script does the scrap of the IGDB. In other to do this you must have a developer
account.

Only use this script if you intend to update the database with recent information.

Four requests per second
"""

import datasets
import re
import os
import requests
import json
import pandas as pd
import psycopg as pg

from google.genai.types import GenerateContentResponseUsageMetadata

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from opensearch_utils import create_index_with_semantic_search, get_models

from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from query import opensearch_client
from dotenv import load_dotenv

opensearch_client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=("admin", "Opensearch16admin#"),
    use_ssl=False,
    verify_certs=False,  # Set to True if using valid certificates
    ssl_show_warn=False,
)


class NullFile:
    """A dummy file object that does nothing."""

    def write(self, data):
        pass

    def flush(self):
        pass

    def fileno(self):
        return -1

    def close(self):
        pass


class IGDB:
    def __init__(self, opensearch_client: OpenSearch) -> None:
        self.BASE_URL = "https://api.igdb.com/v4"
        self.opensearch_client = opensearch_client

        load_dotenv()

        with open("info.json") as f:
            info = dict(json.load(f))

        self.headers = {
            "Client-ID": os.getenv("IGDB_CLIENT_ID"),
            "Authorization": f"Bearer {info["access_token"]}",
        }

    def download(
        self,
        max_workers: int = 16,
        index: str | None = None,
        model_id: str | None = None,
    ) -> None:
        """Pull everything from IGDB and ingest.

        Args:
            max_workers (int): maximum number of threads to use in the indexing
                process, **not** the request processes
            index (str | None): index name target to save the igdb database.
            model_id (str | None): model id to use for embedding.
        """

        GET_MAX_ID_BODY = "fields id; sort id desc; limit 1;"

        GET_ALL_FIELDS_IN_ID_RANGE_BODY = (
            "fields *; where id >= {min_id} & id < {max_id}; sort id asc; limit 500;"
        )

        # Get current max id in IGDB.
        max_id = self.fetch(GET_MAX_ID_BODY).json()[0]["id"]

        if index is None:
            index = "index"

        # index = "igdb_" + datetime.now().isoformat(sep="-", timespec="seconds").replace(
        #     ":", ""
        # )

        if model_id is None:
            model_id = get_models(self.opensearch_client)[0]

        create_index_with_semantic_search(
            self.opensearch_client,
            index,
            model_id,
            [
                "name",
                "storyline",
                "summary",
            ],
        )

        # self.opensearch_client.indices.create(
        #     index=index,
        #     body={
        #         "mappings": {
        #             "dynamic": "true",
        #         },
        #         "settings": {
        #             "number_of_replicas": 0,
        #         },
        #     },
        # )

        for i in tqdm(range(1, max_id + (max_id % 500), 500)):
            b = GET_ALL_FIELDS_IN_ID_RANGE_BODY.format(min_id=i, max_id=i + 500)
            content = list(self.fetch(b).json())

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                executor.map(lambda x: self.ingest(x, index), content)

    def fetch(self, body: str) -> requests.Response:
        return requests.post(
            f"{self.BASE_URL}/games",
            headers=self.headers,
            data=body,
            timeout=10,
        )

    def ingest(self, content: dict, index):
        doc_id = content["id"]
        content.pop("id")
        opensearch_client.index(index=index, body=content, id=doc_id)
        opensearch_client.indices.refresh(index=index)


body = "fields *; where id >= 1 & id <= 500; sort id asc; limit 500;"


# --- Vector/semantic search embedding ---
def setup_vector_search(index_name, model_id):
    """Create hybrid search index with minimal code"""

    # Create embedding pipeline
    opensearch_client.ingest.put_pipeline(
        id="hybrid-pipeline",
        body={
            "processors": [
                {
                    "text_embedding": {
                        "model_id": model_id,
                        "field_map": {
                            "name": "name_vector",
                            "summary": "summary_vector",
                            "storyline": "storyline_vector",
                            # "keywords": "keywords_vector",
                        },
                    }
                }
            ]
        },
    )

    # Create new index with vector fields
    new_index_name = f"{index_name}_hybrid"
    vector_field = {
        "type": "knn_vector",
        "dimension": 384,
        "method": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "lucene",
        },
    }

    if opensearch_client.indices.exists(index=new_index_name):
        opensearch_client.indices.delete(index=new_index_name)

    opensearch_client.indices.create(
        index=new_index_name,
        body={
            "settings": {"default_pipeline": "hybrid-pipeline", "index.knn": True},
            "mappings": {
                "dynamic": True,  # Copies all existing fields automatically
                "properties": {
                    "name_vector": vector_field,
                    "summary_vector": vector_field,
                    "storyline_vector": vector_field,
                    # "keywords_vector": vector_field,
                },
            },
        },
    )

    # Reindex with pipeline (generates vectors automatically)
    opensearch_client.reindex(
        body={
            "source": {"index": index_name},
            "dest": {"index": new_index_name},
        },
        params={"wait_for_completion": "false", "slices": "auto"},
    )

    return new_index_name


class Wikipedia:
    def __init__(self, opensearch_client: OpenSearch) -> None:
        self.opensearch_client = opensearch_client
        pass

    def download(
        self,
        index: str = "wikipedia",
        model_id: str | None = None,
        file_path: str | None = None,
    ) -> None:
        """Ingests Wikipedia video game articles into OpenSearch.

        Performs the ingestion of Wikipedia articles jointly with embedding.
        It uses a simple keyword-matching approach to identify relevant articles.

        Args:
            index (str): The name of the OpenSearch index to create and populate.
                Defaults to `"wikipedia"`.
            model_id (str, optional): The ID of the ML model to use for embeddings.
                If `None`, the first available model is used. Defaults to `None`.
            file_path (str, optional): Path to a file where matched articles
                will be saved in JSONL format. If `None`, no file is saved.
                Defaults to `None`.
        """
        dataset = datasets.load_dataset(
            "wikimedia/wikipedia", "20231101.en", split="train"
        )
        # Split keywords by signal strength
        strong_keywords = {
            "video game",
            "video games",
            "gameplay",
            "game engine",
            "game console",
            "gaming console",
            "platformer",
            "rpg",
            "fps",
        }
        brand_keywords = {"playstation", "xbox", "nintendo", "sega", "game boy"}

        if model_id is None:
            model_id = get_models(self.opensearch_client)[0]

        create_index_with_semantic_search(
            opensearch_client,
            index_name=index,
            model_id=model_id,
            semantic_fields=["title", "text"],
        )

        f = open(file_path, "w", encoding="utf-8") if file_path else NullFile()

        count = 0
        batch = []
        batch_size = 500

        for article in tqdm(dataset):
            article = dict(article)
            text_lower = article["text"].lower()
            title_lower = article["title"].lower()

            # 1. Check Title: Very high signal
            title_match = any(
                re.search(rf"\b{re.escape(kw)}\b", title_lower)
                for kw in strong_keywords | brand_keywords
            )

            # 2. Check Lead Text: Medium signal
            # We require at least TWO matches in the lead text to reduce noise,
            # OR one very strong keyword.
            lead_text = text_lower[:2000]
            strong_match = any(
                re.search(rf"\b{re.escape(kw)}\b", lead_text) for kw in strong_keywords
            )

            brand_matches = sum(
                1
                for kw in brand_keywords
                if re.search(rf"\b{re.escape(kw)}\b", lead_text)
            )

            if title_match or strong_match or brand_matches >= 2:
                # Save to file (no 'if' check needed thanks to NullFile)
                f.write(json.dumps(article) + "\n")

                # Prepare document for bulk indexing
                batch.append(
                    {
                        "_index": index,
                        "_id": article["id"],
                        "_source": {
                            "title": title_lower,
                            "url": article["url"],
                            "text": text_lower,
                        },
                    }
                )

                count += 1

                if len(batch) >= batch_size:
                    bulk(self.opensearch_client, batch)
                    batch = []
                    f.flush()

        # Final batch upload
        if batch:
            bulk(self.opensearch_client, batch)

        f.close()


MODEL_PRICING = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemma-4-31b-it": {"input": 0.0, "output": 0.0},  # Gemma has no paid tier
}


def ingest_usage(
    usage_metadata: GenerateContentResponseUsageMetadata | None,
    conn: pg.Connection | None,
    model: str,
) -> None:
    if usage_metadata is None:
        return

    if conn is None:
        conn = pg.connect(
            dbname="usage",
            user="user",
            password="postgres",
            host="localhost",
            port="5432",
        )

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage (
            id SERIAL PRIMARY KEY,
            source TEXT,
            model TEXT,
            prompt_token_count INTEGER,
            candidates_token_count INTEGER,
            total_token_count INTEGER,
            cached_content_token_count INTEGER,
            thoughts_token_count INTEGER,
            cost_usd NUMERIC(12, 8),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """.strip())

    cost = estimate_cost(model, usage_metadata)

    cursor.execute(
        """
        INSERT INTO usage (
        source, 
        model, 
        prompt_token_count, 
        candidates_token_count,
        total_token_count, 
        cached_content_token_count, 
        thoughts_token_count,
        cost_usd
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """.strip(),
        ("rag", model, *extract_usage_row(usage_metadata), cost),
    )


def estimate_cost(model: str, usage_metadata) -> float:
    """Estimate USD cost for a single response. Returns 0.0 for unknown models."""
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return 0.0

    input_tokens = usage_metadata.prompt_token_count or 0
    output_tokens = usage_metadata.candidates_token_count or 0

    cost = (input_tokens / 1_000_000) * pricing["input"] + (
        output_tokens / 1_000_000
    ) * pricing["output"]
    return cost


def extract_usage_row(
    usage_metadata: GenerateContentResponseUsageMetadata | None,
) -> tuple:
    if usage_metadata is None:
        return (0, 0, 0, 0, 0)
    return (
        usage_metadata.prompt_token_count or 0,
        usage_metadata.candidates_token_count or 0,
        usage_metadata.total_token_count or 0,
        usage_metadata.cached_content_token_count or 0,
        usage_metadata.thoughts_token_count or 0,
    )


if __name__ == "__main__":
    # print(get_models(opensearch_client))

    # from opensearch_utils import search

    # num: int = 10
    # results = search(
    #     opensearch_client,
    #     index="wikipedia",
    #     query="What is the name of the game where you start as a prisioner in an undead asylum"
    #     "and collect souls as currency and xp?",
    #     num=num,
    #     search_type="semantic",
    #     search_fields=["title", "text"],
    # )

    # for i in range(num):
    #     print(results["hits"]["hits"][i]["_source"]["title"])
    from opensearch_utils import setup_embedder

    # model_id = setup_embedder(opensearch_client)

    # igdb = IGDB(opensearch_client)
    # igdb.pull_all(index="igdb", model_id=model_id)
    wikipedia = Wikipedia(opensearch_client)
    # wikipedia.download_wikipedia(index="wikipedia", model_id=model_id, file_path="data/wikipedia.jsonl")

    # wikipedia.download_wikipedia(file_path="data/wikipedia.jsonl")

    from evaluation import Evaluator
    from llm import RAGClient

    model = "gemini-3.1-flash-lite"
    model = "gemini-3.5-flash-lite"
    model = "gemma-4-31b-it"

    rag_client = RAGClient(opensearch_client, model)
    evaluator = Evaluator(rag_client, None)

    # response = opensearch_client.search(
    #     index="wikipedia",
    #     body={
    #         "size": 10000,
    #         "query": {"match_all": {}},
    #     },
    # )

    # ids = [r["_id"] for r in response["hits"]["hits"]]

    # print("74599251" in ids)

    # evaluator.generate_ground_truth(
    #     index="wikipedia", count=3, n=20, file_path="data/wikipedia_ground_truth.csv"
    # )
    # wikipedia_ground_truth = evaluator.generate_ground_truth(
    #     "wikipedia", 3, 300, "data/wikipedia_ground_truth.csv"
    # )

    # igdb_ground_truth = evaluator.generate_ground_truth(
    #     "igdb", 3, 300, "data/igdb_ground_truth.csv"
    # )

    # result = rag_client.search(index="wikipedia", query="", doc_id="785")

    # print(result)

    # evaluator.ground_truth = pd.read_csv("data/wikipedia_ground_truth.csv")

    # hr_score, mrr_score, x = evaluator.evaluate_search(index="wikipedia",search_type="hybrid")
    # print(hr_score, mrr_score, x, sep="\n\n")

    judge = RAGClient(opensearch_client, model=model)

    # evaluator.ground_truth = pd.read_csv("data/igdb_ground_truth.csv")
    # evaluator.evaluate_agent(judge, overwrite=False, max_workers=1, index="igdb")

    evaluator.ground_truth = pd.read_csv("data/wikipedia_ground_truth.csv")
    evaluator.evaluate_agent(judge, overwrite=False, max_workers=1, index="wikipedia")

    # print(result)
    # Boosting optimization

    # print(hr_score, mrr_score, x)
