"""
Phase 3 — graph-grounded retrieval + answer (the payoff).

Pipeline (GraphRAG):
  1. embed the question (same model as ingest: bge-small-en-v1.5)
  2. VECTOR search -> top-k entry nodes (semantically closest pages)
  3. TRAVERSE the typed graph from those entries -> connected subgraph (the
     multi-hop context flat vector RAG misses)
  4. synthesize an answer with Gemini, grounded ONLY in that subgraph
  5. print the answer + the CITED SUBGRAPH (nodes + typed edges) as the audit
     trail — the thing a flat top-k vector store cannot show you

Run (under uv):  uv run answer.py "your question here"
Tunables:        TOP_K entry nodes, HOPS expansion depth.
"""
import os
import sys
import textwrap
import time

from dotenv import load_dotenv
from fastembed import TextEmbedding
from google import genai
from google.genai import errors as genai_errors
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "akshumind123")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # MUST match ingest/embed for valid cosine
INDEX = "page_embedding"
TOP_K = 5      # vector entry points
HOPS = 1       # graph expansion depth from each entry (1 = entry + neighbors)
MAX_NODES = 28 # cap context nodes to keep the prompt grounded + cheap
SNIPPET = 1100 # chars of body text per context page


def embed_query(text: str) -> list[float]:
    model = TextEmbedding(EMBED_MODEL)
    return [float(x) for x in next(iter(model.embed([text])))]


def retrieve(session, qvec: list[float]) -> tuple[list[dict], list[dict], list[str]]:
    """Return (context_nodes, edges, entry_slugs)."""
    # 2. Vector entry points.
    entries = session.run(
        f"CALL db.index.vector.queryNodes('{INDEX}', $k, $q) "
        f"YIELD node, score RETURN node.slug AS slug, score ORDER BY score DESC",
        k=TOP_K, q=qvec,
    ).data()
    entry_slugs = [e["slug"] for e in entries]
    score_by = {e["slug"]: e["score"] for e in entries}

    # 3. Expand HOPS hops over typed edges to gather connected context.
    frontier = set(entry_slugs)
    relevant = set(entry_slugs)
    for _ in range(HOPS):
        nbrs = session.run(
            "MATCH (a:Page)-[]-(b:Page) "
            "WHERE a.slug IN $f AND b.stub = false "
            "RETURN DISTINCT b.slug AS slug",
            f=list(frontier),
        ).data()
        new = {n["slug"] for n in nbrs} - relevant
        relevant |= new
        frontier = new
        if len(relevant) >= MAX_NODES:
            break

    # Prioritize entries, then cap.
    ordered = entry_slugs + [s for s in relevant if s not in entry_slugs]
    keep = ordered[:MAX_NODES]

    nodes = session.run(
        "MATCH (p:Page) WHERE p.slug IN $s "
        "RETURN p.slug AS slug, p.title AS title, p.type AS type, p.text AS text",
        s=keep,
    ).data()
    for n in nodes:
        n["score"] = score_by.get(n["slug"])
        n["is_entry"] = n["slug"] in entry_slugs

    # Edges among the kept set = the cited subgraph.
    edges = session.run(
        "MATCH (a:Page)-[r]->(b:Page) "
        "WHERE a.slug IN $s AND b.slug IN $s "
        "RETURN a.slug AS a, type(r) AS rel, b.slug AS b ORDER BY rel, a",
        s=keep,
    ).data()
    return nodes, edges, entry_slugs


def build_context(nodes: list[dict], edges: list[dict]) -> str:
    lines = ["## Wiki pages (context)\n"]
    for n in nodes:
        body = (n["text"] or "").strip().replace("\n", " ")
        if len(body) > SNIPPET:
            body = body[:SNIPPET] + " …"
        lines.append(f"### [[{n['slug']}]] ({n['type']})\n{body}\n")
    lines.append("\n## Relationships between these pages\n")
    for e in edges:
        lines.append(f"- {e['a']} --{e['rel']}--> {e['b']}")
    return "\n".join(lines)


def synthesize(question: str, context: str) -> str:
    client = genai.Client(api_key=GOOGLE_API_KEY)
    prompt = f"""You are a retrieval assistant answering from a personal knowledge wiki.
Answer the QUESTION using ONLY the CONTEXT below (pages + their relationships).
Rules:
- Ground every claim in the pages. Cite page slugs inline like [[slug]].
- Use the relationships to connect facts across pages (multi-hop reasoning).
- If the context does not contain the answer, say so plainly. Do not invent.
- Be concise. Short sentences. No preamble.

QUESTION: {question}

CONTEXT:
{context}
"""
    # Gemini Flash can 503 under demand spikes — retry, then fall back.
    candidates = [GEMINI_MODEL, "gemini-2.0-flash", "gemini-flash-latest"]
    seen, models = set(), []
    for m in candidates:
        if m not in seen:
            seen.add(m)
            models.append(m)
    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                if model != GEMINI_MODEL:
                    print(f"[note] answered with fallback model {model}")
                return resp.text.strip()
            except genai_errors.ServerError as e:
                last_err = e
                time.sleep(2 * (attempt + 1))  # 2s, 4s, 6s backoff
    raise last_err


def main() -> None:
    if len(sys.argv) < 2:
        print('usage: uv run answer.py "your question"')
        sys.exit(1)
    question = " ".join(sys.argv[1:])
    if not GOOGLE_API_KEY:
        print("[error] GOOGLE_API_KEY not set in environment.")
        sys.exit(1)

    print(f"[q] {question}\n[embed] {EMBED_MODEL}  [model] {GEMINI_MODEL}  "
          f"[top_k] {TOP_K}  [hops] {HOPS}\n")

    qvec = embed_query(question)
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    with driver.session() as session:
        nodes, edges, entries = retrieve(session, qvec)
    driver.close()

    context = build_context(nodes, edges)
    answer = synthesize(question, context)

    print("=" * 70)
    print("ANSWER\n")
    print(textwrap.fill(answer, width=78, replace_whitespace=False))
    print("\n" + "=" * 70)
    print(f"CITED SUBGRAPH  ({len(nodes)} nodes, {len(edges)} edges) -- the audit trail\n")
    print("entry nodes (vector hits):")
    for n in nodes:
        if n["is_entry"]:
            print(f"   [*] {n['slug']:<34} sim={n['score']:.3f}")
    print("pulled in by traversal:")
    for n in nodes:
        if not n["is_entry"]:
            print(f"   [ ] {n['slug']}")
    print("\nedges used:")
    for e in edges:
        print(f"   {e['a']} --{e['rel']}--> {e['b']}")


if __name__ == "__main__":
    main()
