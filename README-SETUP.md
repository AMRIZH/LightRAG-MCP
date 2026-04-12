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
copy .env.local.example .env.local
```

## 2) Security steps (required)

1. Rotate both previously exposed API keys in your provider dashboards.
2. Replace `REVOKE_AND_REPLACE` values in `.env.local` with new keys.
3. Keep `.env` as non-secret runtime config.
4. Keep `.env.example` and `.env.local.example` as shareable templates.

Project overview and quickstart are also available in `README.md`.

## 3) Start server

```
scripts\start-server.bat
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
- Send auth header: `--api-key YOUR_LIGHTRAG_API_KEY`
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
