import os

# Change model in ONE place, not scattered across code
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "google_genai:gemini-3.6-flash")