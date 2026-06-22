"""
Phase 0 spike: prove the engine + connection.

Connects to local Neo4j Community, writes one node + one relationship,
reads them back with Cypher, prints the result, then cleans up.
If this prints the expected line, the foundation is real and we can
build the ingest pipeline (Phase 1) on top of it.

Run:  python spike.py
"""
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "akshumind123")


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print(f"[ok] connected to {URI}")

    with driver.session() as session:
        # Clean slate for the spike's own nodes (idempotent re-runs).
        session.run("MATCH (n:SpikePage) DETACH DELETE n")

        # Write: two pages and one wikilink-style relationship between them.
        session.run(
            """
            CREATE (a:SpikePage {slug: 'neo4j', title: 'Neo4j'})
            CREATE (b:SpikePage {slug: 'graphrag', title: 'GraphRAG'})
            CREATE (a)-[:LINKS_TO {section: 'AI layer'}]->(b)
            """
        )

        # Read back the one-hop path — this is the whole point: traversal works.
        record = session.run(
            """
            MATCH (a:SpikePage {slug: 'neo4j'})-[r:LINKS_TO]->(b:SpikePage)
            RETURN a.title AS from, type(r) AS rel, r.section AS section, b.title AS to
            """
        ).single()

        print(
            f"[ok] traversed: ({record['from']}) "
            f"-[:{record['rel']} section='{record['section']}']-> "
            f"({record['to']})"
        )

        # Clean up so the spike leaves no residue before the real ingest.
        session.run("MATCH (n:SpikePage) DETACH DELETE n")
        print("[ok] cleaned up spike nodes")

    driver.close()
    print("[done] Phase 0 spike passed — engine + connection + traversal all work.")


if __name__ == "__main__":
    main()
