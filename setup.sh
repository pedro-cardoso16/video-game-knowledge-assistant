#!/bin/bash
# mv .env-template .env

# source .env

# curl -v -X POST "https://id.twitch.tv/oauth2/token" \
#   -d "client_id=${IGDB_CLIENT_ID}" \
#   -d "client_secret=${IGDB_CLIENT_SECRET}" \
#   -d "grant_type=client_credentials" > info.json

mkdir -p models
cd models
wget https://artifacts.opensearch.org/models/ml-models/huggingface/sentence-transformers/all-MiniLM-L12-v2/1.0.2/onnx/sentence-transformers_all-MiniLM-L12-v2-1.0.2-onnx.zip
wget https://artifacts.opensearch.org/models/ml-models/huggingface/sentence-transformers/all-MiniLM-L12-v2/1.0.2/onnx/config.json
cd ..