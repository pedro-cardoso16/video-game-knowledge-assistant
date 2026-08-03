# 🎮 Video Game Knowledge Assistant (SageBot)

An end-to-end RAG (Retrieval-Augmented Generation) AI assistant and agent that unifies fragmented video game data from **IGDB** (structured metadata, release dates, genres, ratings) and **Wikipedia** (deep lore, game history, narrative details) into a single intelligent interface.

Built as a capstone project for the [DataTalks.Club LLM Zoomcamp](https://github.com/DataTalksClub/llm-zoomcamp) 2026 cohort.

---

## 📌 Problem Statement

Finding comprehensive video game information is often fragmented:
- **Structured metadata** (release dates, platforms, age ratings, genres) lives on specialized databases like IGDB.
- **Deep narrative lore and development history** are scattered across unstructured sources like Wikipedia.

Standard search engines often fail to synthesize both structured filtering and deep narrative context into direct, natural language answers.

The **Video Game Knowledge Assistant** solves this by aggregating structured metadata and unstructured textual lore into a unified knowledge base, leveraging **Hybrid Search (Lexical + Vector with RRF)** and an **LLM Agent** to answer complex gaming queries with accurate context and source transparency.

---

## 🚀 Quick Start & Installation

### Prerequisites & System Requirements
First of all, you must install docker on your system.

> 🐋 **Docker**: [Docker Engine](https://docs.docker.com/engine/install) or [Docker Desktop](https://docs.docker.com/get-started/get-docker/)

Depending on your host system's hardware, you can run the assistant in one of two modes:

| Mode | Included Data | Required Docker RAM | OpenSearch Heap (`compose.yaml`) |
| :--- | :--- | :---: | :---: |
| **Full Mode (Default)** | IGDB Metadata + 62,000+ Wikipedia Lore Vectors | **8–10 GB** | `-Xms8g -Xmx8g` |
| **Lightweight Mode** | IGDB Metadata Only (Lower-End Hardware) | **4 GB** | `-Xms4g -Xmx4g` |

#### 🌟 Full Mode Setup (Default)
To support neural vector search across 62,000+ Wikipedia lore chunks, 370,000+ IGDB entries, and on-node ML Commons neural embeddings, OpenSearch requires **8 GB of JVM Heap space** (`-Xms8g -Xmx8g`).

**Setting up Docker Desktop (macOS / Windows):**
1. Open **Docker Desktop**.
2. Go to **Settings** ⚙️ ➔ **Resources** ➔ **Memory**.
3. Set the slider to **at least 8 GB** (10 GB recommended).
4. Click **Apply & restart**.

#### ⚡ Lightweight Mode for Lower-End Hardware (Optional)
If your machine has limited RAM (e.g., 8 GB total system RAM) and cannot allocate 8 GB to Docker:
1. Open `compose.yaml` and update the heap setting under `opensearch`:
   ```yaml
   - "OPENSEARCH_JAVA_OPTS=-Xms4g -Xmx4g"
   ```
2. The assistant will operate using the IGDB metadata index, answering queries on structured game data (genres, platforms, release dates, ratings) with a lightweight memory footprint.

---

### Step-by-Step Installation

#### 1. Clone the Repository
```bash
git clone https://github.com/pedro-cardoso16/video-game-knowledge-assistant.git
cd video-game-knowledge-assistant
```

#### 2. Configure Environment Variables
Execute the setup script:

```bash
chmod +x setup.sh && ./setup.sh
```

Open the generated `.env` file and configure your keys. You can create a free Google Gemini key using your Google account at **[Google AI Studio](https://aistudio.google.com/api-keys)**.

> ⚠️ <span style="color:gold">**Warning**</span>  
> Usually, the only reliable model is `gemini-3.1-flash-lite` if you are using the free tier. Sometimes `gemma-4-31b-it` may work, but is more unreliable.

#### 3. Build and Run Container Services
Run the command below to start Docker Compose:

```bash
docker compose up --build -d && docker compose logs sagebot -f
```
> ⚠️ <span style="color:gold">**Warning**</span>  
> This part can take a very long time depending on your hardware $\sim 30$ min,
> so, please be patient.

Wait for the initialization process to finish.

#### 4. Access the Application
Once containers are healthy, open your browser and go to:
👉 **[http://localhost:8501](http://localhost:8501)**

Please click on the `🔄 New conversation` as it may be necessary to refresh in 
order to make the search features work.
---

## 🏗️ Architecture & Pipeline Flow

The system consists of five main components:
1. **Data Ingestion & Extraction**: Scrapes and structures data from IGDB and Wikipedia.
2. **Knowledge Base**: OpenSearch storing both keyword indices and dense vector embeddings.
3. **Retrieval & RAG Flow**: Hybrid search combining BM25 keyword matching with k-NN vector search using Reciprocal Rank Fusion (RRF).
4. **User Interface**: Streamlit web app providing a chat interface and an analytical dashboard.
5. **Monitoring & Feedback**: PostgreSQL database logging query interactions, LLM latency, token usage, and user feedback (thumbs up/down).

```mermaid
flowchart TD
    subgraph UI ["📱 User Interface"]
        User((User)) <--> App["Streamlit Interface (app.py)"]
    end

    subgraph AgentCore ["🧠 AI Agent & Intelligence"]
        App <--> Assistant["LLM Assistant Core (llm.py)"]
        Assistant <--> LLM["Google Gemini API"]
    end

    subgraph DataPipeline ["📥 Data Ingestion Pipeline"]
        IGDB[("IGDB Database\n(Remote API)")] --> Ingest["Ingestion Pipeline\n(ingest.py)"]
        Wiki[("Wikipedia Database\n(Remote Dump)")] --> Ingest
    end

    subgraph Storage ["💾 Knowledge Base"]
        Ingest -->|Index Vectors & Metadata| OpenSearch[("OpenSearch DB\n(BM25 + k-NN Vector)")]
        Assistant <-->|Hybrid Search via RRF| OpenSearch
    end
```

---

## 🧰 Tech Stack

- **LLM / Provider**: Google Gemini (`llm.py`)
- **Embeddings**: SentenceTransformers / HuggingFace embeddings
- **Vector & Keyword Database**: OpenSearch 2.x (Hybrid search + k-NN plugin)
- **Monitoring Database**: PostgreSQL 17
- **UI Framework**: Streamlit
- **Containerization**: Docker & Docker Compose

---

## 📊 Evaluation & Metrics

The project underwent quantitative evaluation for both **Retrieval Performance** and **LLM Output Quality**. Ground truth queries and evaluation notebooks are available in [`main.ipynb`](main.ipynb) with some description of how things work internally.

### 1. Retrieval Evaluation (Hit Rate & MRR)
Evaluated on a ground-truth dataset of queries generated across game titles, lore, and metadata:

```mermaid
---
title: Ground Truth Generation Pipeline
---
flowchart LR
    subgraph Source ["Source"]
        DB[("Knowledge DB")]
    end

    subgraph Generation ["Generation"]
        LLM("LLM")
        Q("questions")
    end

    subgraph Storage ["Storage"]
        GT[("Ground Truth DB")]
    end

    DB -->|retrieve| LLM
    LLM -->|generate| Q
    Q --> GT
```

```mermaid
---
title: Search Evaluation Architecture
---
flowchart LR
    subgraph Inputs ["Inputs"]
        Q("Questions")
        DB[("Knowledge DB")]
        GT("Ground Truth")
    end

    subgraph Search ["Search Pipeline"]
        S("Search")
        R("Results")
    end

    subgraph Metrics ["Evaluation"]
        E("Evaluator")
        MRR("MRR (Mean Reciprocal Rank)")
        HR("HR (Hit Rate)")
    end

    Q --> S
    DB --> S
    S --> R
    R --> E
    GT --> E
    GT --> Q
    E --> MRR
    E --> HR
```
When performing the evaluations, we get this mean result for the two indices 
(IGDB and Wikipedia)
<div align="center">

| Retrieval Method | Hit Rate @ k | Mean Reciprocal Rank (MRR) |
| :--- | :---: | :---: |
| **Lexical Search (BM25)** | 0.822 | 0.735 |
| **Semantic Search (Dense Embeddings)** | 0.316 | 0.236 |
| **Hybrid Search (BM25 + Semantic via RRF)** | **0.793** | **0.707** |

</div>

**Key Takeaway:** Surprisingly, semantic and hybrid search both underperformed 
compared to lexical search. While this could be partly due to embedding quality, 
it is primarily due to how the evaluation was constructed. Since we are working 
with a highly specific dataset, exact keyword matches tend to perform better. 
However, if our evaluation were based on more open-ended questions, hybrid 
search would likely outperform.

In a nutshell, semantic and hybrid search performed poorly because the benchmark 
favors exact document matching, not because semantic search itself is flawed.


### 2. LLM Output & Agent Evaluation (LLM-as-a-Judge)

Outputs were evaluated using an LLM-as-a-Judge approach evaluating tool usage and final answer quality:

```mermaid
---
title: Agent Evaluation Architecture
---
flowchart LR
    subgraph Sources ["Queries & Interaction"]
        U((user))
        Q["questions"]
    end

    subgraph Core ["RAG System"]
        RAG["RAG"]
        A["answer"]
        TU["tool usage"]
    end

    subgraph Evaluation ["Evaluation & Storage"]
        E["evaluator"]
        DB[("evaluation DB")]
    end

    Q --> RAG
    U -->|question| RAG
    RAG --> A
    RAG --> TU
    A --> U
    A --> E
    TU --> E
    E --> DB
    U -->|feedback| DB
```

- **Answer Quality Score**: 0.4
- **Tool Usage Score**: 0.7

---

## 🖥️ User Interface & Monitoring

The application is served via a Streamlit interface containing two primary views:

1. **💬 Chat Assistant**:
    - Ask natural language questions about video games, lore, and metadata.
    - Interactive feedback buttons (👍 Thumbs Up / 👎 Thumbs Down) to log output quality.
        
    <div align="center">
    <img src="media/imgs/chat_example.png" width="600" alt="Chat Example">
    <br>
    <em>Figure 1: SageBot Chat Interface Preview</em>
    </div>

2. **📊 Analytics & Feedback Dashboard**:
    - Live operational tracking displaying query history, latency metrics, user feedback distributions, and model performance logs stored in PostgreSQL.
    - **Don't forget to click on the 🔄 refresh button** to update the page view.

    <div align="center">
    <img src="media/imgs/analytics_example.png" width="500" alt="Analytics Example">
    <br>
    <em>Figure 2: SageBot Analytics Interface Preview</em>
    </div>

```mermaid
---
title: Monitoring Architecture
---
flowchart TD
    subgraph Storage ["Databases"]
        EDB[("evaluation DB")]
        UDB[("usage DB")]
    end

    subgraph Application ["Interface"]
        S("streamlit")
    end

    
    U((user))
   

    EDB --> S
    UDB --> S
    S --> U
```

---

## 📂 Project Structure

```text
.
├── media/imgs/            # Screenshots for README
├── app.py                 # Streamlit UI (Chat & Analytics dashboard)
├── compose.yaml           # Multi-container Docker Compose orchestration
├── dockerfile             # Container definition for SageBot application
├── download_model.py      # Pre-downloads embedding models during Docker build
├── extract.py             # Data extraction script for IGDB & Wikipedia
├── ingest.py              # Ingestion pipeline into OpenSearch & Postgres
├── init-db.sh             # Database initialization script for PostgreSQL
├── llm.py                 # LLM invocation, prompting, and tool logic
├── main.ipynb             # Jupyter Notebook containing analysis & evaluation
├── evaluation.py          # Ground truth generation & LLM-as-a-Judge scripts
├── metrics.py             # Metrics computation (Hit Rate, MRR)
├── monitor.py             # Logging user feedback & metrics to Postgres
├── opensearch_utils.py    # OpenSearch index creation & hybrid search logic
├── requirements.txt       # Python dependencies
├── run.sh                 # Startup script
└── setup.sh               # Environment setup helper
```

---

## 🧪 Running Evaluations Offline

If you want to re-run the retrieval and LLM evaluation benchmarks locally:

1. Ensure OpenSearch and Postgres are running.
2. Open the evaluation notebook:
   ```bash
   jupyter notebook main.ipynb
   ```
3. Run all cells to execute ground truth query generation, Hit Rate/MRR evaluation, and LLM-as-a-Judge scoring. Note that you will run a simplified version since the full test takes a very long time.

---

## 🤝 Acknowledgments
This project was developed as part of the LLM Zoomcamp 2026 cohort led by instructor [@alexeygrigorev](https://github.com/alexeygrigorev). Special thanks to the [DataTalks.Club](https://datatalks.club/) community for providing the resources for this project.