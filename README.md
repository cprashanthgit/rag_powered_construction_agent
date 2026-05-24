# 🏗️ Construction Safety RAG Assistant

Ever wished you could just *ask* a question and get a real answer pulled straight from construction safety manuals? That's exactly what this project does.

We built a **Retrieval-Augmented Generation (RAG)** system that lets you query construction safety documents in plain English. It combines hybrid search, cross-encoder re-ranking, and a flexible dual-mode setup — so you can run it completely **free and offline**, or flip a switch to use **OpenAI + Pinecone** for significantly better answer quality.

---

## ✨ What It Can Do

- 🔍 **Hybrid Search** — combines BM25 keyword search with dense vector retrieval, then fuses results using Reciprocal Rank Fusion for better coverage
- 🎯 **Cross-Encoder Re-ranking** — uses `ms-marco-MiniLM-L-6-v2` to score and narrow down the top-5 candidates to the 3 most relevant document chunks
- 🔀 **Dual-Mode Architecture** — want to keep it free? Use Mode 1. Need polished demo-quality answers? Switch to Mode 2. It's literally just editing 5 lines in a `.env` file
- 🖥️ **Streamlit Chat UI** — a clean, interactive chat interface that runs at `localhost:8501`
- ⚡ **FastAPI REST Server** — exposes both sync and streaming query endpoints at `localhost:8000`
- 📄 **Multi-Document Ingestion** — ingests several construction safety PDFs and chunks them into 8,938 searchable segments

---

## 🏛️ How It Works (Architecture)

```
PDFs (./data/)
    │
    ▼  ingest.py → chunker.py
Chunks (8938 total, ~434 chars each)
    │
    ├──────────────────────────────────────────────────┐
    ▼  [MODE 1] FAISS (local file)                    ▼  [MODE 2] Pinecone (cloud)
    │  all-MiniLM-L6-v2 (384-dim, free)               │  text-embedding-3-small (1536-dim, ~$0.02 once)
    └──────────────────┬───────────────────────────────┘
                       │
                       ▼  hybrid_retriever.py
              BM25 (sparse) + Dense (vector)
              Reciprocal Rank Fusion → top-5 candidates
                       │
                       ▼  reranker.py
              CrossEncoder (ms-marco-MiniLM) → top-3 docs
                       │
    ┌──────────────────┴───────────────────────────────┐
    ▼  [MODE 1] Flan-T5-base (local, CPU, free)        ▼  [MODE 2] GPT-3.5-turbo (OpenAI API, ~$0.002/q)
    └──────────────────┬───────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Streamlit UI       FastAPI Server
        (port 8501)        (port 8000)
```

---

## 🔀 Mode 1 vs Mode 2 — Quick Comparison

| Feature | Mode 1 — Local (Free) | Mode 2 — Cloud (Best Quality) |
|---|---|---|
| Embedding | `all-MiniLM-L6-v2` (HuggingFace) | `text-embedding-3-small` (OpenAI) |
| Vector DB | FAISS (stored locally) | Pinecone (serverless cloud) |
| LLM | `google/flan-t5-base` (runs on CPU) | `gpt-3.5-turbo` (OpenAI API) |
| Answer Quality | Short, 1-2 sentences | Full paragraphs with source citations |
| Index Build Cost | **$0.00** | ~$0.02 (one-time only) |
| Per Query Cost | **$0.00** | ~$0.002 |
| Best For | Development / offline use | Demo day / presentations |

---

## 📁 Project Structure

```
Construction_RAG_Assistant/
├── .env.example              # ← Copy this to .env and fill in your API keys
├── .gitignore
├── requirements.txt
├── README.md
├── RUN_GUIDE.md              # Detailed walkthrough for both modes
│
├── config.py                 # Reads .env and validates all settings
├── ingest.py                 # Loads PDFs from ./data/
├── chunker.py                # Splits pages into overlapping chunks
├── embedder.py               # Embeds chunks → FAISS or Pinecone
├── hybrid_retriever.py       # BM25 + dense retrieval (RRF fusion)
├── reranker.py               # CrossEncoder re-ranking
├── generator.py              # LLM answer generation (sync + streaming)
├── pipeline.py               # Ties everything together into one RAG pipeline
├── api.py                    # FastAPI server (/health, /query, /query/sync)
├── app.py                    # Streamlit chat UI
├── build_index.py            # One-shot script: embed + index all PDFs
├── check_keys.py             # Validates your API keys from .env
│
├── data/                     # Drop your source PDF documents here
└── vector_store/             # FAISS index + chunks.pkl (auto-generated, gitignored)
```

---

## 🚀 Getting Started

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/Construction_RAG_Assistant.git
cd Construction_RAG_Assistant
pip install -r requirements.txt
```

### 2. Set Up Your Environment

```bash
cp .env.example .env
# Open .env and fill in your API keys if you want Mode 2,
# or leave the defaults as-is to run fully local with Mode 1
```

### 3. Build the Search Index

```bash
python build_index.py
```

### 4. Run the App

**Streamlit Chat UI:**
```bash
streamlit run app.py
```
Then open → **http://localhost:8501**

**FastAPI Server:**
```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
Then open → **http://localhost:8000/docs**

---

## 🔑 API Keys (for Mode 2 only)

Copy `.env.example` to `.env` and fill in these two keys:

```env
OPENAI_API_KEY=your-openai-api-key-here       # platform.openai.com/api-keys
PINECONE_API_KEY=your-pinecone-api-key-here   # app.pinecone.io → API Keys
```

> ⚠️ **Never commit your `.env` file.** It's already listed in `.gitignore`.  
> Only `.env.example` (with empty placeholders) gets tracked by git.

---

## 💰 Cost Breakdown

Running in Mode 1 costs you absolutely nothing. Mode 2 is still very cheap — here's what to expect:

| Item | Mode 1 (Local) | Mode 2 (Cloud) |
|---|---|---|
| Index build | $0.00 | ~$0.02 (one-time) |
| Per query — retrieval | $0.00 | $0.00 (Pinecone free tier) |
| Per query — LLM | $0.00 | ~$0.002 (GPT-3.5) |
| 100 demo queries | **$0.00** | **~$0.20** |

---

## 📚 Source Documents

The system was built and tested on the following construction safety and project management documents:

- OSHA Construction Safety Guide
- GTM Construction Safety Manual
- WSDOT Construction Manual
- TxDOT Bridge Inspection Manual
- Montana DOT Project Report

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Embedding (Local) | `sentence-transformers` / `all-MiniLM-L6-v2` |
| Embedding (Cloud) | OpenAI `text-embedding-3-small` |
| Vector Store (Local) | FAISS |
| Vector Store (Cloud) | Pinecone Serverless |
| Sparse Retrieval | BM25 (`rank_bm25`) |
| Re-ranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| LLM (Local) | `google/flan-t5-base` (HuggingFace) |
| LLM (Cloud) | OpenAI `gpt-3.5-turbo` |
| UI | Streamlit |
| API | FastAPI + Uvicorn |
| Config | `python-dotenv` |

---

## 📖 Need More Detail?

For full step-by-step instructions, mode switching, and API testing examples, check out **[RUN_GUIDE.md](./RUN_GUIDE.md)**.

---

*Construction Safety RAG Assistant — built as part of a graduate-level NLP/AI project, April 2026*
