---
type: entity
tags: [database, graph]
sources: [graphrag-overview]
---

# Neo4j

A native **graph database**. Stores nodes, typed relationships, and properties,
with relationships as first-class objects on disk (index-free adjacency), so
multi-hop traversal is cheap.

## Why it suits GraphRAG
- Stores **vectors and the graph together**, so one query can do [[vector-search]]
  plus [[knowledge-graph]] traversal — the [[hybrid-retrieval]] pattern.
- The retrieved subgraph is the audit trail behind a [[graphrag]] answer.

## See also
[[knowledge-graph]] · [[graphrag]] · [[claude]]
