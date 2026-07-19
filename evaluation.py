"""
Evaluates the pipeline in three fields:
1. Search evaluation.
2. Tool usage evaluation.
3. RAG final answer evaluation.
"""

from google.genai.types import GenerateContentConfig
import metrics
import pandas as pd
import pydantic
import json 

from llm import RAGClient, OpenSearch

EVALUATE_AGENT_INSTRUCTIONS = """
You are an expert LLM Evaluator. Your role is to provide an objective quality 
score for an agent's performance based on the following inputs:
- QUESTION: The user's original query.
- ANSWER: The final response provided by the LLM.
- CONTEXT: The ground truth reference and the actual sequence of tool calls made 
    by the agent.

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

import sqlite3 as sql

JUDGE_PROMPT = """
QUESTION:
{question}

ANSWER:
{answer}

CONTEXT:
{context}
""".strip()


class EvaluationResult(pydantic.BaseModel):
    reasoning: str
    answer_score: str  # 'bad', 'average', 'good'
    tool_score: str  # 'bad', 'average', 'good'


class Evaluator:
    def __init__(self, rag_client: RAGClient):
        self.rag_client = rag_client
        self.ground_truth = pd.DataFrame()

    def evaluate_search(self) -> tuple[float, float, pd.DataFrame]:
        return metrics.evaluate_search(self.ground_truth, self.rag_client.search)

    def evaluate_agent(self, judge: RAGClient):
        ground_truth = self.ground_truth.to_dict(orient="records")

        conn = sql.connect("my_data_base.sql")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                question TEXT,
                answer TEXT,
                reasoning TEXT,
                answer_score TEXT,
                tool_score TEXT
            )
            """.strip())

        for x in ground_truth:
            response = judge.llm(
                JUDGE_PROMPT.format(
                    question=x["question"], answer=x["answer"], context=x["context"]
                ),
                config=GenerateContentConfig(
                    system_instruction=EVALUATE_AGENT_INSTRUCTIONS,
                    response_mime_type="application/json",
                    response_schema=EvaluationResult,
                ),
            )

            eval_res: EvaluationResult = response.parsed

            cursor.execute(
                "INSERT INTO evaluations (question, answer, reasoning, answer_score, tool_score) VALUES (?, ?, ?, ?, ?)",
                (x["question"], x["answer"], eval_res.reasoning, eval_res.answer_score, eval_res.tool_score)
            )
            conn.commit()

    # def optimize(search_fields: Iterable[str]) -> dict[str, float]:
    # pass
    # search_fields = set(search_fields)

    # return {}
