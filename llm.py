import pydantic
import time

from opensearch_utils import search
from opensearchpy import OpenSearch
from google.genai import Client
from google.genai.types import GenerateContentResponse
import google.genai.types as types
from google.genai.errors import APIError
from dotenv import load_dotenv, get_key
from typing import ParamSpec, TypeVar, Callable, Literal, Iterable

INSTRUCTION = """
You are a specialized Video Game Knowledge Assistant. Your primary goal is to provide 
factually accurate information sourced EXCLUSIVELY from the provided search tools.

## MANDATORY OPERATING PROCEDURES:
1. **TOOL-FIRST RULE**: You are STRICTLY FORBIDDEN from answering a question using your 
   internal knowledge. Even if you believe you know the answer, you MUST call the 
   `opensearch_search` tool first to retrieve the most current data from the database.
   
2. **EVIDENCE-BASED RESPONSES**: Every claim in your answer must be supported by the 
   results returned from the search tool. Do not invent facts or "hallucinate" details.

3. **TRANSPARENCY**: You must explicitly state which tool and index you used to 
   find the information (e.g., "Based on the IGDB index...").

4. **FALLBACK**: If the search tool returns no results or the information is 
   insufficient to answer the question accurately, simply state: "I don't know."

## STYLE GUIDELINES:
- Be concise and objective.
- Briefly explain your reasoning based on the retrieved context.
- Answer ONLY using information you can support with tool evidence.

## Note: 
For now the only index that you can use is 'igdb' in the search tools.
""".strip()

# You may answer questions that unrelated to video games if they are easy and
# simple to answer.

PROMPT = """
QUESTION:
{question}

CONTEXT:
{context}
""".strip()


def opensearch_search(
    index: Literal["igdb", "wikipedia"],
    query: str,
    num: int = 5,
    model_id: str | None = None,
    search_type: Literal["lexical", "hybrid", "semantic"] = "lexical",
    search_fields: Iterable[str] | None = None,
):
    """
    Search the video game database for relevant information.

    Args:
        index (str): The index to search in ('igdb' or 'wikipedia').
        query (str): The search query.
        num (int): Number of results to return.
        model_id (str): The embedding model ID for semantic search.
        search_type (str): Type of search to perform.
        search_fields (Iterable[str]): Fields to search in.
    """
    # This is just a signature for the LLM.
    # The actual execution is handled by the agent loop.
    pass


class RAGClient:
    def __init__(
        self,
        search_engine: OpenSearch | None,
        model: str = "gemini-3.1-flash-lite",
        client: Client | None = None,
    ) -> None:
        self.__tools: list = []
        self.__search_engine: OpenSearch | None = None

        self.__client: Client = client if client else gen_client()

        self.__model: str = model
        self.search_engine = search_engine

        self.add_tool(opensearch_search)

    def llm(self, query: str, config={}):
        """LLM query without agentic tooling or RAG

        Args
        ----
            query (str): user's query.
        """
        default_config = {"system_instruction": INSTRUCTION}
        config = default_config | config

        return self.__client.models.generate_content(
            model=self.__model,
            contents=query,
            config=config,
        )

    def rag(self, query: str) -> str:
        """Retrieval Augmented Generation with Agentic Tool Use

        Args:
            query (str): query to search in the database and for llm to answer
        """
        # Initialize conversation history
        history: types.ContentListUnionDict = [
            types.Content(role="user", parts=[types.Part.from_text(text=query)])
        ]

        max_turns = 5
        turn = 0

        while turn < max_turns:
            try:
                # Call the LLM with the full history
                response = self.__client.models.generate_content(
                    model=self.__model,
                    contents=history,
                    config=types.GenerateContentConfig(
                        system_instruction=INSTRUCTION,
                        tools=[opensearch_search],
                        tool_config=types.ToolConfig(
                            function_calling_config=types.FunctionCallingConfig(
                                # Initial call forces tool use; subsequent calls are AUTO
                                mode=(
                                    types.FunctionCallingConfigMode.ANY
                                    if turn == 0
                                    else types.FunctionCallingConfigMode.AUTO
                                ),
                            ),
                        ),
                    ),
                )
            except APIError as e:
                if "429" in str(e):
                    print("Quota exceeded (429). Retrying in 30 seconds...")
                    time.sleep(30)
                    continue
                raise e

            # Extract text parts manually to avoid the 'non-text parts' warning from .text property
            text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
            
            # If the model provides a final text answer AND no tool calls, we are done
            if text_parts and not response.function_calls:
                # Add the final response to history for completeness
                history.append(
                    types.Content(
                        role="model", parts=response.candidates[0].content.parts
                    )
                )
                return "\n".join(text_parts)

            # Otherwise, the model wants to call tools
            # We must add the model's tool call response to history before responding to it
            history.append(
                types.Content(role="model", parts=response.candidates[0].content.parts)
            )

            func_calls = response.function_calls
            if not func_calls:
                break

            # Process all tool calls in the current turn (Parallel Tool Calling)
            tool_responses = []
            for call in func_calls:
                args = call.args
                name = call.name

                if name == "opensearch_search":
                    # Sanitize and limit arguments to prevent quota exhaustion
                    safe_args = (args or {}).copy()
                    safe_args['num'] = min(safe_args.get('num', 3), 3)
                    
                    results = self.search(**safe_args)
                    
                    # Clean results: only send essential text to the LLM to save tokens
                    cleaned_results = []
                    if isinstance(results, list):
                        for res in results:
                            # Assuming result is a dict from OpenSearch _source
                            text = str(res) if not isinstance(res, dict) else str(res.get('storyline', res.get('name', res)))
                            cleaned_results.append(text[:1000]) # Truncate to 1000 chars
                    else:
                        cleaned_results = [str(results)[:1000]]

                    tool_responses.append(
                        types.Part.from_function_response(
                            name=name,
                            response={"result": cleaned_results},
                        )
                    )
                else:
                    tool_responses.append(
                        types.Part.from_function_response(
                            name=name or "Unknown",
                            response={"error": f"Unknown tool {name}"},
                        )
                    )

            # Add all tool results as a single 'tool' role entry in history
            history.append(types.Content(role="tool", parts=tool_responses))

            turn += 1
            time.sleep(10)

        return "I'm sorry, I was unable to find a final answer after the maximum number of turns."

    def search(
        self,
        index: Literal["igdb", "wikipedia"],
        query: str,
        num: int = 5,
        model_id: str | None = None,
        search_type: Literal["lexical", "hybrid", "semantic"] = "lexical",
        search_fields: Iterable[str] | None = None,
    ):

        if self.search_engine is None:
            raise RuntimeError("Search engine not initialized.")

        return search(
            self.search_engine,
            index,
            query,
            num,
            model_id,
            {},
            search_type,
            search_fields,
        )

    @property
    def search_engine(self) -> OpenSearch | None:
        return self.__search_engine

    @search_engine.setter
    def search_engine(self, value):
        self.__search_engine = value

    @property
    def model(self):
        return self.__model

    @model.setter
    def model(self, value: str):
        try:
            self.__client.models.get(model=value)
        except APIError as error:
            print(f"{error.message}")

        self.__model = value

    @property
    def tools(self):
        return self.__tools

    def add_tool(self, tool):
        if tool not in self.__tools:
            self.__tools.append(tool)

    def remove_tool(self, tool):
        if tool in self.__tools:
            self.__tools.remove(tool)


def build_context(search_results):
    context = []

    for result in search_results:
        context.append(str(result))

    return "\n".join(context)


def build_prompt(question: str, context: str):
    return PROMPT.format(question=question, context=context)


def gen_client() -> Client:
    load_dotenv()
    client = Client()

    return client
