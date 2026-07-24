#!/bin/bash

FILE_NAME=".env"

FILE_TEMPLATE="GEMINI_API_KEY=<your_api_key>
OPENAI_API_KEY=<your_api_key>

# Only fill this one if you intend to ingest IGDB data yourslef.
IGDB_CLIENT_ID=<optional_api_key> 

POSTGRES_PASSWORD=postgres
POSTGRES_USER=user"

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

sudo chown -R 1000:1000 ./data/opensearch

# curl -v -X POST "https://id.twitch.tv/oauth2/token" \
#   -d "client_id=${IGDB_CLIENT_ID}" \
#   -d "client_secret=${IGDB_CLIENT_SECRET}" \
#   -d "grant_type=client_credentials" > info.json


# mkdir -p models
# cd models
# wget https://artifacts.opensearch.org/models/ml-models/huggingface/sentence-transformers/all-MiniLM-L12-v2/1.0.2/onnx/sentence-transformers_all-MiniLM-L12-v2-1.0.2-onnx.zip
# wget https://artifacts.opensearch.org/models/ml-models/huggingface/sentence-transformers/all-MiniLM-L12-v2/1.0.2/onnx/config.json
# cd ..