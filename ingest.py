"""
Phase 1 — deterministic ingest.

Parse the Akshu Mind wiki (`pages/**/*.md`) into the graph:
  - one node per page  (:Page, plus a label from its type: Concept/Entity/Source)
  - one :LINKS_TO relationship per [[wikilink]] (citing page -> cited page)

No embeddings, no AI — pure parsing, so every number here is hand-checkable
against the files. Idempotent (MERGE), so re-running re-syncs without duplicates.

A [[wikilink]] whose target has no file is kept as a *stub* node (stub: true).
Those are the wiki's "gaps" — pages worth creating — and we want them visible
in the graph, not silently dropped.

Run:  python ingest.py
"""
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "akshumind123")

HERE = Path(__file__).resolve().parent


def wiki_roots() -> list[Path]:
    """Where to read markdown from.

    Set WIKI_DIR to point at any folder of interlinked `.md` notes (all `.md`
    under it are ingested) — this is the clone-and-run path; `.env.example`
    defaults it to the bundled ./sample-wiki.

    If WIKI_DIR is unset, fall back to the author's private "Akshu Mind" vault
    with curated roots (pages/ + real project folders; the Financial_v2
    graphify code-dump is excluded so it can't pollute the graph).
    """
    wiki_dir = os.getenv("WIKI_DIR")
    if wiki_dir:
        return [(HERE / wiki_dir).resolve() if not Path(wiki_dir).is_absolute()
                else Path(wiki_dir)]
    vault = HERE.parents[1] / "Akshu Mind"
    return [
        vault / "pages",
        vault / "projects" / "linkedin-feed-assistant",
        vault / "projects" / "graph-memory-agent",
    ]


WIKI_ROOTS = wiki_roots()

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
HEADING = re.compile(r"^#{1,6}\s+(.+)$")
TYPE_LABEL = {"concept": "Concept", "entity": "Entity", "source": "Source"}


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter, body). Frontmatter is '' if absent."""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", text
    body_start = text.find("\n", end + 1) + 1
    return text[3:end], text[body_start:]


def frontmatter_field(fm: str, key: str) -> str | None:
    for line in fm.splitlines():
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip()
    return None


def parse_page(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    slug = path.stem
    ptype = frontmatter_field(fm, "type") or path.parent.name.rstrip("s")  # folder fallback
    title_match = TITLE.search(text)
    title = title_match.group(1).strip() if title_match else slug

    # Edges, typed by where the [[link]] sits. Dedup on (target, rel).
    edges: dict[tuple[str, str], str] = {}  # (target, rel) -> via section

    def add(target: str, rel: str, via: str) -> None:
        target = target.split("|", 1)[0].strip()
        if target and target != slug:
            edges.setdefault((target, rel), via)

    # CITES from frontmatter `sources: [a, b]` — the provenance edge.
    raw_sources = frontmatter_field(fm, "sources")
    if raw_sources:
        for s in raw_sources.strip("[]").split(","):
            if s.strip():
                add(s.strip(), "CITES", "frontmatter:sources")

    # Walk the body line by line, tracking section + contradiction-callout context.
    # Per WIKI schema, contradictions use a `> [!warning] Contradiction` callout —
    # a plain `[!warning]` (e.g. "Unverified claim") is NOT a contradiction.
    section = ""
    in_contradiction = False
    for line in body.splitlines():
        h = HEADING.match(line)
        if h:
            section = h.group(1).strip()
        stripped = line.lstrip()
        low = stripped.lower()
        if stripped.startswith(">"):
            if "[!warning]" in low and "contradiction" in low:
                in_contradiction = True
        elif stripped != "":
            in_contradiction = False  # callout ends at first non-quote content line

        for raw in WIKILINK.findall(line):
            if in_contradiction:
                rel = "CONTRADICTS"
            elif "see also" in section.lower():
                rel = "SEE_ALSO"
            else:
                rel = "LINKS_TO"
            add(raw, rel, section or "body")

    return {
        "slug": slug,
        "type": ptype,
        "title": title,
        "text": body.strip(),
        "edges": [
            {"target": t, "rel": r, "via": via} for (t, r), via in edges.items()
        ],
    }


def main() -> None:
    files = sorted(
        f for root in WIKI_ROOTS if root.exists() for f in root.rglob("*.md")
    )
    pages = [parse_page(p) for p in files]
    real_slugs = {p["slug"] for p in pages}
    print(f"[parse] {len(pages)} page files across {len(WIKI_ROOTS)} curated roots")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()

    with driver.session() as session:
        # Uniqueness + lookup speed on slug.
        session.run(
            "CREATE CONSTRAINT page_slug IF NOT EXISTS "
            "FOR (p:Page) REQUIRE p.slug IS UNIQUE"
        )

        # Wipe prior ingest so counts reflect exactly the current wiki.
        session.run("MATCH (p:Page) DETACH DELETE p")

        # 1. Upsert real page nodes with their type label + body text.
        for p in pages:
            label = TYPE_LABEL.get(p["type"], "Page")
            session.run(
                f"MERGE (p:Page {{slug: $slug}}) "
                f"SET p:{label}, p.title = $title, p.type = $type, "
                f"p.text = $text, p.stub = false",
                slug=p["slug"], title=p["title"], type=p["type"], text=p["text"],
            )

        # 2. Create typed relationships; stub-create any missing targets.
        dangling = {}  # target slug -> count of inbound links
        for p in pages:
            for e in p["edges"]:
                target, rel, via = e["target"], e["rel"], e["via"]
                if target not in real_slugs:
                    dangling[target] = dangling.get(target, 0) + 1
                    session.run(
                        "MERGE (t:Page {slug: $t}) "
                        "ON CREATE SET t.stub = true, t.title = $t",
                        t=target,
                    )
                # rel type can't be parameterized — it's validated against our own set.
                assert rel in ("LINKS_TO", "SEE_ALSO", "CONTRADICTS", "CITES")
                session.run(
                    f"MATCH (a:Page {{slug: $a}}), (b:Page {{slug: $b}}) "
                    f"MERGE (a)-[r:{rel}]->(b) SET r.via = $via",
                    a=p["slug"], b=target, via=via,
                )

        # 3. Read counts back FROM the graph (ground truth, not our tallies).
        n_pages = session.run(
            "MATCH (p:Page) WHERE p.stub = false RETURN count(p) AS c"
        ).single()["c"]
        n_stubs = session.run(
            "MATCH (p:Page) WHERE p.stub = true RETURN count(p) AS c"
        ).single()["c"]
        n_rels = session.run(
            "MATCH ()-[r]->() RETURN count(r) AS c"
        ).single()["c"]
        by_type = session.run(
            "MATCH (p:Page) WHERE p.stub = false "
            "RETURN p.type AS type, count(p) AS c ORDER BY type"
        ).data()
        by_rel = session.run(
            "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS c ORDER BY c DESC"
        ).data()

    driver.close()

    print("\n[graph] (read back from Neo4j)")
    print(f"  real page nodes : {n_pages}")
    for row in by_type:
        print(f"      {row['type']:<10} {row['c']}")
    print(f"  stub nodes      : {n_stubs}  (wikilink targets with no file = wiki gaps)")
    print(f"  relationships   : {n_rels}")
    for row in by_rel:
        print(f"      {row['rel']:<12} {row['c']}")

    if dangling:
        print("\n[gaps] most-linked missing pages (top 10):")
        for slug, c in sorted(dangling.items(), key=lambda kv: -kv[1])[:10]:
            print(f"      {c:>3}x  [[{slug}]]")

    print(f"\n[done] Phase 1 ingest complete. Cross-check: {len(pages)} files parsed "
          f"-> {n_pages} nodes (should match).")


if __name__ == "__main__":
    main()
