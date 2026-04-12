---
name: lightrag-academic-writing
description: Use when drafting, revising, or fact-checking academic text that must cite sources retrieved from a local LightRAG API.
---

# LightRAG Academic Writing

## Overview
Use LightRAG as a retrieval-first evidence layer before generating prose. The goal is to produce claims that are explicitly grounded in retrieved passages and mapped to citation metadata.

## When to Use
- You are writing academic sections that require verifiable references.
- You need citation-aware drafting from a local knowledge base.
- You must reduce hallucinated claims by forcing evidence retrieval first.

Do not use this skill for pure brainstorming where citations are not required.

## Required Inputs
- LightRAG server base URL (default: http://127.0.0.1:9621)
- Writing task and target section (for example: Literature Review)
- Citation style target (APA-like inline + references list)

## Retrieval Pattern
1. Query LightRAG first, then draft.
2. Prefer `mix` query mode when reranker is enabled.
3. Use `hybrid` mode if reranker is disabled.
4. Capture source references before writing final prose.

## API Flow
1. Health check: `GET /health`
2. Retrieve context: `POST /query/stream`
3. If structured evidence is needed: `POST /query/data`

If server auth is enabled, include `X-API-Key` in requests and fail fast when auth is missing.

Example retrieval body:
```json
{
  "query": "Summarize transformer fine-tuning methods for low-resource academic writing assistance",
  "mode": "hybrid"
}
```

## Drafting Rules
- Do not output strong factual claims without at least one retrieved source.
- Tie every paragraph to evidence notes gathered from retrieval.
- Prefer direct attribution language: "According to [Author, Year]..."
- If evidence is weak or missing, explicitly state uncertainty and ask for additional sources.

## Citation Rules
- Inline citation format: `(Author, Year)`.
- Include filename trace in evidence notes while drafting.
- Final references should include: author, year, title, venue/journal, DOI or URL, and filename when available.

## Prompt Template
Use this prompt shape when drafting:

```text
Task: Write a [section type] on [topic].
Constraints:
1) Retrieve evidence from LightRAG first.
2) Use only retrieved evidence for factual claims.
3) Add inline citations in (Author, Year).
4) End with a References section.
5) If evidence is missing, mark gaps clearly.
```

## Failure Handling
- If API retrieval fails: stop drafting and report the failed endpoint plus status.
- If retrieval is empty: request more documents or narrower query terms.
- If metadata lacks required citation fields: keep claim tentative and flag missing fields.
