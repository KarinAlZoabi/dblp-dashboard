DBLP CONTEXT-AWARE PLANNER PATCH
================================

Purpose
-------
Stop manually teaching every conversational phrase.

The architecture is now:

    user message
        |
        v
    fast local planner
        |
        +-- obvious standalone question --> structured plan immediately
        |
        +-- unclear / conversational follow-up
                |
                v
          Gemini query planner
          + compact VERIFIED session context
                |
                v
          structured JSON plan only
                |
                v
          Python/SQLite DBLP tools
                |
                v
          conversational renderer

Gemini's job remains intentionally minimal:
- resolve natural language
- resolve conversational references
- classify intent
- extract filters/entities

Gemini does NOT:
- count publications
- choose DBLP facts
- calculate page counts
- compute coauthors
- search the database
- invent authors/venues/pages
- decide factual answers

Python/SQLite still does all factual work.

Changed files
-------------
backend/rag/planner.py
backend/rag/conversation.py
backend/rag/service.py

Also included:
evaluate_context_planner.py

No frontend change is required if session_id reuse is already working.
No database rebuild is required.

Testing
-------
1. Restart Uvicorn.
2. Re-run your existing regression suite:

    python evaluate_rag_v2.py

3. Then run:

    python evaluate_context_planner.py

Expected behavior includes:
- "Where did it appear?" resolving the previous paper
- "and how long is it?" resolving the previous paper
- "Who wrote the second result?" resolving previous search result #2
- "Tell me about the newest one instead" selecting by year in Python
- "and in 2023?" inheriting the previous author/intent
- "how many did they have that year?" inheriting author + previous year
- topic refinement such as "what about privacy?"

The old small regex follow-up layer remains only as an emergency fallback if
the remote planner is unavailable.
