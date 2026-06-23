---
type: source
tags: [graphrag, retrieval]
---

# GraphRAG: An Overview

**One-line:** retrieval-augmented generation that uses graph structure, not just
nearest-neighbour text chunks.

## Key takeaways
- Flat RAG retrieves the top-k most similar chunks and stops. It cannot follow a
  chain of facts across documents.
- [[graphrag]] adds a traversal step: find entry points by similarity, then walk
  the [[knowledge-graph]] to gather connected context.
- The retrieved context is an explainable subgraph, not an opaque blob of text.

## Notable claims
- Multi-hop questions ("how does A relate to C, via B?") are where graph retrieval
  beats flat [[vector-search]] decisively.
