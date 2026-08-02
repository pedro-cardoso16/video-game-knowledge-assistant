#!/bin/bash

FILE_NAME=".env"
read -r -d '' FILE_TEMPLATE << 'EOM'
# --- Gemini ---
GEMINI_API_KEY='<your_api_key>'

# --- IGDB ---
# Only fill these ones if you intend to ingest IGDB data yourself.
IGDB_CLIENT_ID='<optional_api_key>'
IGDB_CLIENT_SECRET='<optional_client_secret>'

# Do not change the fields below

# --- Postgres ---
POSTGRES_PASSWORD=postgres
POSTGRES_USER=user

# --- Opensearch ---
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD='Opensearch16admin#'
EOM

if [ -f "${FILE_NAME}" ]; then
    read -p "File $FILE_NAME already exists. Overwrite? (y/N): " response

    if [[ "$response" == "y" || "$response" == "Y" ]]; then
        echo "$FILE_TEMPLATE" > "$FILE_NAME"
        echo "Created $FILE_NAME"
    else
        echo "Skipping file creation."
    fi
else
    echo "$FILE_TEMPLATE" > "$FILE_NAME"
    echo "Created $FILE_NAME"
fi

STREAMLIT_FILE=".streamlit/secrets.toml"

read -r -d '' STREAMLIT_TEMPLATE << 'EOM'
[postgres]
dialect = "postgresql"
host = "postgres"
port = 5432
database = "usage"
user = "user"
password = "postgres"

[postgres_evaluations]
dialect = "postgresql"
host = "postgres"
port = 5432
database = "evaluations"
user = "user"
password = "postgres"
EOM

mkdir -p .streamlit

if [ -f "${STREAMLIT_FILE}" ]; then
    read -p "File $STREAMLIT_FILE already exists. Overwrite? (y/N): " response
    
    if [[ "$response" == "y" || "$response" == "Y" ]]; then
        echo "$STREAMLIT_TEMPLATE" > "$STREAMLIT_FILE"
    else
        echo "Skipping file creation."
    fi
else
    echo "$STREAMLIT_TEMPLATE" > "$STREAMLIT_FILE"
fi


# Load environment variables if .env exists
if [ -f .env ]; then
    source .env
fi

# Necessary for opensearch hybrid search (must have extra memory).
sudo sysctl -w vm.max_map_count=262144

