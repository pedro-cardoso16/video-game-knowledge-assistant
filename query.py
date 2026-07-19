import psycopg
import requests
import json
import os
from datasets import load_dataset
from opensearchpy import OpenSearch, helpers

ops_client = OpenSearch(
    hosts=[{"host": "localhost", "port": 9200}],
    http_auth=("admin", "Opensearch16admin#"),
    use_ssl=False,
    verify_certs=False,  # Set to True if using valid certificates
    ssl_show_warn=False,
)

session = requests.Session()


class OpenSearchHelper:
    def __init__(self) -> None:
        pass


class WikipediaSearch:
    def __init__(self) -> None:
        self.url: str = "https://en.wikipedia.org/w/api.php"

    def search(self, query, params: dict | None = None):
        default_params = {
            "action": "opensearch",
            "namespace": 0,
            "search": query,
            "limit": str(5),
            "format": "json",
        }

        params = (default_params | params) if (params is not None) else default_params

        response = session.get(self.url, params=params)

        return response


def ingest_wikipedia():
    pass


if __name__ == "__main__":

    # print(ops_client.cat.indices())

    wiki_search = WikipediaSearch()

    result = wiki_search.search("Hampi")

    print(result.text)

    # --- Wikipedia dataset download ---

    base_url = "https://storage.googleapis.com/huggingface-nlp/cache/datasets/wikipedia/20200501.en/1.0.0/"
    data_files = {"train": base_url + "wikipedia-train.parquet"}
    # dataset = load_dataset("parquet", data_files=data_files, split="train[:100]")

    dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split="train")
    game_keywords = {"video game", "video games", "game", "games"}

    with open("data/wikipedia_video_games_embeddings.jsonl", "w", encoding="utf-8") as f:

        count = 0

        for article in dataset:
            article = dict(article)

            text_lower = article["text"].lower()
            title_lower = article["title"].lower()

            # Check if the title or the first 300 characters contain game keywords
            if any(kw in title_lower or kw in text_lower[:300] for kw in game_keywords):
                # Save the matched article
                f.write(json.dumps(article) + "\n")
                count += 1

                if count % 100 == 0:
                    print(f"Found {count} game-related articles...\r")
                    f.flush()
                    os.fsync(f.fileno())

    # doc_id = 1
    # index_name = "igdb_2026-07-14-162716"
    # # print(
    # #     ops_client.indices.get_mapping(index=index_name)
    # # )
    # response = ops_client.search(index=index_name, body={"size": 1})

    # for hit in response["hits"]["hits"]:
    #     for val in hit["_source"].values():
    #         print(val)
    #         print()
    # index_name = "games"
    # if ops_client.indices.exists(index=index_name):
    #     ops_client.indices.delete(index=index_name)

    # document_data = {"id": 1, "name": "Thief II: The Metal Age"}

    # if not ops_client.indices.exists(index=index_name):
    #     id_val = document_data["id"]
    #     document_data.pop("id")
    #     ops_client.index(index=index_name, body=document_data, id=id_val)

    # ops_client.indices.refresh(index=index_name)
    # response = ops_client.search(
    #     index=index_name,
    #     body={
    #         "query": {
    #             "match_all": {},
    #         },
    #     },
    # )

    # print(response)

# conn = psycopg.connect(
#     host="localhost", port="5432", dbname="games", user="user", password="postgres"
# )

# cur = conn.cursor()

# cur.execute(r"CREATE TABLE test (id serial PRIMARY KEY, num integer, date date)")
# cur.execute("INSERT INTO test (num, date) VALUES (%s, %s)", (100, "2026-08-12"))
# cur.execute("DROP TABLE test")
# cur.execute(
#     "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s;",
#     ("games",),
# )
# print(cur.fetchone())
# conn.close()
