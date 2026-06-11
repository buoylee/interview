# PostgreSQL Internals and Extensions

PostgreSQL is a full-featured open-source relational database with strong ACID guarantees, extensibility through custom types and functions, and first-class support for both structured and unstructured data. Extensions like pgvector add vector similarity search, making Postgres a practical choice for AI-augmented applications.

## pgvector Index Types: HNSW vs IVFFlat

The pgvector extension supports two approximate nearest neighbor (ANN) index types: HNSW and IVFFlat. Choosing between them involves trade-offs in build time, query speed, recall, and memory.

HNSW (Hierarchical Navigable Small World) builds a multi-layer proximity graph at index creation time. Queries traverse the graph from coarse upper layers down to a dense base layer, achieving high recall with low latency. HNSW has higher build time and memory usage: the graph is built within maintenance_work_mem during index creation, and the index is larger on disk than IVFFlat. Query latency degrades when the index does not fit in RAM, because it is stored in normal Postgres pages read via the buffer cache. However, once the working set is cached, it delivers fast and consistent query latency. HNSW is the preferred choice when query latency and recall quality matter most and you can afford the upfront build cost.

IVFFlat (Inverted File with Flat storage) partitions vectors into a fixed number of clusters (lists) using k-means, then searches only the nearest clusters at query time. Build time is faster than HNSW and memory footprint is smaller, but recall degrades if the number of probed lists is too low. IVFFlat should be built after data is loaded, because k-means centroids derived from an empty or sparse table give poor recall; building earlier is allowed but not recommended.

For exact KNN search (exhaustive scan, no index), pgvector performs a sequential scan over all vectors. This is accurate but O(n) in cost — acceptable for small datasets or during development, but impractical at scale.

## MVCC and Locking

PostgreSQL implements Multi-Version Concurrency Control (MVCC) to allow readers and writers to operate concurrently without blocking each other. Each row update creates a new row version with a transaction ID stamp; old versions are visible to concurrent transactions that started before the update. Stale versions are reclaimed by the VACUUM process.

PostgreSQL uses row-level locking for DML operations. SELECT does not acquire row locks by default; SELECT FOR UPDATE acquires an exclusive lock on the returned rows, preventing concurrent updates. Table-level locks exist for DDL operations (e.g., ALTER TABLE acquires AccessExclusiveLock, which blocks all other access).

Deadlocks occur when two transactions each hold a lock the other needs. PostgreSQL detects deadlocks automatically and aborts one of the transactions with an error. Applications should retry aborted transactions and acquire locks in a consistent order to minimize deadlock frequency.

## Full-Text Search

PostgreSQL has built-in full-text search through the tsvector and tsquery types. A tsvector is a sorted list of normalized lexemes (stemmed words) derived from a document. A tsquery expresses a search condition using lexemes and boolean operators.

A GIN (Generalized Inverted Index) index on a tsvector column enables fast full-text lookups. The index maps each lexeme to the list of rows containing it, making keyword searches O(log n + k) rather than O(n). For frequently searched documents, storing a precomputed tsvector column and indexing it is more efficient than calling to_tsvector at query time.

PostgreSQL's built-in text search parsers handle Latin-alphabet languages well through stemming and stop-word removal. For CJK languages (Chinese, Japanese, Korean), words are not space-delimited, so the default parser produces poor segmentation. CJK full-text search requires an external tokenizer extension such as zhparser (for Chinese) or pg_bigm (bigram-based, language-agnostic). Without a proper tokenizer, CJK queries produce low recall.

## Connection Pooling with PgBouncer

PostgreSQL forks a new backend process for each client connection. Each process consumes roughly 5-10 MB of memory and has per-connection overhead in the query planner and lock tables. At high concurrency (hundreds of connections), this overhead degrades throughput significantly.

PgBouncer is a lightweight connection pooler that sits between the application and Postgres, multiplexing many client connections onto a smaller pool of server connections. It supports three pooling modes. Session mode assigns a server connection to a client for the duration of the client session — compatible with all Postgres features but offers limited multiplexing. Transaction mode reassigns the server connection after each transaction completes, enabling much higher multiplexing ratios. Statement mode reassigns after each statement, which breaks multi-statement transactions and is rarely used.

Transaction mode is the most common production choice. It is incompatible with prepared statements (unless you use protocol-level prepared statement tracking) and server-side cursors that span transactions. Applications must be aware of these constraints when moving to PgBouncer transaction mode.
