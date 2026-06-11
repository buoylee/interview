# Redis Architecture and Usage Patterns

Redis is an in-memory data structure store used as a cache, message broker, and primary database for use cases that require sub-millisecond latency. Its single-threaded command execution model eliminates lock contention and makes performance predictable, while its rich set of native data structures reduces the amount of logic needed in application code.

## Core Data Structures and Typical Uses

Redis provides several native data types, each optimized for specific access patterns.

Strings are the simplest type — a key maps to a byte sequence. Strings support atomic increment/decrement operations (INCR, INCRBY), making them a natural fit for counters, rate limiters, and distributed locks (via SET key value NX PX ttl).

Lists are ordered sequences of strings, implemented as linked lists (modern Redis uses quicklist — listpack nodes — for efficiency, and plain listpack for small lists). LPUSH/RPUSH add to either end; LPOP/RPOP remove from either end. Lists are commonly used as queues (producer pushes to RPUSH, consumer pops from LPOP) and for maintaining bounded activity logs with LTRIM.

Hashes map field-value pairs under a single key, similar to a struct. They are space-efficient when a key has many fields and are commonly used to store user profiles or session state where individual fields need to be updated independently.

Sets are unordered collections of unique strings. SADD, SISMEMBER, and set operations (SUNION, SINTER, SDIFF) make them useful for tracking unique visitors, tag systems, and computing relationships between groups.

Sorted Sets (ZSets) pair each member with a floating-point score and maintain members in score order. They power leaderboards, priority queues, and time-series indexes where range queries by score (ZRANGEBYSCORE) or rank (ZRANGE) are needed.

## Key Expiry Strategies

Redis uses two complementary strategies to reclaim memory from expired keys. Lazy expiration checks whether a key is expired only when the key is accessed. If it is expired, Redis deletes it and returns nil. This avoids scanning all keys but means expired keys consume memory until they are accessed.

Periodic expiration runs a background task at regular intervals that samples a random subset of keys with TTLs and deletes those that have expired. The task is time-bounded per cycle to avoid blocking the event loop. Together, lazy and periodic expiration ensure that expired keys are eventually reclaimed without requiring a full scan.

When memory pressure reaches the configured maxmemory limit, Redis applies an eviction policy (e.g., allkeys-lru, volatile-lru) to proactively remove keys. The choice of eviction policy should match the access pattern: allkeys-lru works well for a general cache; volatile-lru preserves keys without TTLs (which may be critical data) and only evicts those with TTLs.

## Persistence: RDB vs AOF

Redis supports two persistence mechanisms with different durability and recovery trade-offs.

RDB (Redis Database Backup) takes point-in-time snapshots of the dataset at configured intervals (e.g., every 5 minutes if at least 1000 keys changed). Redis forks a child process to write the snapshot, so the main process continues serving requests. RDB files are compact and fast to restore, making RDB suitable for disaster recovery and backups. The downside is data loss of up to the snapshot interval — any writes after the last snapshot are lost on crash.

AOF (Append-Only File) logs every write command as it is executed. On restart, Redis replays the log to reconstruct the dataset. AOF offers much finer durability: with appendfsync everysec, at most one second of writes can be lost. The trade-off is larger file size and slower restart times. AOF files are periodically compacted (BGREWRITEAOF) to remove redundant commands. Many production setups enable both RDB and AOF: AOF provides durability, and RDB provides fast restart fallback.

## Cache Consistency Patterns

Cache-aside (lazy loading) is the most common caching pattern. On a cache miss, the application fetches data from the database, populates the cache, and returns the result. Subsequent reads are served from cache until the TTL expires or the entry is invalidated.

When updating data, the recommended approach is to delete the cache entry rather than update it. Writing a new value to the cache risks a race condition: two concurrent writers can update the database in one order but write to the cache in a different order, leaving stale data. Deleting the entry forces the next read to rehydrate from the database, which is the authoritative source.

The double-delete pattern (delete before write, write to DB, delete again after write) attempts to close the window where a stale read could repopulate the cache between the two operations. Whether double-delete is necessary depends on whether reads can race between the two deletes — in practice, many teams find a single post-write delete sufficient when cache TTLs are short.

## Big-Key and Hot-Key Problems

A big key is a single Redis key whose value is very large — a list with millions of elements, a hash with thousands of fields, or a string value of many megabytes. Big keys cause latency spikes because Redis processes commands synchronously: scanning, deleting, or serializing a big key blocks the event loop for the duration. Mitigation strategies include splitting big structures into shards (e.g., hash by suffix), using UNLINK instead of DEL (UNLINK reclaims memory asynchronously), and using SCAN-based iteration instead of KEYS to avoid blocking scans.

A hot key is a single key receiving a disproportionately high request rate — common in viral content or popular session data. Hot keys saturate the single CPU thread handling that keyspace and can overwhelm a single Redis node even when overall cluster capacity is sufficient. Mitigations include local in-process caching (with a short TTL to bound staleness), replicating the hot key across multiple Redis nodes with a client-side random selection, and redesigning the data model to distribute the access across multiple keys.
