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
   internal knowledge alone. You MUST call the `opensearch_search` tool first.

2. **INDIVIDUAL & CLEAN QUERIES**:
   - **One Game Per Search**: When looking up information for multiple games, you MUST 
    execute **separate, individual tool calls for EACH game**. NEVER combine multiple 
    game titles into a single search query.
   - **Clean Game Titles**: Strip out extra noise from Wikipedia or conversation history 
    before searching IGDB (e.g., search for `"Lords of the Fallen"`, NOT `"Lords of the Fallen (2014)"`).

3. **MULTI-STEP & STRATEGIC REASONING**:
   - Complex queries (e.g., "games similar to X") require multi-step search workflows:
        * **Step 1 (Inspect)**: Search for the target game to retrieve its traits (genres, themes, storyline).
        * **Step 2 (Discover)**: Formulate individual search queries for each discovered candidate game.
        * **Step 3 (Verify)**: Confirm details from retrieved documents before outputting results.

4. **SEARCH TACTICS & RETRIES**:
   - Use `igdb` for structured metadata, ratings, summaries, and storylines.
   - Use `wikipedia` for historical or broader contextual queries.
   - Whenever possible, query ALL available indices (both `igdb` and `wikipedia`) to synthesize a more comprehensive and complete answer.
   - If `lexical` search yields no results for a title, retry using `hybrid` or `semantic` search.

5. **EVIDENCE-BASED RESPONSES**:
   - Every claim, title, rating, or fact in your final answer MUST be supported by 
    retrieved tool evidence. Do not invent facts or ratings.

6. **TRANSPARENCY & FALLBACK**:
   - Explicitly state which index you used (e.g., "Based on the IGDB index...").
   - If you execute an individual search for a specific game across indices/search types 
    and find no results, explicitly state for that specific game: "For this specific one, I couldn't retrieve the information."

## STYLE GUIDELINES:
- Be concise, objective, and well-structured.
- Answer ONLY using details supported by tool evidence.
""".strip()

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
        self.default_boost_dict: dict[str, dict[str, float]] | None = None
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

    def rag(self, query: str, history: list | None = None) -> tuple[str, list]:  # type: ignore
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
            types.Content(role="user", parts=[types.Part.from_text(text=query)])  # type: ignore
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
                p.text for p in response.candidates[0].content.parts if p.text  # type: ignore
            ]

            if text_parts and not response.function_calls:  # type: ignore
                history.append(
                    types.Content(
                        role="model", parts=response.candidates[0].content.parts  # type: ignore
                    )
                )
                self.last_history = history
                return "\n".join(text_parts), history

            history.append(
                types.Content(role="model", parts=response.candidates[0].content.parts)  # type: ignore
            )

            func_calls = response.function_calls  # type: ignore
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

            history.append(types.Content(role="tool", parts=tool_responses))  # type: ignore
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
        search_type: str | Literal["lexical", "hybrid", "semantic"] = "lexical",
        search_fields: Iterable[str] | None = None,
        boost_dict: dict = {},
        doc_id: str | None = None,
    ):
        if self.default_boost_dict is not None:
            boost_dict = self.default_boost_dict[index]

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
    client = Client()

    return client
