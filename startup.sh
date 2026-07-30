#!/bin/bash

# Move to the app directory to ensure relative paths like 'data/...' work
cd /app

echo "Waiting for OpenSearch to be ready..."
# Poll OpenSearch until it responds to a basic request
until curl -s http://opensearch:9200 > /dev/null; do
  echo "OpenSearch is unavailable - sleeping"
  sleep 2
done

echo "OpenSearch is up! Importing data..."

python extract.py

echo "Starting application..."
streamlit run app.py --server.port=8501 --server.address=0.0.0.0