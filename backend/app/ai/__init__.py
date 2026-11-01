"""AI provider abstraction.

Phase 1 implements provider *status detection* only (is Ollama running, which
models are installed, is a Claude key configured). Text generation and
embeddings are added to these providers in Phase 3 together with the RAG
pipeline; nothing in the UI claims those capabilities before then.
"""
