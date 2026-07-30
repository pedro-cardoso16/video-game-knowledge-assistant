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

opensearch_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
    http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False,
)

if __name__ == "__main__":
    setup_embedder(opensearch_client)