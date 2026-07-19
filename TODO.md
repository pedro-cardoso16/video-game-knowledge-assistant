## Data ingestion
* [x] Collect the information from IGDB
* [ ] Collect the information from Wikipedia
* [x] Save information in opensearch index  
    * [ ] Write info to disk
    * [x] Download the `ONNX` model from huggingface and integrate with opensearch
* [ ] Save information in postgres SQL
    * [ ] Write info to disk

## Search evaluation
* [x] Create the ground truth
* [ ] Evaluate 
    * [x] lexical search
    * [x] vector search
    * [ ] hybrid search 
* [ ] Search optimization - find the best parameters for boosting.


## Application
* [ ] Use streamlit to bridge interaction with the user

## Monitoring
* [ ] Grafana monitoring
* [ ] Streamlit monitoring
* [ ] 

## Docker container - all up and running
* [ ] Prepare dockerfile
* [ ] Prepare compose.yaml


---
* [ ] Clean up the [`ingest.py`](ingest.py) and [`query.py`](query.py), they really need to have their tasks 
separated.