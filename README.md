# RAG Web Research Agent (LangChain + Chroma + Streamlit)

A lightweight RAG-powered web research assistant that:
- Searches the web (DuckDuckGo)
- Summarizes results with inline citations like [1], [2]
- Stores summaries into a Chroma vector database (RAG memory)
- Retrieves relevant memory for future questions
- Runs locally with a Streamlit UI + Ollama (no paid API required)

## Tech Stack
- Python
- Streamlit (UI)
- LangChain (LLM orchestration)
- Ollama (local LLM runtime)
- ChromaDB (vector database)
- SentenceTransformers embeddings (`all-MiniLM-L6-v2`)
- DuckDuckGo search (`ddgs`)

## Project Structure
rag-web-research-agent/
│
├── app.py
├── rag_store.py
├── web_search.py
├── requirements.txt
├── .env.example
├── README.md
├── .gitignore
└── screenshots/
    ├── 01-home.jpg
    ├── 02-prompt.jpg
    ├── 03-answer.jpg
    ├── 04-source-memory.jgg
    ├── 05-source-memory-1.jpg
    ├── 06-memory-only.jpg
    └── 07-updated-example.jpg
