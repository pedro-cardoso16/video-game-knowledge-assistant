import os
import glob

from tqdm import tqdm
from opensearch_utils import setup_embedder
from opensearchpy import OpenSearch
from dotenv import load_dotenv
from ingest import PostgresBundler, OpenSearchBundler

# Configuration


def assemble_file(file_path: str, force_reassemble: bool = False):
    parts = sorted(glob.glob(f"{file_path}*.part"))

    output_file = f"{file_path}"

    if os.path.exists(file_path) and not force_reassemble:
        print(f"File {file_path} already exists. Skipping assembly.")
        return

    if not parts:
        print("No file fragments found!")
        return

    print(f"Assembling {file_path} from {len(parts)} parts...")

    # 3. Rebuild the file
    try:
        with open(file_path, "wb") as output_file:
            for part in tqdm(parts, desc=f"Assembling {file_path}", unit="part"):
                print(f"Appending {part}...")
                with open(part, "rb") as pf:
                    output_file.write(pf.read())
        print("Assembly complete!")
    except Exception as e:
        print(f"An error occurred during assembly: {e}")
        # Clean up partial file if it failed mid-way
        if os.path.exists(file_path):
            os.remove(file_path)

    print("Assembly complete!")


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

    # Assmebly of the parts files
    assemble_file("data/wikipedia_index.jsonl")
    assemble_file("data/igdb_index.jsonl")

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
