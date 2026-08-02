#!/bin/bash

# Move to the app directory to ensure relative paths like 'data/...' work
cd /app

echo "Waiting for OpenSearch to be ready..."
# Poll OpenSearch until it responds to a basic request with auth
OPENSEARCH_HOST=${OPENSEARCH_HOST:-opensearch}
OPENSEARCH_PORT=${OPENSEARCH_PORT:-9200}
OPENSEARCH_USER=${OPENSEARCH_USER:-admin}
OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD:-Opensearch16admin#}

until curl -s -u "$OPENSEARCH_USER:$OPENSEARCH_PASSWORD" "http://$OPENSEARCH_HOST:$OPENSEARCH_PORT/" > /dev/null; do
  echo "OpenSearch is unavailable - waiting initialization"
  sleep 15
done

echo "OpenSearch is up! Importing data..."

python extract.py || { echo "extract.py failed — aborting startup"; exit 1; }

echo "Starting application..."
streamlit run app.py --server.port=8501 --server.address=0.0.0.0