import os

from opensearch_utils import setup_embedder
from opensearchpy import OpenSearch
from dotenv import load_dotenv
from ingest import PostgresBundler, OpenSearchBundler

load_dotenv()

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "localhost")
OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "Opensearch16admin#")

# Read the FORCE_REIMPORT environment variable (defaults to False if not set)
FORCE_REIMPORT = os.getenv("FORCE_REIMPORT", "false").lower() in ("true", "1", "yes")


opensearch_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

if __name__ == "__main__":
    setup_embedder(opensearch_client)

    opensearch_bundler = OpenSearchBundler(opensearch_client)
    postgres_blunder = PostgresBundler()

    print(f"Force re-import mode: {FORCE_REIMPORT}")

    opensearch_bundler.import_index(
        "data/igdb_index.jsonl",
        "data/igdb_config.json",
        "igdb",
        force_reimport=FORCE_REIMPORT,
    )
    opensearch_bundler.import_index(
        "data/wikipedia_index.jsonl",
        "data/wikipedia_config.json",
        "wikipedia",
        force_reimport=FORCE_REIMPORT,
    )

    # postgres_blunder.import_database("data/usage.sql", "usage")
    # postgres_blunder.import_database("data/evaluations.sql", "evaluations")
