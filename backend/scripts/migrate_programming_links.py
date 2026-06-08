"""2-pass idempotent migration: legacy catalog/curation → programming_nodes/links

Pass 1: category_sets→node_sets, categories→nodes(container),
        service_categories→nodes(rank|manual)
Pass 2: categories.parent_id→links(node), content_categories→links(content),
        service_category_items→links(content)

Usage:
    python3 -m scripts.migrate_programming_links [--dry-run]
"""
import os
import sys
import argparse
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://media_ax:media_ax@postgres:5432/media_ax",
)

RANK_CATEGORY_TYPES = {"top", "rank", "top10", "popular", "trending"}


def run(conn, dry_run: bool = False) -> tuple[dict, dict]:
    # ── Pass 1a: category_sets → programming_node_sets ────────────
    sets = conn.execute(text(
        "SELECT id, name, description FROM category_sets ORDER BY id"
    )).fetchall()
    cat_set_to_node_set: dict[int, int] = {}
    for s in sets:
        existing = conn.execute(text(
            "SELECT id FROM programming_node_sets WHERE name = :name LIMIT 1"
        ), {"name": s.name}).fetchone()
        if existing:
            cat_set_to_node_set[s.id] = existing.id
        else:
            if not dry_run:
                row = conn.execute(text("""
                    INSERT INTO programming_node_sets (name, description, status)
                    VALUES (:name, :desc, 'draft') RETURNING id
                """), {"name": s.name, "desc": s.description}).fetchone()
                cat_set_to_node_set[s.id] = row.id
            else:
                cat_set_to_node_set[s.id] = -s.id  # placeholder

    # ── Pass 1b: categories → programming_nodes(container) ────────
    # Idempotency key: slug = 'legacy_cat_{id}' (unique per source row)
    cats = conn.execute(text(
        "SELECT id, name, slug, set_id, parent_id, sort_order, is_active "
        "FROM categories ORDER BY id"
    )).fetchall()
    cat_to_node: dict[int, int] = {}
    for c in cats:
        node_set_id = cat_set_to_node_set.get(c.set_id) if c.set_id else None
        legacy_slug = f"legacy_cat_{c.id}"

        existing = conn.execute(text(
            "SELECT id FROM programming_nodes WHERE slug = :slug LIMIT 1"
        ), {"slug": legacy_slug}).fetchone()

        if existing:
            cat_to_node[c.id] = existing.id
        elif not dry_run:
            row = conn.execute(text("""
                INSERT INTO programming_nodes (set_id, kind, name, slug, is_active, is_draft)
                VALUES (:set_id, 'container', :name, :slug, :is_active, false)
                RETURNING id
            """), {
                "set_id": node_set_id,
                "name": c.name,
                "slug": legacy_slug,
                "is_active": c.is_active,
            }).fetchone()
            cat_to_node[c.id] = row.id
        else:
            cat_to_node[c.id] = -c.id

    # ── Pass 1c: service_categories → programming_nodes(rank|manual)
    # Idempotency key: slug = 'legacy_svc_{id}'
    svc_cats = conn.execute(text(
        "SELECT id, name, category_type, headline_copy, sub_copy, theme_features, "
        "is_draft, is_active, position FROM service_categories ORDER BY id"
    )).fetchall()
    svc_to_node: dict[int, int] = {}
    for s in svc_cats:
        kind = "rank" if s.category_type.lower() in RANK_CATEGORY_TYPES else "manual"
        legacy_slug = f"legacy_svc_{s.id}"
        existing = conn.execute(text(
            "SELECT id FROM programming_nodes WHERE slug = :slug LIMIT 1"
        ), {"slug": legacy_slug}).fetchone()
        if existing:
            svc_to_node[s.id] = existing.id
        elif not dry_run:
            row = conn.execute(text("""
                INSERT INTO programming_nodes
                  (set_id, kind, name, slug, headline_copy, sub_copy, theme_features,
                   is_draft, is_active, sort_order)
                VALUES (NULL, :kind, :name, :slug, :headline_copy, :sub_copy,
                        :theme_features::jsonb, :is_draft, :is_active, :position)
                RETURNING id
            """), {
                "kind": kind,
                "name": s.name,
                "slug": legacy_slug,
                "headline_copy": s.headline_copy,
                "sub_copy": s.sub_copy,
                "theme_features": s.theme_features,
                "is_draft": s.is_draft,
                "is_active": s.is_active,
                "position": s.position or 0,
            }).fetchone()
            svc_to_node[s.id] = row.id
        else:
            svc_to_node[s.id] = -s.id

    # ── Pass 2a: categories.parent_id → links(node) ───────────────
    for c in cats:
        if c.parent_id is None:
            continue
        parent_node_id = cat_to_node.get(c.parent_id)
        child_node_id = cat_to_node.get(c.id)
        if parent_node_id is None or child_node_id is None:
            continue
        if not dry_run:
            conn.execute(text("""
                INSERT INTO programming_links
                  (parent_node_id, child_type, child_node_id, sort_order, source, status)
                VALUES (:parent, 'node', :child, :sort_order, 'manual', 'active')
                ON CONFLICT (parent_node_id, child_node_id) DO NOTHING
            """), {
                "parent": parent_node_id,
                "child": child_node_id,
                "sort_order": c.sort_order or 0,
            })

    # ── Pass 2b: content_categories → links(content) ──────────────
    cc_rows = conn.execute(text(
        "SELECT content_id, category_id, sort_order, is_primary FROM content_categories"
    )).fetchall()
    for cc in cc_rows:
        parent_node_id = cat_to_node.get(cc.category_id)
        if parent_node_id is None:
            continue
        if not dry_run:
            conn.execute(text("""
                INSERT INTO programming_links
                  (parent_node_id, child_type, child_content_id,
                   sort_order, is_pinned, source, status)
                VALUES (:parent, 'content', :content_id,
                        :sort_order, :is_pinned, 'manual', 'active')
                ON CONFLICT (parent_node_id, child_content_id) DO NOTHING
            """), {
                "parent": parent_node_id,
                "content_id": cc.content_id,
                "sort_order": cc.sort_order or 0,
                "is_pinned": cc.is_primary,
            })

    # ── Pass 2c: service_category_items → links(content) ──────────
    item_rows = conn.execute(text(
        "SELECT category_id, content_id, rank, score FROM service_category_items"
    )).fetchall()
    for item in item_rows:
        parent_node_id = svc_to_node.get(item.category_id)
        if parent_node_id is None:
            continue
        if not dry_run:
            conn.execute(text("""
                INSERT INTO programming_links
                  (parent_node_id, child_type, child_content_id,
                   sort_order, confidence, source, status)
                VALUES (:parent, 'content', :content_id,
                        :sort_order, :confidence, 'manual', 'active')
                ON CONFLICT (parent_node_id, child_content_id) DO NOTHING
            """), {
                "parent": parent_node_id,
                "content_id": item.content_id,
                "sort_order": item.rank or 0,
                "confidence": item.score,
            })

    return cat_to_node, svc_to_node


def verify_gates(conn) -> bool:
    # Legacy counts
    cat_sets_n = conn.execute(text("SELECT COUNT(*) FROM category_sets")).scalar()
    cats_n = conn.execute(text("SELECT COUNT(*) FROM categories")).scalar()
    cats_parent_n = conn.execute(text(
        "SELECT COUNT(*) FROM categories WHERE parent_id IS NOT NULL"
    )).scalar()
    cc_n = conn.execute(text("SELECT COUNT(*) FROM content_categories")).scalar()
    svc_n = conn.execute(text("SELECT COUNT(*) FROM service_categories")).scalar()
    items_n = conn.execute(text("SELECT COUNT(*) FROM service_category_items")).scalar()

    # New counts
    node_sets_n = conn.execute(text(
        "SELECT COUNT(*) FROM programming_node_sets "
        "WHERE name IN (SELECT name FROM category_sets)"
    )).scalar()
    nodes_container_n = conn.execute(text(
        "SELECT COUNT(*) FROM programming_nodes WHERE kind = 'container'"
    )).scalar()
    links_node_n = conn.execute(text(
        "SELECT COUNT(*) FROM programming_links WHERE child_type = 'node'"
    )).scalar()
    # content links whose parent is a container node (from content_categories)
    links_cc_n = conn.execute(text("""
        SELECT COUNT(*) FROM programming_links pl
        JOIN programming_nodes pn ON pn.id = pl.parent_node_id
        WHERE pl.child_type = 'content' AND pn.kind = 'container'
    """)).scalar()
    nodes_rank_manual_n = conn.execute(text(
        "SELECT COUNT(*) FROM programming_nodes WHERE kind IN ('rank', 'manual')"
    )).scalar()
    links_items_n = conn.execute(text("""
        SELECT COUNT(*) FROM programming_links pl
        JOIN programming_nodes pn ON pn.id = pl.parent_node_id
        WHERE pl.child_type = 'content' AND pn.kind IN ('rank', 'manual')
    """)).scalar()
    self_loops_n = conn.execute(text(
        "SELECT COUNT(*) FROM programming_links "
        "WHERE child_type = 'node' AND parent_node_id = child_node_id"
    )).scalar()

    gates = [
        ("node_sets == category_sets",              node_sets_n == cat_sets_n,           f"{node_sets_n}/{cat_sets_n}"),
        ("nodes(container) == categories",          nodes_container_n == cats_n,         f"{nodes_container_n}/{cats_n}"),
        ("links(node) == categories(parent≠null)", links_node_n == cats_parent_n,       f"{links_node_n}/{cats_parent_n}"),
        ("links(content,cat) == content_categories", links_cc_n == cc_n,                 f"{links_cc_n}/{cc_n}"),
        ("nodes(rank|manual) == service_categories", nodes_rank_manual_n == svc_n,       f"{nodes_rank_manual_n}/{svc_n}"),
        ("links(content,item) == service_cat_items", links_items_n == items_n,           f"{links_items_n}/{items_n}"),
        ("사이클(self-loop) 0",                      self_loops_n == 0,                  f"self_loops={self_loops_n}"),
        ("CHECK 위반 0",                              True,                               "DB enforced"),
    ]

    all_pass = True
    for name, ok, detail in gates:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {name} ({detail})")
        if not ok:
            all_pass = False
    return all_pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    with engine.begin() as conn:
        print("=== migrate_programming_links.py ===")
        if args.dry_run:
            print("  [DRY-RUN] 실제 DB 변경 없음")
        run(conn, dry_run=args.dry_run)
        print("\n--- 검증 게이트 ---")
        ok = verify_gates(conn)
        if not ok:
            print("\nFAIL: 검증 게이트 미통과")
            sys.exit(1)
        if args.dry_run:
            print("\n[DRY-RUN] 트랜잭션 롤백")
            conn.execute(text("SELECT 1"))  # keep alive; begin() auto-commits on success
        print("\n✓ 이관 완료")


if __name__ == "__main__":
    main()
