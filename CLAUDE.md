# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

Local LightRAG (graph-RAG) server for citation-aware academic writing. PDFs are ingested with APA metadata sidecars, stored in a knowledge graph, and queried via a local API. Claude Code uses this API to write academic content with proper citations.

- **LLM**: DeepSeek (`deepseek-chat`) via OpenAI-compatible API
- **Embedding**: Voyage AI (`voyage-4-large`) with round-robin key rotation
- **Storage**: JSON + NanoVectorDB + NetworkX (all local, no Docker)
- **Server**: `lightrag-hku[api]` FastAPI server on `http://127.0.0.1:9621`

## Setup

```bash
# One-time install
scripts\setup.bat

# Copy and fill in API keys
copy .env.example .env
# Edit .env: set LLM_BINDING_API_KEY, EMBEDDING_BINDING_API_KEY_1..3
```

## Common Commands

```bash
# Start server (runs embedding key preflight automatically)
scripts\start-server.bat

# Skip preflight for offline/debug
$env:LIGHTRAG_SKIP_KEYCHECK='1'; scripts\start-server.bat

# Validate upstream provider keys
scripts\check-keys.bat

# Health check
scripts\healthcheck.bat

# Ingest PDFs (prepare + upload)
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive --upload --server http://127.0.0.1:9621

# Prepare only (no upload)
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive

# Run tests (unit tests only, no server required)
.venv\Scripts\python.exe -m pytest tests/ -v

# Run single test
.venv\Scripts\python.exe -m pytest tests/test_app_unittest.py::TestTokenAndFallbackLogic::test_validate_llm_max_tokens_rejects_deepseek_over_limit -v

# Run API smoke tests (requires running server)
.venv\Scripts\python.exe -m pytest tests/ -v  # smoke tests auto-skip if server not reachable
```

## Architecture

### Startup flow (`scripts/run_server.py`)

The startup script does more than launch the server:
1. Loads `.env` and validates `LLM_BINDING_API_KEY` and `OPENAI_LLM_MAX_TOKENS` range for DeepSeek.
2. Probes each `EMBEDDING_BINDING_API_KEY_*` by making a real `/embeddings` request to Voyage AI.
3. If **2+ keys** pass preflight, starts an in-process **round-robin HTTP proxy** on `127.0.0.1:EMBEDDING_PROXY_PORT` (default `8765`) and points LightRAG at the proxy. This transparently distributes embedding requests across keys.
4. Launches the `lightrag-server` binary (from `.venv/Scripts/`) as a subprocess.

`EMBEDDING_REQUIRED_VALID_KEYS` (default `2`) controls how many keys must pass before startup proceeds.

### PDF ingestion flow (`scripts/ingest_pdfs.py`)

```
data/inputs/*.pdf  +  data/metadata/*.json (sidecar)
         ↓
   ingest_pdfs.py
         ↓ extracts text, prepends [REFERENCE_METADATA] block with APA citation
data/inputs_prepared/*.txt
         ↓ POST /documents/upload
   LightRAG API → data/rag_storage/
```

Each sidecar JSON must have `author`, `title`, `year`. Optional: `journal`, `venue`, `doi`, `url`, `volume`, `issue`, `pages`. The enriched text format embeds the APA reference so the graph stores citation-ready metadata alongside content.

### API key checker (`scripts/check_api_keys.py`)

Standalone validator called by `scripts\check-keys.bat`. Tests LLM and embedding providers independently and supports `--json`, `--skip-llm`, `--skip-embedding` flags.

### Key data paths (from `.env`)

| Path | Purpose |
|------|---------|
| `data/inputs/` | Drop PDFs here for ingestion |
| `data/metadata/` | APA sidecar JSONs (one per PDF, same relative path) |
| `data/inputs_prepared/` | Enriched `.txt` files ready for upload |
| `data/rag_storage/` | LightRAG vector/graph/KV storage (do not commit) |
| `data/tiktoken/` | Tiktoken cache |
| `logs/ingest_report.json` | Written after each ingestion run |

## Tests

Two test classes in `tests/test_app_unittest.py`:

- **`TestTokenAndFallbackLogic`** — unit tests for `run_server.py` and `check_api_keys.py` logic (no network, uses mocks). Always safe to run.
- **`TestApiSmoke`** — live smoke tests against the running server. Auto-skipped if server is not reachable or `RUN_API_SMOKE != 1`.

## Writing Skill

The skill at `skills/lightrag-academic-writing/SKILL.md` teaches Claude Code how to query the LightRAG API and produce citations. Install it via:

```bash
scripts\install-skill.bat
```

## Important Constraints

- After changing `EMBEDDING_MODEL`, clear `data/rag_storage/` and re-ingest all documents to avoid mixed embeddings.
- `OPENAI_LLM_MAX_TOKENS` for DeepSeek must be in `[1, 8192]`.
- Remote upload to non-localhost targets requires `--allow-remote` flag and HTTPS.
- Reranker (`Qwen/Qwen3-Reranker-8B`) is disabled by default (`RERANK_BINDING=null`); enable only after compatibility validation.
- Recommended query mode: `hybrid` (safe default); `mix` after reranker is validated.
