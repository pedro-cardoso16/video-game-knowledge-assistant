#!/bin/bash

FILE_NAME=".env"

FILE_TEMPLATE="# --- Gemini ---
GEMINI_API_KEY=<your_api_key>

# --- IGDB ---
# Only fill these ones if you intend to ingest IGDB data yourslef.
IGDB_CLIENT_ID=<optional_api_key> 
IGDB_CLIENT_SECRET=<optional_client_secret>

# Do not change the fields below

# --- Postgres ---
POSTGRES_PASSWORD=postgres
POSTGRES_USER=user

# --- Opensearch ---
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD='Opensearch16admin#'"

if [ -f "${FILE_NAME}" ]; then
    read -p "File $FILE_NAME already exists. Overwrite? (y/N): " response

    if [[ "$response" != "y" && "$response" != "Y" ]]; then
        echo "Skipping file creation."
        exit 0
    fi     
fi

# Create .env file
echo "$FILE_TEMPLATE" > .env
source .env

# Necessary for opensearch hybrid search (must have extra memory).
sudo sysctl -w vm.max_map_count=262144

