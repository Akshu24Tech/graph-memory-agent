"""
Phase 2 (part B) — node embeddings + vector index.

Embeds each real page (title + body) with a local, free model
(BAAI/bge-small-en-v1.5, 384 dims) via fastembed (ONNX runtime, no torch —
avoids the heavy/fragile torch stack and keeps the repo light to clone-and-run).
Stores the vector on the node and builds a cosine vector index. Kept separate
from ingest.py (Lego principle): rebuild the graph without re-embedding.

First run downloads the ONNX model (~130MB), then it's cached.

Run:  python embed.py
"""
import os

from dotenv import load_dotenv
from fastembed import TextEmbedding
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "akshumind123")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMS = 384
INDEX = "page_embedding"


def embed_texts(model: TextEmbedding, texts: list[str]) -> list[list[float]]:
    return [[float(x) for x in v] for v in model.embed(texts)]


def main() -> None:
    print(f"[model] loading {MODEL_NAME} (fastembed/ONNX) ...")
    model = TextEmbedding(MODEL_NAME)

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()

    with driver.session() as session:
        # Pull real pages (skip stub gap-nodes — they have no text to embed).
        rows = session.run(
            "MATCH (p:Page) WHERE p.stub = false "
            "RETURN p.slug AS slug, p.title AS title, p.text AS text"
        ).data()
        print(f"[embed] embedding {len(rows)} pages ...")

        # Embed title + body together; the model truncates long text safely.
        texts = [f"{r['title']}\n\n{r['text'] or ''}" for r in rows]
        vectors = embed_texts(model, texts)

        for r, vec in zip(rows, vectors):
            session.run(
                "MATCH (p:Page {slug: $slug}) "
                "CALL db.create.setNodeVectorProperty(p, 'embedding', $vec)",
                slug=r["slug"], vec=vec,
            )

        # Cosine vector index over the embeddings.
        session.run(
            f"CREATE VECTOR INDEX {INDEX} IF NOT EXISTS "
            f"FOR (p:Page) ON (p.embedding) "
            f"OPTIONS {{indexConfig: {{"
            f"`vector.dimensions`: {DIMS}, "
            f"`vector.similarity_function`: 'cosine'}}}}"
        )
        # Wait until the index is online before querying it.
        session.run("CALL db.awaitIndex($name, 60)", name=INDEX)

        n_emb = session.run(
            "MATCH (p:Page) WHERE p.embedding IS NOT NULL RETURN count(p) AS c"
        ).single()["c"]
        print(f"[ok] {n_emb} nodes carry a {DIMS}-dim embedding; index '{INDEX}' online")

        # Validation: a semantic query that does NOT keyword-match the target.
        probe = "storing an AI agent's long-term memory in a graph"
        qvec = embed_texts(model, [probe])[0]
        print(f"\n[validate] nearest pages to: \"{probe}\"")
        hits = session.run(
            f"CALL db.index.vector.queryNodes('{INDEX}', 5, $q) "
            f"YIELD node, score RETURN node.slug AS slug, score ORDER BY score DESC",
            q=qvec,
        ).data()
        for h in hits:
            print(f"      {h['score']:.3f}  {h['slug']}")

    driver.close()
    print("\n[done] Phase 2 part B complete — embeddings + vector index ready for retrieval.")


if __name__ == "__main__":
    main()
