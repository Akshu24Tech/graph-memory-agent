---
type: concept
tags: [retrieval, graph, embeddings]
sources: [graphrag-overview]
---

# Hybrid retrieval

Combine **vector similarity** to find entry points with **graph traversal** to
expand context. The bridge between [[vector-search]] and the [[knowledge-graph]].

## The pipeline
1. Embed the question, find the nearest pages by [[vector-search]].
2. From those entry nodes, walk the [[knowledge-graph]] one or more hops.
3. Hand the resulting subgraph to a model to synthesize an answer.

This is the mechanism underneath [[graphrag]]. The payoff is multi-hop reasoning
plus a traceable subgraph you can audit.

> [!warning] Contradiction — "vectors alone are enough" overstated
> A common claim is that a good embedding model makes graph traversal unnecessary.
> The [[graphrag-overview]] source disputes this: single-hop similarity cannot
> connect facts across documents, no matter how good the embeddings.

## See also
[[graphrag]] · [[neo4j]]
