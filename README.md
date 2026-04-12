# lightRAG-MCP (Windows Bare-Metal)

Local LightRAG setup for citation-aware academic writing with:
- LLM: DeepSeek (`deepseek-chat`)
- Embedding: SiliconFlow (`Qwen/Qwen3-Embedding-4B`)
- Storage: JSON + NanoVector + NetworkX (local default)

## Quick Start

1. Install runtime and dependencies:

```powershell
scripts\setup.bat
```

2. Create local config files:

```powershell
copy .env.example .env
copy .env.local.example .env.local
```

3. Put real API keys in `.env.local`:

```ini
LLM_BINDING_API_KEY=REVOKE_AND_REPLACE
EMBEDDING_BINDING_API_KEY=REVOKE_AND_REPLACE
```

Replace `REVOKE_AND_REPLACE` with your actual keys before starting the server.

4. Start LightRAG server:

```powershell
scripts\start-server.bat
```

5. Verify health:

```powershell
scripts\healthcheck.bat
```

## Ingest PDFs with APA Metadata

- PDF input folder: `data/inputs`
- Sidecar metadata folder: `data/metadata`
- Prepared text output: `data/inputs_prepared`

Prepare + upload:

```powershell
.venv\Scripts\python.exe scripts\ingest_pdfs.py --recursive --upload --server http://127.0.0.1:9621
```

Required metadata fields per sidecar JSON:
- `author`
- `title`
- `year`

## Install Writing Skill

Install the local skill for VS Code prompts and agent skills:

```powershell
scripts\install-skill.bat
```

Skill source:
- `skills/lightrag-academic-writing/SKILL.md`
- `skills/lightrag-academic-writing/pressure-scenarios.md`

## Security Notes

- Keep real keys only in `.env.local`.
- Do not commit `.env`, `.env.local`, `env`, or runtime data folders.
- Rotate any previously exposed API keys immediately.

## Detailed Guide

For the full setup and workflow notes, see `README-SETUP.md`.
