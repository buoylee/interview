# Elasticsearch Internals Interview Layer Design

## Context

The current Elasticsearch notes already form a systematic learning route:

```text
core concepts
-> mapping
-> analysis
-> query DSL
-> aggregations
-> storage internals
-> cluster architecture
-> performance tuning
-> data sync
-> production operations
```

The existing chapters are strong for learning. They explain the dependency chain from mapping and analysis to query behavior, then move into Lucene storage, shard routing, cluster reliability, tuning, synchronization, and production operations.

The remaining gap is not general content volume. The gap is interview output: a learner can read the chapters and understand the material, but still lack a compact way to answer layered interviewer follow-ups about Elasticsearch internals.

## Problem

Elasticsearch interviews often start with surface questions and then move into "why" questions:

- Why is Elasticsearch near real time?
- What happens between document write and search visibility?
- Why is deep pagination expensive?
- Why are aggregations memory-sensitive?
- Why can primary shard count not be changed casually?
- What should you check when search latency suddenly rises?

The current notes cover these topics across stages 2-10, but they are not yet organized as interview follow-up chains. This creates three practical risks:

1. **Answer shape risk**
   The learner may explain too much chapter detail instead of giving a concise answer first, then expanding based on follow-up depth.

2. **Follow-up risk**
   The learner may answer the first question but fail to connect it to the next layer: segment, translog, query phase, fetch phase, routing, shard recovery, or memory behavior.

3. **Production narrative risk**
   The learner may know the mechanism but not translate it into a troubleshooting or system-design answer.

## Goals

- Add a dedicated `elasticsearch/roadmap/11-interview/` layer.
- Preserve the existing 1-10 learning chapters as the source of truth.
- Convert internals knowledge into interview-ready answer chains.
- Help the learner answer at three depths:
  - one-sentence answer
  - core mechanism chain
  - interviewer follow-up and production scenario
- Cover enough internals for normal backend and senior backend interviews.
- Make deeper Lucene-source-level topics explicit as optional stretch material, not required baseline.

## Non-Goals

- Do not rewrite stages 1-10.
- Do not turn the interview layer into another full Elasticsearch textbook.
- Do not add large amounts of API reference material.
- Do not require Lucene source-code reading as the normal route.
- Do not optimize for search-engine infrastructure specialist interviews in the first pass.

## Recommended Structure

Create a new directory:

```text
elasticsearch/roadmap/11-interview/
```

Add six focused documents.

### `01-internals-question-map.md`

Purpose: give the learner a map of high-frequency internals questions.

Content:

- Question groups:
  - inverted index and analysis
  - write path
  - search path
  - storage structures
  - aggregation and memory
  - shard and cluster
  - performance troubleshooting
- Link each question group back to the source learning chapters.
- Mark each question as:
  - must know
  - good to know
  - deep follow-up

This document should answer: "Which ES internals questions do I need to prepare first?"

### `02-write-path-deep-dive.md`

Purpose: make write-path internals speakable in interviews.

Core chains:

- client request -> coordinating node -> primary shard -> replica shard
- document -> mapping -> analyzer -> inverted index terms
- index buffer -> refresh -> searchable segment
- translog -> durability -> flush -> Lucene commit
- segment immutability -> delete marker -> merge

Key questions:

- Why is Elasticsearch near real time?
- What is the difference between refresh, flush, and merge?
- What does translog protect?
- Why is update implemented as delete plus add?
- How do primary and replica writes coordinate?

### `03-search-path-deep-dive.md`

Purpose: make search execution explainable from query text to final hits.

Core chains:

- query text -> analyzer -> terms
- terms -> term dictionary -> posting list
- shard-level scoring -> BM25
- query phase -> top N doc IDs
- fetch phase -> `_source` load
- coordinating node -> merge shard results

Key questions:

- What happens when a `match` query executes?
- Why are `match` and `term` different?
- How does BM25 affect ranking?
- Why is deep pagination expensive?
- How do `search_after`, scroll, and PIT differ?

### `04-storage-structures.md`

Purpose: collect the storage structures that interviewers often use for deeper probing.

Core topics:

- inverted index
- term dictionary
- FST
- posting list
- skip data as optional stretch
- Doc Values
- Stored Fields and `_source`
- Fielddata and why it can cause heap pressure
- segment files as optional stretch

Key questions:

- What is an inverted index?
- How does Elasticsearch quickly find terms?
- Why are Doc Values useful for sorting and aggregations?
- Why should text fields avoid Fielddata?
- What does segment immutability buy, and what does it cost?

### `05-cluster-and-shard.md`

Purpose: prepare distributed-systems follow-ups.

Core chains:

- routing key -> hash -> primary shard
- primary shard -> replica replication
- master-eligible nodes -> voting configuration -> election
- cluster state -> shard allocation -> rebalance
- node failure -> replica promotion -> shard recovery

Key questions:

- How does ES route a document to a shard?
- Why can primary shard count not be changed directly?
- What is split brain and how does ES avoid it?
- What happens when a data node dies?
- Why can oversharding hurt performance?

### `06-production-troubleshooting.md`

Purpose: turn mechanism knowledge into production interview answers.

Scenario chains:

- search latency suddenly rises
- write throughput drops
- heap usage remains high
- aggregation OOM or circuit breaker trips
- cluster turns yellow or red
- segment count grows too high
- indexing delay or data sync lag appears

For each scenario, use:

```text
symptom
first checks
likely mechanisms
evidence to collect
fix options
how to verify
interview answer shape
```

This document should answer: "How do I sound like someone who can debug ES in production?"

## Answer Template

Each interview question should follow this format:

```text
一句话答案
核心链路
为什么这样设计
常见追问
生产场景怎么说
关联章节
```

This keeps answers concise while preserving depth.

## Learning Flow

The learner experience should become:

1. Study stages 1-5 for usage and modeling fundamentals.
2. Study stages 6-8 for core internals and tuning mechanisms.
3. Study stages 9-10 for system integration and production operations.
4. Use stage 11 to convert the learned material into interview answers.
5. Practice by starting with the one-sentence answer and expanding only when asked.

## Acceptance Criteria

After implementation, the ES notes should clearly answer:

- Can this route support systematic ES learning?
- Can the learner explain ES internals rather than only APIs?
- Can the learner handle common follow-up chains about write path, search path, storage, shards, and production issues?
- Can the learner distinguish baseline backend interview knowledge from optional Lucene-deep material?
- Can the learner quickly find the source chapter behind each interview answer?

## Risks And Controls

| Risk | Control |
| --- | --- |
| Stage 11 duplicates stages 1-10 | Keep stage 11 answer-shaped and link back to source chapters |
| The layer becomes too broad | Focus only on high-frequency internals and production follow-ups |
| Lucene depth becomes overwhelming | Mark source-level details as optional stretch material |
| Answers become memorized slogans | Require each answer to include mechanism chain and production scenario |

## Implementation Notes

- Start with `01-internals-question-map.md`, because it defines the boundaries.
- Then write path and search path should come next; these are the highest-value internals topics.
- Storage structures and cluster/shard can follow.
- Production troubleshooting should come last, because it composes earlier mechanisms.
- The top-level roadmap should link to the actual `11-interview` directory after the documents exist.
