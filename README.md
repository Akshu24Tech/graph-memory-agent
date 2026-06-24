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

> **Security note:** `docker-compose.yml` ships a local-dev password default for the
> Neo4j container. That's fine for a local-only graph, but set your own
> `NEO4J_PASSWORD` before exposing Neo4j to any network. The MCP tools are
> read-only (`run-cypher` rejects writes), so an agent can read the graph but not mutate it.

## Use it from Claude Code (MCP)

`.mcp.json` wires Google's [MCP Toolbox for Databases](https://mcp-toolbox.dev)
into Claude Code, so you can query the graph in plain language. Toolbox is
**tool-based, not LLM-generates-Cypher**: `tools.yaml` defines exactly what the
agent may run, so it can't hallucinate or mutate a query. This repo ships four:

| Tool | What it does |
|---|---|
| `graph-schema` | Dump labels, relationship types, property keys (call first). |
| `run-cypher` | Arbitrary **read-only** Cypher (writes rejected). |
| `page-neighbors` | Locked query: typed neighbors of a page slug. |
| `path-between` | Locked query: shortest chain between two slugs (the multi-hop bridge). |

Setup:

1. Download the Toolbox binary into this folder (it's gitignored, ~282MB):
   ```bash
   # Windows AMD64 — see mcp-toolbox.dev for macOS/Linux URLs
   curl -O https://storage.googleapis.com/mcp-toolbox-for-databases/v1.5.0/windows/amd64/toolbox.exe
   ```
2. Open this folder in Claude Code, approve the server when prompted, run `/mcp`
   to confirm it's connected.
3. Ask things like *"what pages contradict something?"*, *"what links into
   neo4j?"*, or *"find the path from neo4j to memory-governance."*

Swap `--config tools.yaml` for `--prebuilt neo4j` in `.mcp.json` if you'd rather
use Toolbox's built-in Neo4j toolset instead of these custom tools.

## Tech stack

Neo4j Community Edition · fastembed (ONNX, no torch) · Gemini (`google-genai`) ·
Google MCP Toolbox for Databases · Python + uv.

## Project layout

```
docker-compose.yml   local Neo4j
ingest.py            markdown -> typed graph
embed.py             embeddings + vector index
answer.py            GraphRAG retrieval + synthesis
sample-wiki/         7 interlinked demo pages (clone-and-run)
tools.yaml           MCP Toolbox source + 4 Neo4j tools
.mcp.json            launches MCP Toolbox (stdio) for Claude Code
```

## Notes & limits

- Tuning lives at the top of `answer.py`: `TOP_K` (entry nodes) and `HOPS`
  (traversal depth).
- The embedding model in `embed.py` and `answer.py` must match (both bge-small).
- Built local-first and single-instance — it's a retrieval/explainability demo,
  not a horizontally-scaled deployment.

## License

MIT — see [LICENSE](LICENSE).
