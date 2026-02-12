from __future__ import annotations
import re
import streamlit as st
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from web_search import web_search
from rag_store import add_note, retrieve
from urllib.parse import urlparse


SYSTEM = """You are a research assistant.

Hard rules:
- Use ONLY the provided SOURCES and MEMORY.
- Do NOT invent citations. Only use [1]..[N] from SOURCES.
- NO bullet points, NO lists.

Output format MUST be exactly:

Short Answer:
<3–5 sentences, one paragraph. MUST contain AT LEAST 3 inline citations total, e.g., ...[1] ...[2]. Each citation must be attached to a claim.>

Tight Paragraph Summary:
<3–6 sentences, one paragraph. NO citations here.>

Absolutely DO NOT include any Sources/References/Citations/Links section.
If you cannot include at least 3 citations in Short Answer, rewrite Short Answer until it contains 2+ citations.
"""




def _strip_bad_citations(text: str, max_n: int) -> str:
    """
    Removes citations like [99] or [0] or repeated junk that aren't in 1..max_n.
    Keeps valid [1]..[max_n].
    """
    def repl(m):
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= max_n else ""
    return re.sub(r"\[(\d+)\]", repl, text)

def format_sources_for_prompt(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        title = (r.get("title") or "").strip()
        link = (r.get("link") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        lines.append(f"[{i}] {title}\nURL: {link}\nSnippet: {snippet}\n")
    return "\n".join(lines)

def sources_list(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, start=1):
        link = (r.get("link") or "").strip()
        if link:
            lines.append(f"[{i}] {link}")
    return "\n".join(lines)

def is_bad_url(url: str) -> bool:
    if not url:
        return True
    if len(url) > 140:  # anything longer is usually tracking garbage
        return True

    host = urlparse(url).netloc.lower()

    # tracking / redirect domains
    if "bing.com" in host:
        return True
    if "doubleclick" in host or "googleadservices" in host:
        return True

    return False


st.set_page_config(page_title="RAG Web Research Agent", layout="wide")
st.title("rag-web-research-agent")

# Sidebar controls (cleaner UI)
with st.sidebar:
    st.header("Controls")
    model = st.text_input("Ollama model", value="llama3.1:8b")
    num_results = st.slider("Web results", 3, 10, 6)
    memory_k = st.slider("Memory hits", 0, 8, 4)
    mode = st.radio("Mode", ["Web-first", "Memory-first"], index=0)
    save_to_memory = st.checkbox("Save answer to memory", value=True)

query = st.text_input("Ask a question")

if st.button("Research") and query.strip():
    llm = ChatOllama(model=model, temperature=0.2)

    memory_notes = retrieve(query, k=memory_k) if memory_k > 0 else []
    memory_block = ""
    if memory_notes:
        cleaned_notes = []
        for m in memory_notes:
            note = (m["content"] or "").replace("\r\n", "\n")
            note = re.split(r"\n\s*(?:Sources|Source|References|Citations|Links)\s*:\s*", note, maxsplit=1)[0].strip()
            cleaned_notes.append(f"- ({m['source']}) {note}")
        memory_block = "\n".join(cleaned_notes)

    results = []
    if mode == "Web-first":
        with st.spinner("Searching the web..."):
            results = web_search(query, num_results=num_results)
            results = [r for r in results if not is_bad_url(r.get("link", ""))]
            results = results[:num_results]

    else:
        # Memory-first: only search if memory seems empty/weak
        if len(memory_notes) < 2:
            with st.spinner("Memory looks thin — searching the web..."):
                results = web_search(query, num_results=num_results)
                results = [r for r in results if not is_bad_url(r.get("link", ""))]
                results = results[:num_results]


    sources_block = format_sources_for_prompt(results) if results else "(No web sources used.)"
    urls_only = sources_list(results) if results else "(No web sources used.)"

    prompt = f"""
Question: {query}

MEMORY (never treat this as SOURCES; do not copy links from here):
{memory_block if memory_block else "(No memory retrieved.)"}


SOURCES:
{sources_block}

Write the answer following the exact format rules.
Important:
- If no SOURCES are provided, answer only from MEMORY and say that sources were not used.
- Do NOT include any links or a Sources section in your answer.
"""

    with st.spinner("Summarizing..."):
        resp = llm.invoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])

        def count_citations(text: str) -> int:
            return len(re.findall(r"\[(\d+)\]", text))

        # Retry once if Short Answer has < 2 citations
        attempts = 0
        raw = resp.content

        while attempts < 1:
            # grab just the Short Answer section
            m = re.search(r"Short Answer:\s*(.*?)(?:\n\s*Tight Paragraph Summary:|\Z)", raw, flags=re.S)
            short = m.group(1) if m else raw
            if count_citations(short) >= 3:
                break

            raw = llm.invoke([
                SystemMessage(content=SYSTEM),
                HumanMessage(content=prompt + "\n\nReminder: Short Answer MUST include at least 2 citations like [1] and [2]. Rewrite only Short Answer and Tight Paragraph Summary in the same required format.")
            ]).content
            attempts += 1

        cleaned = raw.replace("\r\n", "\n")

        # Remove any accidental Sources/References/Links block the model tried to add
        cleaned = re.split(r"\n\s*(?:Sources|Source|References|Citations|Links)\s*:\s*", cleaned, maxsplit=1)[0].strip()

        # Also remove "naked URL lists" like: [1] https://...
        cleaned = re.sub(r"\n\[\d+\]\s+https?://\S+\s*", "\n", cleaned).strip()

        if results:
            cleaned = _strip_bad_citations(cleaned, max_n=len(results))
            cleaned = cleaned + "\n\nSources:\n" + urls_only
        else:
            cleaned = cleaned + "\n\nSources:\n(No web sources used.)"


    st.subheader("Answer")
    st.markdown(cleaned)

    if save_to_memory:
        content_only = re.split(r"\n\s*(?:Sources|Source|References|Citations|Links)\s*:\s*", cleaned.replace("\r\n", "\n"), maxsplit=1)[0].strip()
        add_note(text=f"Q: {query}\n\n{content_only}", source="web_research_summary", query=query)
        st.success("Saved to memory (Chroma).")

    # Show sources + memory nicely
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Web sources used")
        if not results:
            st.info("No web sources used in this run.")
        else:
            for i, r in enumerate(results, start=1):
                title = r.get("title", "")
                link = r.get("link", "")
                snippet = r.get("snippet", "")
                st.markdown(f"**[{i}] {title}**")
                if link:
                    st.markdown(link)
                if snippet:
                    st.caption(snippet)
                st.divider()

    with col2:
        st.subheader("Memory retrieved (RAG)")
        if not memory_notes:
            st.info("No memory retrieved.")
        else:
            for m in memory_notes:
                st.markdown(f"**Source:** {m['source']}")
                st.write(m["content"])
                st.divider()
