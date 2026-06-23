# Graph-Memory Agent

**Turn a folder of interlinked markdown notes into a Neo4j knowledge graph, then
answer multi-hop questions with a _traceable cited subgraph_ — the explainability
flat vector RAG can't give you.**

Built on the free, local Neo4j Community Edition. No paid services required (the
optional answer-synthesis step uses the Gemini free tier).

---

## Why this exists

Flat vector RAG retrieves the top-k most *similar* chunks and stops. It can't
**connect** facts that live in different documents. This project adds the missing
step: find entry points by similarity, then **traverse the graph** to gather
connected context — and it returns the subgraph it used, so every answer is
auditable instead of an opaque blob.

```
question ─▶ embed ─▶ VECTOR search (entry nodes) ─▶ TRAVERSE typed graph
                                                          │
                          answer + cited subgraph ◀─ LLM synthesis
```

## Demo

A question whose answer requires chaining across pages:

```
$ uv run answer.py "Why can't plain vector search answer multi-hop questions, and what fixes it?"

ANSWER
Plain vector search cannot answer multi-hop questions because it is single-hop,
returning similar chunks but unable to connect facts across documents
[[vector-search]] [[graphrag-overview]]. This is fixed by [[hybrid-retrieval]]
and [[graphrag]] ... A graph database like [[neo4j]] can store vectors and the
graph together, facilitating this hybrid approach [[neo4j]].

CITED SUBGRAPH  (7 nodes, 43 edges) -- the audit trail
entry nodes (vector hits):
   [*] vector-search      sim=0.873
   [*] hybrid-retrieval   sim=0.885
   [*] graphrag           sim=0.851
pulled in by traversal:
   [ ] neo4j
   [ ] knowledge-graph        ◀── the multi-hop bridge a flat retriever misses
```

`knowledge-graph` and `neo4j` were **not** vector hits — graph traversal pulled
them in. That is the whole point.

## How it works

| Stage | Script | What it does |
|---|---|---|
| Graph build | `ingest.py` | Parse `.md` → page nodes + **typed** edges from `[[wikilinks]]`: `LINKS_TO`, `SEE_ALSO` (under a "See also" heading), `CITES` (frontmatter `sources:`), `CONTRADICTS` (inside a `[!warning] Contradiction` callout). Deterministic, idempotent. |
| Embeddings | `embed.py` | Embed each page locally (`BAAI/bge-small-en-v1.5` via fastembed/ONNX, 384-dim), build a cosine vector index. |
| Retrieval | `answer.py` | Embed question → vector entry nodes → traverse the typed graph → synthesize a grounded, cited answer + print the subgraph. |

## Quickstart

**Prerequisites:** [Docker](https://www.docker.com/), [uv](https://docs.astral.sh/uv/),
and (optional, for `answer.py`) a free [Gemini API key](https://aistudio.google.com/apikey).

```bash
# 1. clone, then start a local Neo4j
cp .env.example .env          # set NEO4J_PASSWORD + GOOGLE_API_KEY
docker compose up -d          # Neo4j Community at bolt://localhost:7687

# 2. build the graph from the bundled sample wiki (WIKI_DIR=./sample-wiki)
uv run ingest.py              # markdown -> nodes + typed edges
uv run embed.py               # embeddings + vector index

# 3. ask it anything
uv run answer.py "your multi-hop question here"
```

Point it at **your own** notes by setting `WIKI_DIR` in `.env` to any folder of
interlinked markdown (Obsidian vaults work great), then re-run `ingest.py` + `embed.py`.

## Use it from Claude Code (MCP)

`.mcp.json` wires the official [Neo4j MCP server](https://github.com/neo4j-contrib/mcp-neo4j)
into Claude Code, so you can query the graph in plain language (it issues Cypher
for you). Open this folder in Claude Code, approve the server when prompted, run
`/mcp` to confirm it's connected, then ask things like *"what pages contradict
something?"* or *"what links into neo4j?"*.

`UV_LINK_MODE=copy` is set in the config on purpose — some filesystems reject uv's
hardlinks; this makes the server install reliably everywhere.

## Tech stack

Neo4j Community Edition · fastembed (ONNX, no torch) · Gemini (`google-genai`) ·
Neo4j MCP server · Python + uv.

## Project layout

```
docker-compose.yml   local Neo4j
ingest.py            markdown -> typed graph
embed.py             embeddings + vector index
answer.py            GraphRAG retrieval + synthesis
sample-wiki/         7 interlinked demo pages (clone-and-run)
.mcp.json            Neo4j MCP server for Claude Code
```

## Notes & limits

- Tuning lives at the top of `answer.py`: `TOP_K` (entry nodes) and `HOPS`
  (traversal depth).
- The embedding model in `embed.py` and `answer.py` must match (both bge-small).
- Built local-first and single-instance — it's a retrieval/explainability demo,
  not a horizontally-scaled deployment.

## License

MIT — see [LICENSE](LICENSE).
