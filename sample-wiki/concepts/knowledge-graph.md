---
type: concept
tags: [graph, knowledge]
sources: [graphrag-overview]
---

# Knowledge graph

A network of **entities** (nodes) and **typed relationships** (edges). Unlike a
table, the relationships are first-class: "A *cites* B", "A *contradicts* B".

## Why it matters for retrieval
- A query can **traverse** edges to gather context that is connected but not
  textually similar — the multi-hop step flat [[vector-search]] cannot do.
- Stored in a graph database like [[neo4j]], traversal is cheap (index-free
  adjacency: each node points directly at its neighbours).

## See also
[[neo4j]] · [[hybrid-retrieval]]
