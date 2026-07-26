<!-- [![GitHub Sponsors](https://img.shields.io/badge/Sponsor_me-EA4AAA?style=for-the-badge&logo=github-sponsors&logoColor=white)](https://github.com/sponsors/pedro-cardoso16)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee&logoColor=white)](https://www.buymeacoffee.com/pedro.cardoso) -->

## Acknowledgments
This project was developed as part of the LLM Zoomcamp cohort leaded by instructor [@alexeygrigorev](https://github.com/alexeygrigorev).
Special thanks to the [DataTalksClub/llm-zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp) community for providing the resources and framework for this project.

# Video game knowledge assistant
Get fast reviews of video games using an extensive aggregated source of metadata and reviews from 
IGDB and Wikipedia.


## Getting started

### Docker installation
It's recommended to use github codespaces, in this way you won't need to install anything in your local machine.

If you intend to use in your local machine must have docker engine installed in your system or docker desktop. 
> **Docker engine** installation guide: https://docs.docker.com/engine/install  
> **Docker desktop** installation guide: https://docs.docker.com/get-started/get-docker/

Once this is done we can begin the setup.
### Run app
In the main project folder execute:
```bash
chmod +x setup.sh && ./setup.sh 
```
This will create a `.env` file. 

In this file, replace the `<>` fields with your keys. You can create a free one using your google account and accessing the site https://aistudio.google.com/api-keys. 

```bash
docker compose up --build -d
```
Wait until the completion is done.

If you are in codespaces a dedicated window will be open. If you are on a local machine. Open in a web browser in the following address:
```bash
https://localhost:9200
```

In the web page you should see
<!-- Insert figure here -->



# How it works

## Architecture

```mermaid
graph TD
    User <-->  App(streamlit app)
    LLM(LLM client) <--> Assistant
    User((User)) <--> Assistant(assistant)
    Assistant <--> OpenSearch
    B --> OpenSearch(opensearch) 
    IGDB[("IGDB\n(remote)")] -->|ingest| B[("index DB\n(local)")]
    WIKIPEDIA[("Wikipedia\n(remote)")] -->|ingest| B
```

RAG
Search evaluation (MRR, RRF)
Response with RAG evaluation (LLM as a judge)
Tool usage evaluation (LLM as a judge)

### Evaluation
One very important aspect of monitoring and pre/post - deployment phases are the 
evaluation. We have offline evaluation (before deployment) and online evaluation 
(post-deployment).

#### Search evaluation
In order to perform the search evaluation we will use the module `evaluation.py`. 
In this module there is a method called `gen_ground_truth` which will use the llm
to generate questions based on random documents of this database. Each question
is tied to single document and this specific document is what we will try to retrieve
using the generated questions as a query

```mermaid
---
title: Ground truth generation pipeline
---
flowchart LR
DB[(index DB)] -->|retrieve| LLM
LLM(LLM) -->|generate| Q(questions) 
Q --> GT[(ground truth DB)]
```
```mermaid
---
title: Search evaluation architecture
---
flowchart LR
Q(questions) --> S(search)
DB[(DB)] --> S
S --> R(results)
R --> E(evaluator)
GT(ground truth) --> E
E --> MRR("MRR (mean reciprocal rank)")
E --> HR("HR (hit rate)")
```

#### Agent evaluation
Once our search tools are optimized, we can proceed to the complete RAG evaluation.
In this step, we use a separate LLM as a judge. 

1. Use the generated questions and query them to the llm.
2. Once the final answer is given the LLM judge rates the final answer and the 
    tool usage each as 'bad' (0.0) 'average' (0.5) or 'good' (1.0)
3. The reviews are saved into a sql database.

##### Users feedbacks
The users can only evaluate the final answer and, for simplicity, they just have two 
options 'bad' (0.0) or 'good' (1.0). These info are also saved in our sql database.

```mermaid
---
title: Agent evaluation architecture
---
flowchart LR
E[evaluator]
Q(questions)
RAG(RAG)
A(answer)
TU(tool usage)
U((user))

Q --> RAG
RAG --> A
RAG --> TU
TU --> E
A --> E
A --> U
E --> DB[(evaluation DB)]
U -->|feedback| DB
U -->|question| RAG
```


### Data ingestion from IGDB
We use [IGDB](https://www.igdb.com/) information for ingesting metadata and reviews. The data is available remotely and is ingested into the local store (Postgres or OpenSearch) for retrieval.

### Architecture assessment
- Strengths: clear separation of responsibilities (ingest, retrieval, LLM, UI), use of OpenSearch for RAG enables fast vector/keyword search, and Grafana for observability.
- Risks/Improvements: consider explicit vector store and embedding service, caching of LLM responses, access control for remote IGDB, and automated ETL for data freshness. Also clarify whether Postgres or OpenSearch is the primary source of truth and ensure schema/versioning for ingested data.


## Monitoring
For monitoring we will use streamlit, since the data we want to observe is relatively simple.

```mermaid
---
title: Monitoring architecture
---
flowchart TD
EDB[(evaluation DB)]
UDB[(usage DB)]
S(streamlit)
U((user))

EDB --> S
UDB --> S
S --> U
```

We can observe the model's performance and usage in the tab <!-- Insert tab name here -->. There we will the following things.
* Users feedback with corresponding questions and answers
* LLM-judge evaluations on tool usage and answer quality
* The token usage (input and output) and price (if you are using a paid model).

On the streamlit app access the *usage* tab  
![streamlit_screenshot](media/imgs/streamlit_app.jpg)