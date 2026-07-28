import pydantic
import time
import random
from ingest import save_usage_metadata
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
   
2. **QUERY REWRITING**: When calling search tools, do not simply pass the user's query. 
   Rephrase and optimize the query to improve search recall. Extract key entities and 
   concepts to create a search term that is likely to match the stored document metadata.
   
3. **EVIDENCE-BASED RESPONSES**: Every claim in your answer must be supported by the 
   results returned from the search tool. Do not invent facts or "hallucinate" details.

4. **TRANSPARENCY**: You must explicitly state which tool and index you used to 
   find the information (e.g., "Based on the IGDB index...").

5. **FALLBACK**: If the search tool returns no results or the information is 
   insufficient to answer the question accurately, simply state: "I don't know."

## STYLE GUIDELINES:
- Be concise and objective.
- Briefly explain your reasoning based on the retrieved context.
- Answer ONLY using information you can support with tool evidence.
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
        ai_client: Client | None = None,
    ) -> None:
        self.usage_history = []
        self.last_history = None
        self.__tools: list = []
        self.__search_engine: OpenSearch | None = None

        self.__client: Client = ai_client if ai_client else gen_client()

        self.__model: str = model
        self.search_engine = search_engine

        self.add_tool(opensearch_search)

    def flush_usage_history(self):
        self.usage_history = []

    def llm(self, query: str, config={}):
        """LLM query without agentic tooling or RAG

        Args
        ----
            query (str): user's query.
        """
        default_config = {"system_instruction": INSTRUCTION}
        config = default_config | config

        response = self.__client.models.generate_content(
            model=self.__model,
            contents=query,
            config=config,
        )

        self.usage_history.append(response.usage_metadata)

        return response

    # def rag(self, query: str) -> str:
    #     """Retrieval Augmented Generation with Agentic Tool Use

    #     Args:
    #         query (str): query to search in the database and for llm to answer
    #     """
    #     # Initialize conversation history
    #     history: types.ContentListUnionDict = [
    #         types.Content(role="user", parts=[types.Part.from_text(text=query)])
    #     ]

    #     max_turns = 5
    #     max_retries = 5
    #     turn = 0

    #     while turn < max_turns:
    #         retries = 0
    #         response = None
    #         while retries < max_retries:
    #             try:
    #                 # Call the LLM with the full history
    #                 response = self.__client.models.generate_content(
    #                     model=self.__model,
    #                     contents=history,
    #                     config=types.GenerateContentConfig(
    #                         system_instruction=INSTRUCTION,
    #                         tools=[opensearch_search],
    #                         tool_config=types.ToolConfig(
    #                             function_calling_config=types.FunctionCallingConfig(
    #                                 # Initial call forces tool use; subsequent calls are AUTO
    #                                 mode=(
    #                                     types.FunctionCallingConfigMode.ANY
    #                                     if turn == 0
    #                                     else types.FunctionCallingConfigMode.AUTO
    #                                 ),
    #                             ),
    #                         ),
    #                     ),
    #                 )

    #                 self.usage_history.append(response.usage_metadata)
    #                 break

    #             except APIError as e:
    #                 if "429" in str(e):
    #                     retries += 1
    #                     wait_time = (2**retries) * 10 + random.random()
    #                     print(f"Quota exceeded (429). Retrying in {wait_time:.2f} seconds...")
    #                     time.sleep(wait_time)
    #                     continue
    #                 raise e

    #         print("Successfully retrieved the content.")
    #         # Extract text parts manually to avoid the 'non-text parts' warning from .text property
    #         text_parts = [
    #             p.text for p in response.candidates[0].content.parts if p.text
    #         ]

    #         # If the model provides a final text answer AND no tool calls, we are done
    #         if text_parts and not response.function_calls:
    #             # Add the final response to history for completeness
    #             history.append(
    #                 types.Content(
    #                     role="model", parts=response.candidates[0].content.parts
    #                 )
    #             )

    #             self.last_history = history
    #             return "\n".join(text_parts)

    #         # Otherwise, the model wants to call tools
    #         # We must add the model's tool call response to history before responding to it
    #         history.append(
    #             types.Content(role="model", parts=response.candidates[0].content.parts)
    #         )

    #         func_calls = response.function_calls
    #         if not func_calls:
    #             break

    #         # Process all tool calls in the current turn (Parallel Tool Calling)
    #         tool_responses = []
    #         for call in func_calls:
    #             args = call.args
    #             name = call.name

    #             if name == "opensearch_search":
    #                 # Sanitize and limit arguments to prevent quota exhaustion
    #                 safe_args = (args or {}).copy()
    #                 safe_args["num"] = min(safe_args.get("num", 3), 3)

    #                 results = self.search(**safe_args)

    #                 # Clean results: OpenSearch returns a dict with hits -> hits.
    #                 # We must extract _source and ignore vectors.
    #                 cleaned_results = []

    #                 # Handle OpenSearch response structure
    #                 hits = []
    #                 if isinstance(results, dict) and "hits" in results:
    #                     hits = results["hits"].get("hits", [])
    #                 elif isinstance(results, list):
    #                     hits = results

    #                 for hit in hits:
    #                     # Get the actual document source
    #                     source = (
    #                         hit.get("_source", hit) if isinstance(hit, dict) else hit
    #                     )

    #                     if isinstance(source, dict):
    #                         # Filter out the vector fields and technical metadata to get the actual content
    #                         # We exclude any field containing 'vector' or 'embedding' to be generic
    #                         content_fields = [
    #                             f"{k}: {v}"
    #                             for k, v in source.items()
    #                             if not any(
    #                                 bad in k.lower()
    #                                 for bad in ["vector", "embedding", "id"]
    #                             )
    #                         ]

    #                         text_val = ", ".join(content_fields)
    #                         cleaned_results.append(
    #                             text_val[:1000] if text_val else "Empty document"
    #                         )
    #                     else:
    #                         cleaned_results.append(str(source)[:1000])

    #                 if not cleaned_results:
    #                     cleaned_results = ["No relevant information found."]

    #                 tool_responses.append(
    #                     types.Part.from_function_response(
    #                         name=name,
    #                         response={"result": cleaned_results},
    #                     )
    #                 )
    #             else:
    #                 tool_responses.append(
    #                     types.Part.from_function_response(
    #                         name=name or "Unknown",
    #                         response={"error": f"Unknown tool {name}"},
    #                     )
    #                 )

    #         # Add all tool results as a single 'tool' role entry in history
    #         history.append(types.Content(role="tool", parts=tool_responses))

    #         turn += 1
    #         time.sleep(10)

    #     return "I'm sorry, I was unable to find a final answer after the maximum number of turns."

    def rag(self, query: str, history: list | None = None) -> tuple[str, list]:
        """Retrieval Augmented Generation with Agentic Tool Use

        Args:
            query (str): query to search in the database and for llm to answer
            history (list | None): prior conversation turns (Gemini Content objects).
                Pass None to start a fresh conversation.

        Returns:
            (answer, updated_history) so the caller can persist it for the next turn.
        """
        if history is None:
            history: types.ContentListUnionDict = []

        history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=query)])
        )

        max_turns = 10
        max_retries = 5
        turn = 0

        while turn < max_turns:
            retries = 0
            response = None
            while retries < max_retries:
                try:
                    response = self.__client.models.generate_content(
                        model=self.__model,
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=INSTRUCTION,
                            tools=[opensearch_search],
                            tool_config=types.ToolConfig(
                                function_calling_config=types.FunctionCallingConfig(
                                    mode=(
                                        types.FunctionCallingConfigMode.ANY
                                        if turn == 0
                                        else types.FunctionCallingConfigMode.AUTO
                                    ),
                                ),
                            ),
                        ),
                    )
                    
                    self.usage_history.append(response.usage_metadata)
                    break

                except APIError as e:
                    if "429" in str(e):
                        retries += 1
                        wait_time = (2**retries) * 10 + random.random()
                        print(
                            f"Quota exceeded (429). Retrying in {wait_time:.2f} seconds..."
                        )
                        time.sleep(wait_time)
                        continue
                    raise e

            print("Successfully retrieved the content.")
            text_parts = [
                p.text for p in response.candidates[0].content.parts if p.text
            ]

            if text_parts and not response.function_calls:
                history.append(
                    types.Content(
                        role="model", parts=response.candidates[0].content.parts
                    )
                )
                self.last_history = history
                return "\n".join(text_parts), history

            history.append(
                types.Content(role="model", parts=response.candidates[0].content.parts)
            )

            func_calls = response.function_calls
            if not func_calls:
                break

            tool_responses = []
            for call in func_calls:
                args = call.args
                name = call.name

                if name == "opensearch_search":
                    safe_args = (args or {}).copy()
                    safe_args["num"] = min(safe_args.get("num", 3), 3)
                    results = self.search(**safe_args)

                    cleaned_results = []
                    hits = []
                    if isinstance(results, dict) and "hits" in results:
                        hits = results["hits"].get("hits", [])
                    elif isinstance(results, list):
                        hits = results

                    for hit in hits:
                        source = (
                            hit.get("_source", hit) if isinstance(hit, dict) else hit
                        )
                        if isinstance(source, dict):
                            content_fields = [
                                f"{k}: {v}"
                                for k, v in source.items()
                                if not any(
                                    bad in k.lower()
                                    for bad in ["vector", "embedding", "id"]
                                )
                            ]
                            text_val = ", ".join(content_fields)
                            cleaned_results.append(
                                text_val[:1000] if text_val else "Empty document"
                            )
                        else:
                            cleaned_results.append(str(source)[:1000])

                    if not cleaned_results:
                        cleaned_results = ["No relevant information found."]

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

            history.append(types.Content(role="tool", parts=tool_responses))
            turn += 1
            time.sleep(10)

        return (
            "I'm sorry, I was unable to find a final answer after the maximum number of turns.",
            history,
        )

    def search(
        self,
        index: Literal["igdb", "wikipedia"],
        query: str,
        num: int = 5,
        model_id: str | None = None,
        search_type: Literal["lexical", "hybrid", "semantic"] = "lexical",
        search_fields: Iterable[str] | None = None,
        boost_dict: dict = {},
        doc_id: str | None = None,
    ):

        if self.search_engine is None:
            raise RuntimeError("Search engine not initialized.")

        if doc_id is not None:
            return self.search_engine.get(index=index, id=doc_id)

        return search(
            self.search_engine,
            index,
            query,
            num,
            model_id,
            boost_dict,
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
    client = Client(
        # http_options={"timeout": 10},
    )

    return client
