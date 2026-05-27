"""Agent helpers for the NotebookLM-like project.

This module exposes `create_agent` which will try to construct a real
LangChain agent when API keys are present. Otherwise it returns a small
`MockAgent` suitable for local development and UI prototyping.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

try:
    from langchain.agents import create_agent as lc_create_agent
    from langchain.agents.middleware import HumanInTheLoopMiddleware
    from langchain.chat_models import init_chat_model
    from langchain_tavily import TavilySearch
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False


class MockAgent:
    """A minimal mock agent used when API keys are not available.

    Methods:
    - `collect_sources(topic)` -> list of source dicts
    - `summarize(sources)` -> short summary string
    - `invoke(text)` -> dict with sources and summary
    """

    def __init__(self) -> None:
        pass

    def collect_sources(self, topic: str) -> List[Dict[str, Any]]:
        # deterministic fake sources for UI testing
        return [
            {"title": f"Intro to {topic}", "url": "https://example.com/intro", "snippet": f"A gentle intro to {topic}."},
            {"title": f"Deep dive: {topic}", "url": "https://example.org/deep", "snippet": f"An in-depth article about {topic}."},
            {"title": f"News on {topic}", "url": "https://news.example/{topic}", "snippet": f"Recent news related to {topic}."},
        ]

    def summarize(self, sources: List[Dict[str, Any]]) -> str:
        titles = ", ".join(s.get("title", "(untitled)") for s in sources[:3])
        return f"Summary (mock): Found {len(sources)} sources including: {titles}. Key points synthesized." 

    def invoke(self, text: str) -> Dict[str, Any]:
        sources = self.collect_sources(text)
        summary = self.summarize(sources)
        return {"sources": sources, "summary": summary}


class RealAgent:
    def __init__(self, llm: Any, search_tool: Any, agent_graph: Any) -> None:
        self.llm = llm
        self.search = search_tool
        self.agent_graph = agent_graph
        self._thread_id: Optional[uuid.UUID] = None

    def _extract_text(self, output: Any) -> str:
        if isinstance(output, dict):
            if "messages" in output and isinstance(output["messages"], list):
                texts: List[str] = []
                for message in output["messages"]:
                    if isinstance(message, dict):
                        texts.append(str(message.get("content", "")))
                    else:
                        texts.append(
                            str(
                                getattr(message, "content", None)
                                or getattr(message, "text", None)
                                or message
                            )
                        )
                return "\n".join(texts)
            return json.dumps(output)
        if isinstance(output, list):
            return "\n".join(self._extract_text(item) for item in output)
        return str(output)

    def _parse_sources(self, text: str) -> List[Dict[str, Any]]:
        text = text.strip()
        if not text:
            return []

        json_text = None
        if text.startswith("[") or text.startswith("{"):
            json_text = text
        else:
            match = re.search(r"(\[.*\])", text, re.S)
            if match:
                json_text = match.group(1)

        if json_text:
            try:
                parsed = json.loads(json_text)
                if isinstance(parsed, list):
                    return [
                        {
                            "title": item.get("title", "Untitled"),
                            "url": item.get("url", ""),
                            "snippet": item.get("snippet", ""),
                        }
                        for item in parsed
                        if isinstance(item, dict)
                    ]
                if isinstance(parsed, dict) and isinstance(parsed.get("sources"), list):
                    return [
                        {
                            "title": item.get("title", "Untitled"),
                            "url": item.get("url", ""),
                            "snippet": item.get("snippet", ""),
                        }
                        for item in parsed["sources"]
                        if isinstance(item, dict)
                    ]
            except json.JSONDecodeError:
                pass

        return []

    def _run_graph(self, input_value: Any, thread_id: uuid.UUID) -> Dict[str, Any]:
        config = {"configurable": {"thread_id": thread_id}}
        all_chunks: List[Any] = []
        try:
            for chunk in self.agent_graph.stream(input_value, config=config):
                if isinstance(chunk, dict) and "__interrupt__" in chunk:
                    interrupt_obj = chunk["__interrupt__"][0]
                    hitl_value = interrupt_obj.value
                    
                    # Check if this is a finalize_sources interrupt
                    action_requests = hitl_value.get("action_requests", [])
                    if action_requests and action_requests[0].get("name") == "finalize_sources":
                        # Extract sources from the tool arguments
                        sources_json = action_requests[0].get("args", {}).get("sources", "[]")
                        try:
                            sources = json.loads(sources_json) if isinstance(sources_json, str) else sources_json
                        except:
                            sources = []
                        return {"hitl_request": hitl_value, "sources_for_review": sources}
                    
                    return {"hitl_request": hitl_value}
                all_chunks.append(chunk)
        except Exception as e:
            import traceback
            print("\n=== GRAPH EXECUTION ERROR ===")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            print("\nFull traceback:")
            traceback.print_exc()
            print("=== END ERROR ===")
            raise

        if not all_chunks:
            return {"sources": []}

        # Check if finalize_sources tool was executed - extract from tools chunk
        for chunk in all_chunks:
            if isinstance(chunk, dict) and "tools" in chunk:
                messages = chunk["tools"].get("messages", [])
                for msg in messages:
                    tool_name = getattr(msg, "name", None) or (msg.get("name") if isinstance(msg, dict) else None)
                    if tool_name == "finalize_sources":
                        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
                        if content:
                            sources = self._parse_sources(content)
                            if sources:
                                return {"sources": sources, "raw_text": content}

        # Extract the final AI message from the last 'model' chunk
        final_message = None
        for chunk in reversed(all_chunks):
            if isinstance(chunk, dict) and "model" in chunk:
                messages = chunk["model"].get("messages", [])
                if messages:
                    final_message = messages[-1]
                    break

        if final_message is None:
            return {"sources": []}

        text = self._extract_text(final_message)
        return {"sources": self._parse_sources(text), "raw_text": text}

    def start_collect_sources(self, topic: str) -> Dict[str, Any]:
        self._thread_id = uuid.uuid4()
        prompt = (
            "Collect web sources for the user's topic. Return only a JSON array of "
            "objects with title, url, and snippet fields."
        )
        return self._run_graph({"messages": [{"role": "user", "content": f"{prompt}\n\nTopic: {topic}"}]}, self._thread_id)

    def resume_collect_sources(self, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if self._thread_id is None:
            return {"sources": []}
        return self._run_graph(Command(resume={"decisions": decisions}), self._thread_id)

    def collect_sources(self, topic: str) -> List[Dict[str, Any]]:
        try:
            result = self.search.invoke({"query": topic})
        except Exception as exc:
            return [{"title": "(error)", "url": "", "snippet": str(exc)}]

        if not isinstance(result, dict):
            return []

        raw_results = result.get("results") or []
        sources: List[Dict[str, Any]] = []
        for entry in raw_results:
            sources.append(
                {
                    "title": entry.get("title") or entry.get("url") or "Untitled",
                    "url": entry.get("url", ""),
                    "snippet": entry.get("content") or entry.get("snippet") or entry.get("raw_content") or "",
                }
            )
        return sources

    def summarize(self, sources: List[Dict[str, Any]]) -> str:
        if not sources:
            return "No sources to summarize."

        lines = [
            "Summarize the following sources into a short paragraph, highlighting the main findings and relevance:",
        ]
        for idx, source in enumerate(sources, start=1):
            lines.append(
                f"{idx}. {source['title']} ({source['url']}) - {source['snippet']}"
            )
        prompt = "\n".join(lines)

        try:
            response = self.llm.invoke(prompt)
        except Exception:
            response = self.llm.invoke(str(prompt))

        if isinstance(response, str):
            return response

        if hasattr(response, "content"):
            return getattr(response, "content")
        if hasattr(response, "text"):
            return getattr(response, "text")
        return str(response)

    def invoke(self, text: str) -> Dict[str, Any]:
        sources = self.collect_sources(text)
        summary = self.summarize(sources)
        return {"sources": sources, "summary": summary}


def create_agent(
    use_mock_if_no_keys: bool = True,
    openai_api_key: Optional[str] = None,
    tavily_api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Any:
    """Create a LangChain agent when keys are present, otherwise return MockAgent.

    Args:
        use_mock_if_no_keys: if True and keys not found, return MockAgent.
        openai_api_key, tavily_api_key: override env vars.
        model: model string for `init_chat_model` (e.g. 'openai:gpt-3.5-turbo').
    """
    openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    tavily_api_key = tavily_api_key or os.environ.get("TAVILY_API_KEY")
    model = model or os.environ.get("MODEL", "openai:gpt-3.5-turbo")

    if LANGCHAIN_AVAILABLE and openai_api_key and tavily_api_key:
        from langchain_core.tools import tool
        
        llm = init_chat_model(model, api_key=openai_api_key)
        search = TavilySearch(
            tavily_api_key=tavily_api_key,
            max_results=5,
            include_answer=False,
            include_raw_content=False,
            include_images=False,
        )
        
        @tool
        def finalize_sources(sources: str) -> str:
            """Finalize and return the selected sources as JSON.
            
            Args:
                sources: JSON string containing array of source objects with title, url, and snippet.
            """
            return sources
        
        agent_graph = lc_create_agent(
            model=llm,
            tools=[search, finalize_sources],
            system_prompt=(
                "You are a research assistant. First, use tavily_search to collect sources. "
                "Then, use finalize_sources to return the results as a JSON array of objects "
                "with title, url, and snippet fields."
            ),
            middleware=[
                HumanInTheLoopMiddleware(
                    {
                        "tavily_search": {
                            "allowed_decisions": ["approve", "reject"],
                            "description": "Review the Tavily search query before execution.",
                        },
                        "finalize_sources": {
                            "allowed_decisions": ["approve", "edit", "reject"],
                            "description": "Review and approve the final sources before returning them.",
                        },
                    }
                )
            ],
            checkpointer=InMemorySaver(),
        )
        return RealAgent(llm, search, agent_graph)

    if use_mock_if_no_keys:
        return MockAgent()

    raise RuntimeError("LangChain not available or API keys missing; set OPENAI_API_KEY and TAVILY_API_KEY")


if __name__ == "__main__":
    a = create_agent()
    print(type(a))
