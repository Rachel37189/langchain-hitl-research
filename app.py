import os
import json
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from src.agent import create_agent

st.set_page_config(page_title="NotebookLM - Collector (MVP)")

st.title("📚 NotebookLM — Collector (MVP)")

st.markdown(
    "This small app runs an Agent to collect web sources for a topic. If you haven't provided API keys it will run in mock mode."
)

real_mode = bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("TAVILY_API_KEY"))
if real_mode:
    st.success("Real Tavily + OpenAI integration is enabled.")
else:
    st.warning("Mock mode active. Set OPENAI_API_KEY and TAVILY_API_KEY in .env to enable real search.")

topic = st.text_input("Enter a topic to search/collect", value="Quantum computing")

if "agent" not in st.session_state:
    # create an agent (mock if keys missing)
    st.session_state.agent = create_agent()

if "sources" not in st.session_state:
    st.session_state.sources = []
if "sources_for_review" not in st.session_state:
    st.session_state.sources_for_review = []
if "hitl_request" not in st.session_state:
    st.session_state.hitl_request = None
if "hitl_topic" not in st.session_state:
    st.session_state.hitl_topic = ""
if "hitl_raw_text" not in st.session_state:
    st.session_state.hitl_raw_text = ""

agent = st.session_state.agent

if st.button("Collect sources"):
    st.session_state.sources = []
    st.session_state.sources_for_review = []
    st.session_state.hitl_request = None
    st.session_state.hitl_raw_text = ""
    with st.spinner("Collecting sources..."):
        try:
            if hasattr(agent, "start_collect_sources"):
                result = agent.start_collect_sources(topic)
                if isinstance(result, dict) and result.get("hitl_request"):
                    st.session_state.hitl_request = result["hitl_request"]
                    st.session_state.hitl_topic = topic
                else:
                    st.session_state.sources = result.get("sources", []) if isinstance(result, dict) else []
                    st.session_state.hitl_raw_text = result.get("raw_text", "") if isinstance(result, dict) else ""
            else:
                result = agent.collect_sources(topic) if hasattr(agent, "collect_sources") else []
                st.session_state.sources = result
        except Exception as e:
            st.error(f"Agent failed: {e}")
            st.session_state.sources = []

if st.session_state.hitl_request:
    request = st.session_state.hitl_request
    action_requests = request.get("action_requests", [])
    
    # Check if this is a source selection approval
    if action_requests and action_requests[0].get("name") == "finalize_sources":
        st.subheader("📋 Review and Select Sources")
        st.info("Select which sources you want to include in the final result.")
        
        sources_for_review = st.session_state.get("sources_for_review", [])
        selected_sources = []
        
        for i, source in enumerate(sources_for_review):
            with st.expander(f"✓ {source.get('title', 'Untitled')}", expanded=True):
                col1, col2 = st.columns([1, 4])
                with col1:
                    include = st.checkbox("Include", value=True, key=f"source_select_{i}")
                with col2:
                    st.markdown(f"**URL:** {source.get('url', 'N/A')}")
                    st.write(source.get('snippet', 'No description available'))
                
                if include:
                    selected_sources.append(source)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Approve Selected Sources", type="primary", use_container_width=True):
                # Edit the sources argument to only include selected ones
                edited_sources_json = json.dumps(selected_sources)
                decision_payload = [{
                    "type": "edit",
                    "edited_action": {
                        "name": "finalize_sources",
                        "args": {"sources": edited_sources_json}
                    }
                }]
                with st.spinner("Finalizing sources..."):
                    try:
                        result = agent.resume_collect_sources(decision_payload)
                        st.session_state.sources = result.get("sources", selected_sources)
                        st.session_state.hitl_request = None
                        st.session_state.sources_for_review = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to finalize sources: {e}")
        
        with col2:
            if st.button("❌ Reject All", use_container_width=True):
                decision_payload = [{"type": "reject", "message": "User rejected all sources."}]
                with st.spinner("Canceling..."):
                    try:
                        agent.resume_collect_sources(decision_payload)
                        st.session_state.hitl_request = None
                        st.session_state.sources_for_review = []
                        st.session_state.sources = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to cancel: {e}")
    
    else:
        # Original generic approval UI for tavily_search
        st.warning("Human approval required before executing the search.")
        decisions: list[dict[str, str]] = []
        decision_widgets = []

        for idx, action in enumerate(action_requests):
            st.subheader(f"Review action {idx + 1}")
            st.write(f"**Tool:** {action.get('name')}")
            if action.get("description"):
                st.write(action["description"])
            st.write("**Arguments:**")
            st.json(action.get("args", {}))

            decision = st.radio(
                "Decision",
                ["approve", "reject"],
                index=0,
                key=f"hitl_decision_{idx}",
            )
            reason = ""
            if decision == "reject":
                reason = st.text_area(
                    "Rejection message",
                    value="This search query should not be executed.",
                    key=f"hitl_reason_{idx}",
                    height=80,
                )
            decision_widgets.append({"type": decision, "message": reason})

        if st.button("Submit approval"):
            with st.spinner("Resuming approved search..."):
                decision_payload = []
                for decision in decision_widgets:
                    if decision["type"] == "approve":
                        decision_payload.append({"type": "approve"})
                    else:
                        decision_payload.append({"type": "reject", "message": decision["message"] or "Rejected by reviewer."})
                try:
                    result = agent.resume_collect_sources(decision_payload)
                    if isinstance(result, dict) and result.get("hitl_request"):
                        st.session_state.hitl_request = result["hitl_request"]
                        st.session_state.sources_for_review = result.get("sources_for_review", [])
                        st.rerun()
                    else:
                        st.session_state.sources = result.get("sources", [])
                        st.session_state.hitl_raw_text = result.get("raw_text", "")
                        st.session_state.hitl_request = None
                        st.rerun()
                except Exception as e:
                    st.error(f"Resuming search failed: {e}")

if st.session_state.sources:
    st.success(f"✅ {len(st.session_state.sources)} sources approved and ready for summarization.")
    st.subheader("📚 Approved Sources")
    
    for i, s in enumerate(st.session_state.sources, 1):
        with st.container():
            st.markdown(f"**{i}. [{s.get('title', 'Untitled')}]({s.get('url', '#')})**")
            st.write(s.get('snippet', 'No description'))
            st.divider()

    if st.button("Summarize approved sources"):
        with st.spinner("Summarizing..."):
            try:
                summary = agent.summarize(st.session_state.sources) if hasattr(agent, "summarize") else "(no summarizer available)"
            except Exception as e:
                st.error(f"Summarization failed: {e}")
                summary = ""
        if summary:
            st.subheader("📝 Summary")
            st.markdown(summary)

if st.session_state.hitl_raw_text:
    st.subheader("Raw search output")
    st.write(st.session_state.hitl_raw_text)
