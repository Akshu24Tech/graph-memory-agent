---
type: concept
tags: [graphrag, retrieval, graph]
sources: [graphrag-overview]
---

# GraphRAG

RAG where retrieval uses **graph structure**, not just top-k chunks. It is
[[hybrid-retrieval]] applied to a [[knowledge-graph]] of extracted entities and
relationships.

## Why teams adopt it
- **Multi-hop reasoning** — chain facts across documents.
- **Explainability** — the answer ships with the subgraph that backs it, an audit
  trail flat [[vector-search]] cannot give.
- **Less hallucination** — answers are grounded in explicit, traceable facts.

## Where it runs
Commonly on [[neo4j]], which stores vectors and the graph together so a single
query does similarity + traversal. Tools like [[claude]] can drive it.

## See also
[[hybrid-retrieval]] · [[knowledge-graph]] · [[neo4j]]
