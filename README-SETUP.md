# LightRAG Bare-Metal Setup (Windows)

## 1) One-time setup

Run from project root:

```
scripts\setup.bat
```

This creates `.venv`, installs `lightrag-hku[api]`, and creates required folders.

Then create local environment files from templates:

```
copy .env.example .env
```

## 2) Security steps (required)

1. Rotate both previously exposed API keys in your provider dashboards.
2. Replace `REVOKE_AND_REPLACE` values in `.env` with new keys.
3. Treat `.env` as secret local runtime config (never commit/share it).
4. Keep `.env.example` as shareable template.

Project overview and quickstart are also available in `README.md`.

## 3) Start server

```
scripts\start-server.bat
```

The startup script runs provider key preflight automatically and stops if keys are invalid.

Run checker directly:

```
scripts\check-keys.bat
```

PowerShell bypass for offline/debug sessions:

```
$env:LIGHTRAG_SKIP_KEYCHECK='1'; scripts\start-server.bat
```

Health check:

```
scripts\healthcheck.bat
```

Default endpoint: `http://127.0.0.1:9621`

## 4) Prepare PDF metadata sidecars

For each PDF in `data/inputs`, create matching JSON in `data/metadata`.

Example mapping:
- `data/inputs/paper-a.pdf`
- `data/metadata/paper-a.json`

Required fields in JSON:
- `author`
- `title`
- `year`

By default, ingestion fails if the sidecar is missing or required fields are empty.

Optional fields:
- `journal`, `venue`, `publisher`, `doi`, `url`, `volume`, `issue`, `pages`, `filename`

## 5) Build metadata-enriched text and upload

Prepare only:

```
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive
```

Prepare + upload to LightRAG API:

```
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive --upload --server http://127.0.0.1:9621
```

Optional flags:
- Allow missing metadata (not recommended): `--allow-missing-metadata`
- Send auth header (avoid hardcoding literal keys in command history): `--api-key $env:LIGHTRAG_API_KEY`
- Allow non-localhost upload targets: `--allow-remote` (requires HTTPS for remote)
- File/page guardrails: `--max-pdf-size-bytes` and `--max-pages`

Output files are written to `data/inputs_prepared`.
A run report is written to `logs/ingest_report.json`.

## 6) Query from client tools (Claude/Copilot)

Use LightRAG server API at `http://127.0.0.1:9621`.

Suggested query mode after reranker is validated: `mix`.
Baseline mode (current safe default): `hybrid`.

## 7) Install the local writing skill

Install the project skill into your VS Code prompts folder and Codex skills folder:

```
scripts\install-skill.bat
```

Skill source in this repository:
- `skills/lightrag-academic-writing/SKILL.md`
- `skills/lightrag-academic-writing/pressure-scenarios.md`

## Notes on reranker

`Qwen/Qwen3-Reranker-8B` is documented in `.env` but disabled by default (`RERANK_BINDING=null`) to ensure stable startup.
Enable it only after confirming compatible endpoint behavior with LightRAG reranker bindings.

## Troubleshooting 401

If logs show `openai.AuthenticationError: Error code: 401 - Api key is invalid` during embedding:
- Update `EMBEDDING_BINDING_API_KEY_MAIN` and `EMBEDDING_BINDING_API_KEY_FALLBACK` in `.env` with valid Voyage API keys.
- `EMBEDDING_BINDING_API_KEY_FALLBACK` is optional and used only if main fails.
- Re-run `scripts\check-keys.bat` until embedding check passes.
- Restart with `scripts\start-server.bat`.

Voyage model choice:
- Default in this project is `voyage-4-large`.

After changing embedding model:
- Clear old vector data in `data/rag_storage` and re-ingest documents to avoid mixed embeddings.
