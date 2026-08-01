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
import streamlit as st
import json
from opensearchpy import OpenSearch, helpers
import subprocess
import os

from google.genai.types import GenerateContentResponseUsageMetadata

from opensearchpy.helpers import bulk
from opensearch_utils import create_index_with_semantic_search, get_models

from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
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
            "Authorization": f"Bearer {info['access_token']}",
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
        """Ingests Wikipedia video game articles into OpenSearch."""
        dataset = datasets.load_dataset(
            "wikimedia/wikipedia", "20231101.en", split="train"
        )
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

            title_match = any(
                re.search(rf"\b{re.escape(kw)}\b", title_lower)
                for kw in strong_keywords | brand_keywords
            )

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
                f.write(json.dumps(article) + "\n")

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

        if batch:
            bulk(self.opensearch_client, batch)

        f.close()


MODEL_PRICING = {
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-flash-lite-latest": {
        "input": 0.30,
        "output": 2.50,
    },  # Points to 3.5 Flash-Lite
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3.6-flash": {"input": 1.50, "output": 7.50},
    "gemini-flash-latest": {"input": 1.50, "output": 7.50},  # Points to 3.6 Flash
    "gemma-4-26b-a4b-it": {
        "input": 0.00,
        "output": 0.00,
    },  # Gemma models are open weights
    "gemma-4-31b-it": {"input": 0.00, "output": 0.00},
}


def save_usage_metadata(
    usage_metadata: GenerateContentResponseUsageMetadata | None,
    conn: pg.Connection | None,
    model: str,
    custom_pricing: dict | None = None,
) -> None:
    """### Ingest usage

    Args:
        usage_metadata (GenerateContentResponseUsageMetadata | None): metadata
            of the usage from the last query
        conn (Connection | None): connection to postgres server
        model (str): model's name
        custom_pricing (dict | None): optional dictionary with 'input' and 'output' rates
    """
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

    with conn:
        with conn.cursor() as cursor:

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

            cost = estimate_cost(model, usage_metadata, custom_pricing)

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


def estimate_cost(
    model: str,
    usage_metadata,
    custom_pricing: dict | None = None, 
) -> float:
    """Estimate USD cost for a single response. Uses custom_pricing if provided."""
    pricing = custom_pricing or MODEL_PRICING.get(model)
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


def save_user_feedback(
    conn: pg.Connection, question: str, answer: str, score: str
) -> None:
    """Save a user's thumbs up/down review for an assistant answer."""
    with conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id SERIAL PRIMARY KEY,
                    source TEXT,
                    question TEXT,
                    answer TEXT,
                    reasoning TEXT,
                    answer_score TEXT,
                    tool_score TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                """
                INSERT INTO evaluations (source, question, answer, answer_score)
                VALUES (%s, %s, %s, %s)
                """,
                ("user", question, answer, score),
            )


class OpenSearchBundler:
    def __init__(self, client: OpenSearch):
        self.client = client

    def export_index(self, index: str, data_file: str, config_file: str):
        """Exports index settings, mappings, and all documents."""
        print(f"📦 Exporting index: {index}...")

        settings = self.client.indices.get_settings(index=index)
        mappings = self.client.indices.get_mapping(index=index)

        config = {"settings": settings[index], "mappings": mappings[index]}

        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        print(f"✅ Metadata saved to {config_file}")

        query = {"query": {"match_all": {}}}
        page = self.client.search(index=index, body=query, scroll="2m", size=1000)  # type: ignore

        scroll_id = page["_scroll_id"]
        hits = page["hits"]["hits"]
        count = 0

        with open(data_file, "w", encoding="utf-8") as f:
            while len(hits) > 0:
                for hit in hits:
                    doc = hit["_source"]
                    doc["_id"] = hit["_id"]
                    f.write(json.dumps(doc) + "\n")
                    count += 1

                page = self.client.scroll(scroll_id=scroll_id, scroll="2m")  # type: ignore
                scroll_id = page["_scroll_id"]
                hits = page["hits"]["hits"]

        print(f"✅ {count} documents saved to {data_file}")

    def _deep_clean(self, data):
        """Recursively removes forbidden keys from nested dictionaries."""
        forbidden = [
            "uuid",
            "creation_date",
            "version",
            "provided_name",
            "default_pipeline",
        ]
        if isinstance(data, dict):
            return {
                k: self._deep_clean(v)
                for k, v in data.items()
                if not any(word in k.lower() for word in forbidden)
            }
        elif isinstance(data, list):
            return [self._deep_clean(i) for i in data]
        return data

    def import_index(
        self,
        data_file: str,
        config_file: str,
        new_index_name: str,
        force_reimport: bool = False,
    ):
        print(f"🚀 Checking index status for: {new_index_name}...")

        # 1. Register search pipeline for RRF hybrid search
        search_pipeline_body = {
            "description": "Modern RRF rank-blending search pipeline",
            "phase_results_processors": [
                {
                    "score-ranker-processor": {
                        "combination": {
                            "technique": "rrf",
                            "parameters": {"rank_constant": 60},
                        }
                    }
                }
            ],
        }
        try:
            self.client.search_pipeline.put(
                id="search_pipeline", body=search_pipeline_body
            )
        except Exception:
            pass

        # 2. Register ingest pipeline if ML model is active
        try:
            models = get_models(self.client)
            if models:
                model_id = models[0]
                ingest_pipeline_body = {
                    "description": "Ingest embedder",
                    "processors": [
                        {
                            "text_embedding": {
                                "model_id": model_id,
                                "field_map": {
                                    "name": "name_vector",
                                    "summary": "summary_vector",
                                    "storyline": "storyline_vector",
                                    "title": "title_vector",
                                    "text": "text_vector",
                                },
                            }
                        }
                    ],
                }
                self.client.ingest.put_pipeline(
                    id=f"{new_index_name}_ingest_pipeline", body=ingest_pipeline_body
                )
        except Exception as e:
            print(f"Notice setting ingest pipeline: {e}")

        # 3. PERSISTENCE CHECK: If index already exists and has documents, SKIP import!
        if self.client.indices.exists(index=new_index_name) and not force_reimport:
            try:
                doc_count = self.client.count(index=new_index_name).get("count", 0)
                if doc_count > 0:
                    print(
                        f"✅ Index '{new_index_name}' already exists with {doc_count} documents. Skipping import."
                    )
                    return
            except Exception:
                pass

        # 4. Load Configuration
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        raw_settings = config["settings"].get("settings", {})
        sanitized_settings = self._deep_clean(raw_settings)

        mappings_data = config["mappings"]
        if "mappings" in mappings_data:
            mappings_data = mappings_data["mappings"]

        # 5. Delete existing empty index if needed
        if self.client.indices.exists(index=new_index_name):
            print(f"🗑️ Re-creating index '{new_index_name}' for clean import...")
            self.client.indices.delete(index=new_index_name)

        # 6. Create Index
        try:
            self.client.indices.create(
                index=new_index_name,
                body={"settings": sanitized_settings, "mappings": mappings_data},
            )
            print(f"✅ Index '{new_index_name}' created successfully.")
        except Exception as e:
            print(f"❌ Failed to create index '{new_index_name}': {e}")
            return

        # 7. Bulk Import Documents from JSONL
        def jsonl_generator():
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f:
                    doc = json.loads(line)
                    doc_id = doc.pop("_id", None)
                    yield {"_index": new_index_name, "_id": doc_id, "_source": doc}

        print(f"📦 Bulk loading documents into '{new_index_name}'...")
        success, failed = helpers.bulk(self.client, jsonl_generator())
        print(
            f"✅ Successfully imported {success} documents into '{new_index_name}'. Failures: {failed}"
        )


class PostgresBundler:
    def __init__(self, container_name="postgres", user="user", password="postgres"):
        self.container_name = container_name
        self.user = user
        self.password = password

    def export_database(self, db_name: str, output_file: str):
        """Exports a database using pg_dump via docker exec."""
        print(f"📦 Exporting database {db_name}...")

        cmd = f"docker exec -u postgres -e PGPASSWORD={self.password} {self.container_name} pg_dump -h localhost -U {self.user} {db_name}"

        try:
            with open(output_file, "w") as f:
                subprocess.run(cmd, shell=True, stdout=f, check=True)
            print(f"✅ Database {db_name} saved to {output_file}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Export failed: {e}")

    def import_database(self, sql_file: str, db_name: str):
        """Imports a .sql file into a database via docker exec."""
        print(f"🚀 Importing {sql_file} into database {db_name}...")

        create_db_cmd = f'docker exec -e PGPASSWORD={self.password} {self.container_name} psql -U {self.user} -d postgres -c "CREATE DATABASE {db_name};"'

        try:
            subprocess.run(create_db_cmd, shell=True, capture_output=True)
        except Exception:
            pass

        try:
            with open(sql_file, "r") as f:
                cmd = f"docker exec -i -e PGPASSWORD={self.password} {self.container_name} psql -U {self.user} -d {db_name}"
                subprocess.run(cmd, shell=True, stdin=f, check=True)
            print(f"✅ Database {db_name} restored successfully.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Import failed: {e}")


if __name__ == "__main__":
    from opensearch_utils import setup_embedder

    wikipedia = Wikipedia(opensearch_client)

    from evaluation import Evaluator
    from llm import RAGClient

    model = "gemini-3.5-flash-lite"
    model = "gemini-3.1-flash-lite"
    model = "gemma-4-31b-it"

    rag_client = RAGClient(opensearch_client, model)
    evaluator = Evaluator(rag_client, None)

    opensearch_bundler = OpenSearchBundler(opensearch_client)

    postgres_blunder = PostgresBundler()
    postgres_blunder.export_database("usage", "data/usage.sql")
