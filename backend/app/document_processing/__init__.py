"""Document import pipeline: validation, storage, text extraction, metadata, chunking.

Everything here is pure processing with no database access, so it can be tested
in isolation and reused by background jobs later.
"""
