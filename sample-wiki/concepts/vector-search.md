---
type: concept
tags: [retrieval, embeddings]
sources: [graphrag-overview]
---

# Vector search

Find items by **semantic similarity**: embed text into vectors, then return the
nearest neighbours by cosine distance. No keyword overlap required — "long-term
agent memory" can match a page that never uses those words.

## Strengths
- Great at "find me things like this".
- Cheap, simple, well-understood.

## Limits
- It is single-hop. It returns similar chunks but cannot **connect** facts that
  live in different documents.
- That gap is exactly what [[hybrid-retrieval]] and [[graphrag]] close.

## See also
[[knowledge-graph]] · [[hybrid-retrieval]]
