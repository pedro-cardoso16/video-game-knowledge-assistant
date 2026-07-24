"""OpenSearch Developer Ergonomics and Sanity Preservation Layer.

This module acts as a critical defensive facade over the official `opensearch-py`
client, bridging the substantial gap between idiomatic Python software design
and the uniquely creative architectural paradigms native to OpenSearch.

By design, the upstream SDK requires developers to manually orchestrate verbose
payloads, manage mutually blind background task engines, and write primitive
interval-polling state machines just to execute basic cluster lifecycles.

This utility explicitly encapsulates those fragmentation vectors, shielding main
application code from low-level infrastructure boilerplate. It converts highly
imperative, anti-pythonic workflows into linear, predictable, and ergonomically
pleasant execution boundaries.
"""

import time
import json

from tqdm import tqdm

# from collections.abc import Iterable
from opensearchpy import OpenSearch, exceptions
from typing import Iterable, Literal


def create_index_with_semantic_search(
    opensearch_client: OpenSearch,
    index_name: str,
    model_id: str,
    semantic_fields: Iterable[str],
    search_pipeline_id: str = "search_pipeline",
) -> None:
    """Setup index cleanly using native semantic fields.

    Creates a new index with built-in semantic search capabilities.
    No ingest pipeline is required as OpenSearch processes data natively.

    Args:
        opensearch_client: Active OpenSearch client instance.
        index_name: Name of the index to create.
        model_id: ML Model ID registered in the cluster.
        search_pipeline_id: Pipeline used for score normalization/hybrid merging.
        *semantic_fields: values representing the semantic text fields.

    Example:
        create_index_with_semantic_search(
            client, "my-index", "model-abc", "summary_vector"
        )
    """

    if not semantic_fields:
        raise ValueError("You must provide at least one text field name to map.")

    semantic_fields = tuple(semantic_fields)

    ingest_pipeline_id = f"{index_name}_ingest_pipeline"

    field_map = {field: f"{field}_vector" for field in semantic_fields}

    ingest_pipeline_body = {
        "description": "Ingest embedder",
        "processors": [
            {
                "text_embedding": {
                    "model_id": model_id,
                    "field_map": field_map,
                }
            }
        ],
    }

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

    opensearch_client.ingest.put_pipeline(
        id=ingest_pipeline_id, body=ingest_pipeline_body
    )

    opensearch_client.search_pipeline.put(
        id=search_pipeline_id, body=search_pipeline_body
    )

    vector_field_config = {  # Target vector storage
        "type": "knn_vector",
        "dimension": 384,  # Adjust based on your model's dimensions
        "method": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "lucene",
        },
    }

    index_settings_properties = {}

    for key in semantic_fields:
        index_settings_properties[key] = {"type": "text"}
        index_settings_properties[f"{key}_vector"] = vector_field_config

    creation_payload = {
        "settings": {
            "index.knn": True,  # Required for vector fields
            "index.default_pipeline": ingest_pipeline_id,
            "index.search.default_pipeline": search_pipeline_id,
        },
        "mappings": {
            "properties": index_settings_properties,
            "dynamic": "true",
        },
    }

    try:
        opensearch_client.indices.create(index=index_name, body=creation_payload)
    except exceptions.RequestError as e:
        if "resource_already_exists_exception" in str(e):
            print(f"Notice: Index '{index_name}' already exists. Skipping creation.")
        else:
            raise e


def setup_embedder(
    opensearch_client: OpenSearch,
    model: str = "huggingface/sentence-transformers/all-MiniLM-L12-v2",
) -> str:
    """
    Warning:
        > **FUNCTION DOESN'T CHECK FOR CREATED MODELS**
        >
        > This functions doesn't check for the existance of a previous set model.
        > Calling it multiple times without check will cause errors.

    Args:
        model (str): The address of the model to use. Defaults to `"huggingface/sentence-transformers/all-MiniLM-L12-v2"`

    Returns:
        model_id (str): The id of the created model.
    """
    # Check whether or not a model group already exists
    response = opensearch_client.transport.perform_request(
        "GET",
        "/_plugins/_ml/model_groups/_search",
        body={
            "query": {
                "match": {"name": "default_model_group"},
            },
        },
    )

    # If the model group exists, skips the group creation
    try:
        model_group_id: str = response["hits"]["hits"][0]["_id"]
    except:
        print("Model group doesn't exist, creating one...")
        # Creates a ml group that may be used for sentence embedding
        response = opensearch_client.transport.perform_request(
            "POST",
            "/_plugins/_ml/model_groups/_register",
            body={
                "name": "default_model_group",
                "description": "Default model group for local models",
            },
        )
        model_group_id: str = response["model_group_id"]

    # =====================================================================
    # 1. REGISTER THE MODEL (Downloads and records metadata)
    # =====================================================================
    print(f"\n[1/2] Dispatched registration for model: {model}")
    response = opensearch_client.transport.perform_request(
        "POST",
        "/_plugins/_ml/models/_register",
        body={
            "name": model,
            "version": "1.0.2",
            "model_group_id": model_group_id,
            "model_format": "ONNX",
        },
    )

    # Save the task id for progress check
    reg_task_id = response["task_id"]

    t0 = time.time()
    while True:
        response = opensearch_client.transport.perform_request(
            "GET", f"/_plugins/_ml/tasks/{reg_task_id}"
        )
        status = response.get("state")

        if status == "COMPLETED":
            model_id = response["model_id"]
            print(
                f"\nRegistration COMPLETED in {time.time() - t0:.1f}s. Model ID: {model_id}"
            )
            break

        if status in ["FAILED", "CANCELLED"]:
            error_details = response.get("error", "Unknown registration failure")
            raise RuntimeError(
                f"\nModel Registration Failed ({status}): {error_details}"
            )

        print(
            f"Registering model... Status: {status} | Time elapsed: {time.time() - t0:.1f}s",
            end="\r",
        )
        time.sleep(3)

    # =====================================================================
    # 2. DEPLOY THE MODEL (Loads the model binaries into cluster memory)
    # =====================================================================
    print(f"\n[2/2] Dispatched deployment request for model ID: {model_id}")
    deploy_response = opensearch_client.transport.perform_request(
        "POST", f"/_plugins/_ml/models/{model_id}/_deploy"
    )
    deploy_task_id = deploy_response["task_id"]

    t1 = time.time()
    while True:
        response = opensearch_client.transport.perform_request(
            "GET", f"/_plugins/_ml/tasks/{deploy_task_id}"
        )
        status = response.get("state")

        if status == "COMPLETED":
            print(
                f"\nDeployment COMPLETED in {time.time() - t1:.1f}s. Model is warm and active!"
            )
            break

        if status in ["FAILED", "CANCELLED"]:
            error_details = response.get("error", "Unknown deployment failure")
            raise RuntimeError(f"\nModel Deployment Failed ({status}): {error_details}")

        print(
            f"Deploying model to node RAM... Status: {status} | Time elapsed: {time.time() - t1:.1f}s",
            end="\r",
        )
        time.sleep(3)

    return model_id


def get_models(opensearch_client: OpenSearch) -> list[str]:

    response = opensearch_client.transport.perform_request(
        "GET",
        "/_plugins/_ml/models/_search",
        body={
            "query": {
                "match_all": {},
            },
        },
    )["hits"]["hits"]

    try:
        response = {r["_source"]["model_id"] for r in response}
    except:
        response = set()

    return list(response)


def ingest_from_jsonl(
    opensearch_client: OpenSearch,
    file_path: str,
    index_name: str,
    ratio: int = 1,
):
    # data conversion
    with open(file_path, "r") as f:
        total_lines = sum(1 for _ in f)
        f.seek(0)
        break_limit = int(total_lines * ratio)
        for index, line in enumerate(tqdm(f, total=break_limit)):
            line = line.strip()

            data = json.loads(line)

            body = {
                "title": data["title"],
                "url": data["url"],
                "text": data["text"],
            }

            opensearch_client.index(index=index_name, body=body, id=data["id"])

            if index >= break_limit:
                break


def search(
    opensearch_client: OpenSearch,
    index: str,
    query: str,
    num: int,
    model_id: str | None = None,
    boost_dict: dict = {},
    search_type: Literal["lexical", "semantic", "hybrid"] = "lexical",
    search_fields: Iterable[str] | None = None,
):
    """Search wrapper for OpenSearch supporting lexical, semantic, and hybrid modes."""

    fields = list(search_fields) if search_fields else ["*"]
    query_block = {}


    if model_id is None:
        model_id = get_models(opensearch_client)[0]

    match search_type:
        case "lexical":
            boosted_fields = [f"{f}^{boost_dict.get(f, 1)}" for f in fields]
            query_block = {"multi_match": {"query": query, "fields": boosted_fields}}

        case "semantic":
            # if len(fields) == 1:
            if fields[0] == '*':
                fields = get_vector_fields(opensearch_client, index)
                # Remove the '_vector' suffix if you need the original text field names
                fields = [f.replace("_vector", "") for f in fields]
            
            # query_block = {
            #     "neural": {
            #         f"{field}_vector": (
            #             {
            #                 "query_text": query,
            #                 "model_id": model_id,
            #             }
            #         )
            #     }
            # }
            # else:
            should_queries = [
                {
                    "neural": {
                        f"{key}_vector": (
                            {
                                "query_text": query,
                                "model_id": model_id,
                            }
                        )
                    }
                }
                for key in fields
            ]
            query_block = {"bool": {"should": should_queries}}

        case "hybrid":
            if fields[0] == '*':
                fields = get_vector_fields(opensearch_client, index)
                # Remove the '_vector' suffix if you need the original text field names
                fields = [f.replace("_vector", "") for f in fields]

            # if len(fields) == 1:
            #     field = fields[0]
                 # neural_part = {
                #     "neural": {
                #         f"{field}_vector": (
                #             {
                #                 "query_text": query,
                #                 "model_id": model_id,
                #             }
                #         )
                #     }
                # }
            # else:
            neural_part = {
                "bool": {
                    "should": [
                        {
                            "neural": {
                                f"{key}_vector": (
                                    {
                                        "query_text": query,
                                        "model_id": model_id,
                                    }
                                )
                            }
                        }
                        for key in fields
                    ]
                }
            }

            boosted_fields = [f"{f}^{boost_dict.get(f, 1)}" for f in fields]
            query_block = {
                "hybrid": {
                    "queries": [
                        {"multi_match": {"query": query, "fields": boosted_fields}},
                        neural_part,
                    ],
                },
            }

        case _:
            raise ValueError(
                "Invalid search_type value, must be 'lexical', 'semantic' or 'hybrid'."
            )

    body = {
        "size": num,
        "query": query_block,
    }

    return opensearch_client.search(index=index, body=body)


def get_vector_fields(opensearch_client: OpenSearch, index_name: str) -> list[str]:
    """Retrieves all field names from an index that end with '_vector'."""
    # 1. Fetch the mapping for the index
    response = opensearch_client.indices.get_mapping(index=index_name)
    
    # 2. Navigate the response structure: {index_name}: {mappings: {properties: {...}}}
    properties = response[index_name].get("mappings", {}).get("properties", {})
    
    # 3. Filter for fields ending in '_vector'
    vector_fields = [field for field in properties.keys() if field.endswith("_vector")]
    
    return vector_fields