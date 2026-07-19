"""ingest.py

This script does the scrap of the IGDB. In other to do this you must have a developer
account.

Only use this script if you intend to update the database with recent information.

Four requests per second
"""

import datasets
from opensearchpy import OpenSearch, exceptions
from collections.abc import Iterable

from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from query import ops_client
from datetime import datetime
import requests
import json
import os
import time
from dotenv import load_dotenv
from opensearch_utils import create_index_with_semantic_search, get_models

ops_client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=("admin", "Opensearch16admin#"),
    use_ssl=False,
    verify_certs=False,  # Set to True if using valid certificates
    ssl_show_warn=False,
)


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

    def pull_all(
        self,
        max_workers: int = 16,
        index: str | None = None,
        model_id: str | None = None,
    ) -> None:
        """Pull everything from IGDB and ingest.

        Args:
            max_workers (int): maximum number of threads to use in the indexing
                process, **not** the request processes
        """

        GET_MAX_ID_BODY = "fields id; sort id desc; limit 1;"

        GET_ALL_FIELDS_IN_ID_RANGE_BODY = (
            "fields *; where id >= {min_id} & id < {max_id}; sort id asc; limit 500;"
        )

        # Get current max id in IGDB.
        max_id = self.fetch(GET_MAX_ID_BODY).json()[0]["id"]

        index = "igdb_" + datetime.now().isoformat(sep="-", timespec="seconds").replace(
            ":", ""
        )

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

    def ingest(self, content: dict, index_name):
        doc_id = content["id"]
        content.pop("id")
        ops_client.index(index=index_name, body=content, id=doc_id)
        ops_client.indices.refresh(index=index_name)


body = "fields *; where id >= 1 & id <= 500; sort id asc; limit 500;"


# --- Vector/semantic search embedding ---
def setup_vector_search(index_name, model_id):
    """Create hybrid search index with minimal code"""

    # Create embedding pipeline
    ops_client.ingest.put_pipeline(
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

    if ops_client.indices.exists(index=new_index_name):
        ops_client.indices.delete(index=new_index_name)

    ops_client.indices.create(
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
    ops_client.reindex(
        body={
            "source": {"index": index_name},
            "dest": {"index": new_index_name},
        },
        params={"wait_for_completion": "false", "slices": "auto"},
    )

    return new_index_name


def download_wikipedia(
    file_path: str = "data/wikipedia_video_games_embeddings.jsonl",
) -> None:
    """Ingest wikipedia video games articles

    Performs the ingestion of the wikipedia jointly with the embedding. It uses
    very simple and naive approach to find relevant articles bey word matching.

    Args:
        file_path (str): file path of the ingested *db* in `jsonl` format.
    """
    dataset = datasets.load_dataset("wikimedia/wikipedia", "20231101.en", split="train")
    game_keywords = {"video game", "video games", "game", "games"}

    with open(file_path, "w", encoding="utf-8") as f:

        count = 0

        for article in tqdm(dataset):
            article = dict(article)

            text_lower = article["text"].lower()
            title_lower = article["title"].lower()

            # Check if the title or the first 300 characters contain game keywords
            if any(kw in title_lower or kw in text_lower[:300] for kw in game_keywords):
                # Save the matched article
                f.write(json.dumps(article) + "\n")
                count += 1

                if count % 100 == 0:
                    # print(f"Found {count} game-related articles...          \r")
                    # Write to disk
                    f.flush()
                    os.fsync(f.fileno())


if __name__ == "__main__":
    pass
    # index_name = "igdb_2026-07-14-162716"

    # model_id = setup_embedder()

    # response = ops_client.transport.perform_request(
    #     "GET",
    #     f"/_plugins/_ml/models/_search",
    #     body={
    #         "query": {
    #             "match_all": {},
    #         },
    #     },
    # )

    # create_index_with_semantic_search(
    #     ops_client, "wikipedia", model_id, {"text", "title"}
    # )

    # ops_client.index(
    #     index="wikipedia",
    #     body={
    #         "text": "A very jhon dark souls game",
    #         "title": "Dark souls",
    #         "url": "https://wikipedia.dark_souls",
    #     },
    #     id="1",
    # )

    # response = ops_client.search(
    #     index="wikipedia",
    #     body={
    #         "query": {
    #             "neural": {
    #                 "text_vector": {
    #                     "query_text": "souls",
    #                     "model_id": model_id,
    #                     "k": 5,
    #                 }
    #             },
    #         },
    #     },
    # )

    # for i in response["hits"]["hits"]:
    #     title = i["_source"]["url"]
    #     print(title)
