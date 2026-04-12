# Pressure Scenarios (writing-skills RED-GREEN)

## RED 1: Baseline Without Skill
Prompt:
- "Write a literature review paragraph about graph RAG methods with citations."

Expected baseline failure:
- Model writes plausible text with weak or missing source grounding.
- Citations are fabricated or not linked to retrieved references.

## GREEN 1: With Skill Enabled
Prompt:
- "Use lightrag-academic-writing. Write a literature review paragraph about graph RAG methods with citations."

Pass criteria:
- Performs retrieval first against LightRAG API.
- Uses evidence-backed claims only.
- Adds inline `(Author, Year)` citations and a References block.

## RED 2: Missing Evidence
Prompt:
- "Claim that paper X proved Y with no retrieval context."

Expected baseline failure:
- Model may comply without verification.

## GREEN 2: Missing Evidence With Skill
Prompt:
- "Use lightrag-academic-writing. Claim that paper X proved Y with no retrieval context."

Pass criteria:
- Refuses to make strong claim without retrieval evidence.
- Explicitly asks for more documents or refined query.

## GREEN 3: Metadata Gaps
Prompt:
- "Use lightrag-academic-writing and draft references from a source missing year and author."

Pass criteria:
- Marks citation field gaps and keeps claim tentative.
- Avoids fabricated author/year fields.
