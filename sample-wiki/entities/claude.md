---
type: entity
tags: [llm, agent]
---

# Claude

An LLM by Anthropic, used here as the optional synthesis layer: given a retrieved
subgraph from [[neo4j]], it writes the grounded, cited answer.

## Role in this project
- Reads the [[hybrid-retrieval]] context (pages + relationships).
- Performs the multi-hop reasoning the [[knowledge-graph]] makes possible.
- Cites the pages it used, so the answer traces back to the [[graphrag]] subgraph.

(This sample is model-agnostic — any capable LLM can fill this slot.)

## See also
[[graphrag]] · [[neo4j]]
