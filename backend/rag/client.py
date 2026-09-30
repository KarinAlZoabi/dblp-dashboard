from __future__ import annotations

import os
from functools import lru_cache

from google import genai


@lru_cache(maxsize=1)
def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    # Reusing the client lets the SDK reuse underlying HTTP resources.
    return genai.Client(api_key=api_key)
