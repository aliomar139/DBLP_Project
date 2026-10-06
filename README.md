# DBLP Research Intelligence Platform

A high-performance research intelligence platform and local agentic discovery assistant for the DBLP computer science bibliography (over 8.7M publications).

## 🌟 Key Highlights

- **Hybrid Agentic RAG:** Dual-tier natural language research assistant powered by high-speed cloud inference (Groq `qwen/qwen3.8-27b`, ~400+ tokens/s) with seamless automatic fallback to local Ollama (`qwen2.5-coder:7b`) on CPU when offline.
- **Text-to-SQL & Self-Correction:** Schema-aware query planner generating safe read-only DuckDB SQL with automated self-correction loops.
- **Hybrid Retrieval:** Dense semantic retrieval (MiniLM embeddings + Faiss HNSW index) combined with lexical SQLite FTS5 across 8.73M publication titles.
- **Deep Analytics Engine:** High-performance DuckDB analytics spanning publications, authors, institutions, venues, topics, and citation lineage.
- **Interactive UI:** Modern React + TypeScript + Vite frontend with rich data visualizations (D3, Recharts), graph exploration, and verified calculation provenance.

## 🏗️ Architecture

```
DBLP_Project/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entrypoint
│   │   ├── routes/             # REST API endpoints (assistant, authors, trends, etc.)
│   │   ├── services/           # Agentic RAG, DuckDB services, hybrid retrieval
│   │   └── schemas/            # Pydantic models & response contracts
│   └── tests/                  # API test suites and verification scripts
├── dashboard/                  # React + TypeScript + Vite frontend application
│   ├── src/
│   │   ├── pages/              # Platform dashboard views
│   │   ├── components/         # UI components & charts
│   │   └── api.ts              # Backend API client
├── data/                       # DBLP raw dataset definitions & benchmark samples
├── database/                   # DuckDB database configuration & manifests
├── docs/                       # Technical specs, architecture reviews, and handoff
├── reports/                    # Benchmarks & validation reports
└── scripts/                    # Ingestion, index building, and evaluation utilities
```

## 🚀 Quick Start

### 1. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install fastapi uvicorn duckdb faiss-cpu sentence-transformers onnxruntime
```

### 2. Run the Backend API
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Dashboard
```bash
cd dashboard
npm install
npm run dev
```

### 4. Agentic Assistant Configuration
* **High-Speed Cloud Inference (Recommended):** Add your free [Groq](https://console.groq.com) API key to `.env`:
  ```bash
  GROQ_API_KEY=gsk_...
  GROQ_MODEL=qwen/qwen3.8-27b
  ```
* **Offline Local Fallback:** Ensure [Ollama](https://ollama.ai) is running locally if you want offline CPU execution:
  ```bash
  ollama run qwen2.5-coder:7b
  ```
  *(The system automatically routes to local Ollama if offline or if the cloud API is unreachable).*

## 🛡️ License
MIT License.
