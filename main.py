import requests
import json
import pandas as pd
import sys
from ingest import IGDB
import metrics

from google.genai import Client, types
from dotenv import load_dotenv
from opensearchpy import OpenSearch
from query import opensearch_client
from llm import RAGClient
from metrics import evaluate_search
from opensearch_utils import get_models, setup_embedder, search


def load_database():
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    response = requests.get(url)

    print(response)


if __name__ == "__main__":

    opensearch_client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_auth=("admin", "Opensearch16admin#"),
        use_ssl=False,
        verify_certs=False,  # Set to True if using valid certificates
        ssl_show_warn=False,
    )

    # igdb = IGDB(opensearch_client)
    # igdb.pull_all(index="igdb")

    ai = RAGClient(opensearch_client, model="gemini-3.1-flash-lite")

    response = ai.rag(
        query="What are the reviews of Dark Souls"
    )

    print(response)
    # model_id = setup_embedder(opensearch_client)
    # # print(get_models(opensearch_client))

    # igdb = IGDB(opensearch_client)

    # igdb.pull_all(model_id=model_id)

    # print(igdb.opensearch_client.cat.indices())
    # model_id = get_models(opensearch_client)[0]
    # print(model_id)
    # # response = opensearch_client.search(
    # #     index="igdb_2026-07-17-221359",
    # #     body={
    # #         "query": {
    # #             "neural": {
    # #                 "name_vector": {
    # #                     "query_text": "Dark souls II",
    # #                     "model_id": "OyPJcp8BilAjMLOPR-dH",
    # #                 },
    # #             },
    # #         },
    # #     },
    # # )

    # response = search(
    #     opensearch_client,
    #     "igdb_2026-07-17-221359",
    #     "Dark souls II",
    #     5,
    #     model_id=model_id,
    #     search_type="semantic",
    #     search_fields=[
    #         "name",
    #         "storyline",
    #     ],
    # )

    # print(response["hits"]["hits"][0]["_source"]["name"])
    # # response = ai.llm("What are the sources that you use in your search?")

    # index_name = "igdb_2026-07-14-162716"
