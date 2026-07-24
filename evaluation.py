"""
Evaluates the pipeline in three fields:
1. Search evaluation.
2. Tool usage evaluation.
3. RAG final answer evaluation.
"""

import random
import time
import pandas as pd
import pydantic
import metrics
import sqlite3 as sql
import psycopg as pg

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast, Literal
from tqdm import tqdm
from pydantic import BaseModel
from google.genai.types import GenerateContentConfig

# from query import opensearch_client
from llm import RAGClient

import pandas as pd
import time
import random
from typing import Literal, cast, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pydantic import BaseModel

# --- Evaluate agent instructions ---

EVALUATE_AGENT_INSTRUCTION = """
You are an expert LLM Evaluator. Your role is to provide an objective quality 
score for an agent's performance based on the following inputs:
- QUESTION: The user's original query.
- ANSWER: The final response provided by the LLM.
- CONTEXT: The ground truth reference and the actual sequence of tool calls made 
    by the agent.
- REFERENCE DOCUMENT: The document data from which the QUESTION was generated. 
    That is the ground truth.

### EVALUATION CRITERIA

#### 1. Final Answer Quality
Score based on:
- **Accuracy**: Does it align with the ground truth in the CONTEXT?
- **Relevance**: Does it directly answer the QUESTION without adding irrelevant fluff?
- **Conciseness**: Is the length appropriate (not too brief to be useless, not too long to be tedious)?

#### 2. Tool Usage Efficiency
Score based on:
- **Correctness**: Did the agent use the correct tool for the task?
- **Query Quality**: Were the search queries specific and optimized to find the answer?
- **Logic**: Did the agent avoid redundant tool calls?

### SCORING RUBRIC
- **'bad'**: Factually incorrect, ignores context, or uses tools incorrectly/randomly.
- **'average'**: Correct but incomplete, or tool usage was slightly inefficient.
- **'good'**: Perfectly accurate, fully supported by context, and optimal tool usage.

### OUTPUT FORMAT
You must provide your reasoning first, then the scores in the following format:
Reasoning: <your_explanation>
Answer Score: <bad|average|good>
Tool Score: <bad|average|good>
""".strip()

JUDGE_PROMPT = """
QUESTION:
{question}

ANSWER:
{answer}

CONTEXT:
{context}

REFERENCE DOCUMENT:
{reference_doc}
""".strip()

# --- Ground truth generation instructions ---

GROUND_TRUTH_GENERATION_INSTRUCTION = r"""
Create {count} high-quality questions based on the provided CONTEXT.

### GUIDELINES:
1. **Search Intent**: Design queries that a user would actually type into a search engine to find this specific document.
2. **Natural Phrasing**: Use natural, concise language. Avoid being overly formal or robotic.
3. **Avoid Copy-Pasting**: Do not copy phrases directly from the CONTEXT. Rephrase information into a natural question.
4. **The "Specialist's Guess" Constraint**: 
    - Generally avoid using the game's title directly (do this for only ~1 of the {count} questions).
    - Instead, include **distinguishing characteristics**: mention a unique game mechanic, a specific plot twist, a rare character name, or a distinct setting described in the CONTEXT.
    - The query must contain enough specific "hooks" so that a specialist in the field could reasonably deduce which game is being referenced.
5. **Domain Flexibility**: While most documents relate to video games, some may be outliers (non-game related). Generate appropriate questions based on the provided CONTEXT regardless of the subject matter.
6. **Variety**: Ensure the questions cover different attributes (e.g., one about the story, one about the mechanics, one about the setting).

### OUTPUT FORMAT:
Your response must be a JSON object matching the provided schema. 
Example:
{{
    "questions": ["Which RPG features a world where souls are used as currency in an undead asylum?", "What game has a mechanic involving X in the Y region?"],
    "reasonings": ["Uses the unique 'soul currency' and 'undead asylum' hooks to identify the game", "Targets the specific X mechanic which is unique to this title"]
}}
""".strip()

GROUND_TRUTH_GENERATION_PROMPT = """
CONTEXT:
{context}
""".strip()


class GTOutput(BaseModel):
    """Ground truth output"""

    questions: list[str]
    reasonings: list[str]


class EvaluationResult(pydantic.BaseModel):
    reasoning: str
    answer_score: str  # 'bad', 'average', 'good'
    tool_score: str  # 'bad', 'average', 'good'


class Evaluator:
    def __init__(self, rag_client: RAGClient, ground_truth: pd.DataFrame | None = None):
        self.rag_client = rag_client
        self.ground_truth = ground_truth if ground_truth is not None else pd.DataFrame()

    def _get_db_connection(self):
        # In production, use environment variables for these
        return pg.connect(
            dbname="evaluations",
            user="user",
            password="postgres",
            host="localhost",
            port="5432",
        )
    
    def chunked(self, iterable, size):
        it = list(iterable)
        for i in range(0, len(it), size):
            yield it[i:i + size]

    

    def evaluate_agent(
        self,
        judge: RAGClient,
        overwrite: bool = False,
        max_workers: int = 2,
        index: Literal["igdb", "wikipedia"] = "igdb",
    ) -> None:
        """Performs tools usage and RAG answer evaluations with batch saving."""
        if self.ground_truth.empty:
            raise ValueError("Ground truth is empty.")

        ground_truth_list = self.ground_truth.to_dict(orient="records")
        conn = self._get_db_connection()

        try:
            with conn:
                with conn.cursor() as cursor:
                    if overwrite:
                        cursor.execute("DROP TABLE IF EXISTS evaluations")

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS evaluations (
                            id SERIAL PRIMARY KEY,  
                            source TEXT,
                            question TEXT,
                            answer TEXT,
                            reasoning TEXT,
                            answer_score TEXT,
                            tool_score TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    cursor.execute("SELECT question FROM evaluations")
                    evaluated_questions = {row[0] for row in cursor.fetchall()}

            questions_to_process = [
                x for x in ground_truth_list if x["question"] not in evaluated_questions
            ]

            if not questions_to_process:
                print("All questions already evaluated.")
                return

            window_size = 1
            batch = []
            batch_size = 1  # Save every 1 result(s) to DB

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                with tqdm(total=len(questions_to_process), desc="Evaluating") as pbar:
                    for window in self.chunked(questions_to_process, window_size):
                        futures = {
                            executor.submit(self._process_single_evaluation, x, judge, index): x
                            for x in window
                        }

                        for future in as_completed(futures):
                            result = future.result()
                            if result:
                                batch.append(result)

                            if len(batch) >= batch_size:
                                print("Batch completed. Saving to database.")
                                self._save_eval_batch(batch)
                                batch = []

                            pbar.update(1)

            if batch:
                self._save_eval_batch(batch)

            # # Process in threads
            # with ThreadPoolExecutor(max_workers=max_workers) as executor:
            #     futures = {
            #         executor.submit(self._process_single_evaluation, x, judge, index): x
            #         for x in questions_to_process
            #     }

            #     batch = []
            #     batch_size = 1  # Save every 1 result(s) to DB

            #     for future in tqdm(
            #         as_completed(futures), total=len(futures), desc="Evaluating"
            #     ):
            #         result = future.result()
            #         if result:
            #             batch.append(result)

            #         if len(batch) >= batch_size:
            #             print("Batch completed. Saving to database.")
            #             self._save_eval_batch(batch)
            #             batch = []

            #     if batch:
            #         self._save_eval_batch(batch)

        finally:
            conn.close()

    def _process_single_evaluation(
        self, item: Dict, judge: RAGClient, index: Literal["igdb", "wikipedia"]
    ) -> tuple | None:
        """Helper to evaluate a single question with retry logic."""
        try:
            # 1. Get Answer from RAG
            answer = self.rag_client.rag(item["question"])
            context = self.rag_client.last_history
            reference_doc = self.rag_client.search(
                index=index, query="", doc_id=item["doc_id"]
            )

            # reference_doc_temp = [
            #     data
            #     for data in reference_doc["_source"]
            #     if data in ("title", "name", "summary", "text")
            # ]

            reference_doc_temp = {key:val for key, val in reference_doc["_source"].items() if key in ("title", "name", "summary", "text", "storyline")}
            reference_doc = reference_doc_temp
            # 2. Judge the answer
            retries = 0
            max_retries = 5

            while retries < max_retries:
                try:
                    response = judge.llm(
                        JUDGE_PROMPT.format(
                            question=item["question"],
                            answer=answer,
                            context=context,
                            reference_doc=str(reference_doc),
                        ),
                        config=dict(
                            system_instruction=EVALUATE_AGENT_INSTRUCTION,
                            response_mime_type="application/json",
                            response_schema=EvaluationResult, # Ensure your judge client handles this
                        ),
                    )

                    if response and response.parsed:
                        # Validation (assuming Pydantic model EvaluationResult)
                        # eval_res = EvaluationResult.model_validate(response.parsed)
                        eval_res = dict(response.parsed)

                        judge.flush_usage_history()
                        self.rag_client.flush_usage_history()
                        
                        return (
                            "judge",
                            item["question"],
                            answer,
                            eval_res.get("reasoning"),
                            eval_res.get("answer_score"),
                            eval_res.get("tool_score"),
                        )

                except Exception as e:
                    if "429" in str(e):
                        wait = (2**retries) * 10 + random.random()
                        time.sleep(wait)
                    else:
                        time.sleep(2)
                retries += 1
        except Exception as e:
            print(f"Failed to process: {item['question'][:30]}... Error: {e}")
        return None

    def _save_eval_batch(self, batch: List[tuple]):
        """Inserts a batch of results into Postgres."""
        conn = self._get_db_connection()
        try:
            with conn:
                with conn.cursor() as cursor:
                    cursor.executemany(
                        """INSERT INTO evaluations (source, question, answer, reasoning, answer_score, tool_score) 
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        batch,
                    )
        finally:
            conn.close()

    def generate_ground_truth(
        self,
        index: str,
        count: int = 5,
        n: int = 50,
        file_path: str = "data/ground_truth.csv",
    ) -> pd.DataFrame:
        """Generates questions/reasoning pairs from random documents."""
        if not self.rag_client.search_engine:
            raise ValueError("Search engine not initialized.")

        # Fetch candidate docs
        body = {"size": 1000, "query": {"match_all": {}}}
        results = self.rag_client.search_engine.search(body=body, index=index)["hits"][
            "hits"
        ]

        sampled_docs = random.sample(results, min(n, len(results)))
        all_data = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_to_doc = {}
            for doc in sampled_docs:
                source = doc["_source"]
                # Filter for text-heavy fields to provide better context
                context = " ".join(
                    [
                        str(v)
                        for v in source.values()
                        if isinstance(v, str) and len(v) > 20
                    ]
                )

                f = executor.submit(call_llm, self.rag_client, context, count)
                future_to_doc[f] = doc["_id"]

            for future in tqdm(
                as_completed(future_to_doc),
                total=len(future_to_doc),
                desc="Generating GT",
            ):
                doc_id = future_to_doc[future]
                try:
                    res = (
                        future.result()
                    )  # Expects object with .questions and .reasonings
                    for q, r in zip(res.questions, res.reasonings):
                        all_data.append(
                            {"question": q, "reasoning": r, "doc_id": doc_id}
                        )

                    # Save progress every document to avoid total loss
                    pd.DataFrame(all_data).to_csv(file_path, index=False)
                except Exception as e:
                    print(f"Doc {doc_id} failed: {e}")

        return pd.DataFrame(all_data)


# class Evaluator:
#     def __init__(self, rag_client: RAGClient, ground_truth: pd.DataFrame | None = None):
#         self.rag_client = rag_client
#         if ground_truth is None:
#             self.ground_truth: pd.DataFrame = pd.DataFrame()

#     def evaluate_search(
#         self,
#         index="igdb",
#         search_type: Literal["lexical", "hybrid", "semantic"] = "lexical",
#     ) -> tuple[float, float, pd.DataFrame]:
#         if self.ground_truth.empty:
#             raise ValueError("ground_truth is empty, must set a value")

#         index = cast(Literal["igdb", "wikipedia"], index)

#         return metrics.evaluate_search(
#             self.ground_truth,
#             lambda query: self.rag_client.search(
#                 index=index, query=query, search_type=search_type
#             ),
#         )

#     def evaluate_agent(self, judge: RAGClient, overwrite: bool = False) -> None:
#         """## Evaluate Agent

#         Performs the tools usage and RAG's final answer evaluations.

#         Args:
#             judge (RAGClient): LLM client that will be the judge (evaluator) that is in independent from the evaluated model.

#         Returns:
#             None
#         """
#         ground_truth = self.ground_truth.to_dict(orient="records")

#         conn = pg.connect(
#             dbname="evaluations",
#             user="user",
#             password="postgres",
#             host="localhost",
#             port="5432",
#         )
#         # conn = sql.connect("data/evaluations.sql")

#         with conn:
#             with conn.cursor() as cursor:
#                 if overwrite:
#                     cursor.execute("DELETE FROM evaluations")

#                 cursor.execute("""
#                     CREATE TABLE IF NOT EXISTS evaluations (
#                         id SERIAL PRIMARY KEY,
#                         source TEXT,
#                         question TEXT,
#                         answer TEXT,
#                         reasoning TEXT,
#                         answer_score TEXT,
#                         tool_score TEXT
#                     )
#                     """.strip())

#                 # --- Step 2: Resume Capability ---
#                 # Fetch already evaluated questions to avoid duplicates and save tokens
#                 cursor.execute("SELECT question FROM evaluations")
#                 evaluated_questions = {row[0] for row in cursor.fetchall()}

#                 results_to_insert = []

#                 # --- Step 3: Controlled Parallelism ---
#                 # Use ThreadPoolExecutor with limited workers to maximize throughput without hitting 429s
#                 def process_question(x):
#                     try:

#                         answer = self.rag_client.rag(x["question"])
#                         context = self.rag_client.last_history

#                         eval_res = None
#                         retries = 0
#                         max_retries = 5

#                         # Mandatory delay to stay under RPM limits and avoid 429s
#                         time.sleep(5)

#                         while retries < max_retries:
#                             try:
#                                 response = judge.llm(
#                                     JUDGE_PROMPT.format(
#                                         question=x["question"], answer=answer, context=context
#                                     ),
#                                     config=dict(
#                                         GenerateContentConfig(
#                                             system_instruction=EVALUATE_AGENT_INSTRUCTION,
#                                             response_mime_type="application/json",
#                                             response_schema=EvaluationResult,
#                                         )
#                                     ),
#                                 )

#                                 if response and response.parsed is not None:
#                                     eval_res = EvaluationResult.model_validate(response.parsed)
#                                     break

#                                 print(f"Schema violation for question {x['question'][:20]}... Retrying...")
#                             except Exception as e:
#                                 if "429" in str(e):
#                                     wait_time = 30 * (2**retries)
#                                     print(f"Quota exceeded (429). Retrying in {wait_time} seconds...")
#                                 else:
#                                     print(f"LLM call failed: {e}. Retrying in 4s...")
#                                     wait_time = 4
#                                 time.sleep(wait_time)

#                             retries += 1

#                         if eval_res:
#                             return (
#                                 "judge",
#                                 x["question"],
#                                 answer,
#                                 eval_res.reasoning,
#                                 eval_res.answer_score,
#                                 eval_res.tool_score,
#                             )
#                     except Exception as e:
#                         print(f"Error processing question {x['question'][:20]}: {e}")
#                     return None

#                 # Filter items that need evaluation
#                 questions_to_process = [x for x in ground_truth if x["question"] not in evaluated_questions]

#                 with ThreadPoolExecutor(max_workers=1) as executor:
#                     # Use tqdm to track progress of the parallel execution
#                     futures = [executor.submit(process_question, x) for x in questions_to_process]
#                     for future in tqdm(as_completed(futures), total=len(futures), desc="Parallel LLM judge evaluation"):
#                         res = future.result()
#                         if res:
#                             results_to_insert.append(res)

#                 if results_to_insert:
#                     cursor.executemany(
#                         """INSERT INTO evaluations (
#                         source,
#                         question,
#                         answer,
#                         reasoning,
#                         answer_score,
#                         tool_score) VALUES (%s, %s, %s, %s, %s, %s)
#                         """.strip(),
#                         results_to_insert,
#                     )

#                 cursor.execute(
#                     """
#                     SELECT * FROM evaluations
#                     """.strip(),
#                 )
#                 print(cursor.fetchall())

#         conn.close()

#     def generate_ground_truth(
#         self,
#         index: str,
#         count: int = 5,
#         n: int = 100,
#         file_path: str = "data/ground_truth.csv",
#     ) -> pd.DataFrame:
#         """Generate ground truth.

#         Args:
#             index_name (str): Name of the OpenSearch index.
#             count (int, optional): Number of questions to generate per document. Defaults to `5`.
#             n (int, optional): Number of randomly selected documents. Defaults to `100`.

#         Returns:
#             pd.DataFrame: DataFrame with columns `question` and `doc_id`.
#         """
#         # Use a list to collect results for DataFrame conversion at the end
#         all_data = []
#         body = {
#             "size": 10000,
#             "query": {
#                 "match_all": {},
#             },
#         }

#         if self.rag_client.search_engine is None:
#             raise ValueError("Invalid search_engine in rag_client")

#         results = self.rag_client.search_engine.search(body=body, index=index)["hits"]["hits"]


#         results = random.sample(results, n)

#         with ThreadPoolExecutor(max_workers=2) as executor:
#             futures_map = {}

#             for result in tqdm(results, desc="Submitting tasks", leave=False):
#                 source = result["_source"]
#                 doc_id = result["_id"]

#                 context = "\n".join(
#                     [
#                         f"{key}:\n{str(val)}"
#                         for key, val in source.items()
#                         if isinstance(val, (str, int, float))
#                     ]
#                 )

#                 future = executor.submit(call_llm, self.rag_client, context, count)
#                 futures_map[future] = doc_id

#             for future in tqdm(
#                 as_completed(futures_map),
#                 total=len(futures_map),
#                 desc="Generating Ground Truth",
#             ):
#                 try:
#                     result = future.result()
#                     doc_id = futures_map[future]

#                     # Create rows for each generated question
#                     for q, r in zip(result.questions, result.reasonings):
#                         all_data.append({"question": q, "reasoning": r, "doc_id": doc_id})

#                     # Incremental save: Save current progress to CSV to prevent data loss on crash
#                     temp_df = pd.DataFrame(all_data)
#                     temp_df.to_csv(file_path, index=False, quotechar='"')

#                 except Exception as e:
#                     print(f"Error generating ground truth for a document: {e}")

#         df = pd.DataFrame(all_data)
#         df.to_csv(file_path, index=False, quotechar='"')

#         return df


def call_llm(rag_client: RAGClient, context: str, count: int):
    answer = None

    while True:
        try:
            answer = rag_client.llm(
                GROUND_TRUTH_GENERATION_PROMPT.format(context=context),
                config={
                    "system_instruction": GROUND_TRUTH_GENERATION_INSTRUCTION.format(
                        count=count
                    ),
                    "response_schema": GTOutput,
                    "response_mime_type": "application/json",
                },
            )

            # Check if the LLM actually returned a parsed object matching the schema
            if answer and answer.parsed is not None:
                break

            # If answer.parsed is None, it's a schema violation; treat it as an error to retry
            print("Schema violation: parsed output is None. Retrying...")

        except Exception as e:
            time.sleep(4)

    return cast(GTOutput, answer.parsed)
