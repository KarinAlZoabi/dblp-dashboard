DBLP hardening patch
====================

Fixes the failure clusters revealed by the 52-query adversarial suite:

- topic queries like "Find federated learning papers from 2020 to 2023"
  no longer get mistaken for exact paper titles
- weird author wording such as "put out in 2020"
- dataset-count and possessive author-count paraphrases are routed locally
- page-count with hyphen punctuation and "what are the pages" wording
- top-N topic result limits
- latest/oldest author publication ordering
- explicit venue filters (e.g. CoRR)
- explicit conference/journal publication-type filters
- years such as 1800 are parsed as filters instead of title text
- typo-tolerant exact-title lookup
- conservative typo-tolerant author-name resolution
- publication-not-found wording is consistent with regression tests
- simple discovery wording such as "I'm looking for work on..." avoids an
  unnecessary answer-generation LLM call

Files to replace:
  backend/rag/parsing.py
  backend/rag/planner.py
  backend/rag/conversation.py
  backend/rag/retrieval.py
  backend/rag/service.py
  backend/rag/response_renderer.py

No index rebuild is required.

After replacing the files:
  1. restart Uvicorn
  2. run your original evaluate_rag_v2.py
  3. run your original evaluate_context_planner_v2.py
  4. run your original evaluate_rag_hardening.py
  5. run evaluate_hardening_fixes.py from this patch
