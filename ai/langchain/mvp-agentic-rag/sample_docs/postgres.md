# Postgres Index Tuning

Use HNSW indexes for approximate nearest neighbor search on pgvector
columns. For full-text search, a GIN index on a tsvector column gives
fast keyword lookup. Combine both for hybrid retrieval.
