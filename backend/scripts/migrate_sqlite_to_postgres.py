#!/usr/bin/env python3
"""SQLite → Postgres 데이터 이전 스크립트

사용법:
  python3 migrate_sqlite_to_postgres.py \
      --sqlite-path /app/media_ax_dev.db \
      --pg-url postgresql://media_ax:media_ax@postgres:5432/media_ax \
      [--truncate] [--dry-run]

옵션:
  --truncate   이전 전 Postgres 테이블 모두 TRUNCATE (기존 데이터 삭제)
  --dry-run    실제 이전 없이 SQLite/Postgres row count 비교 보고만

설계 원칙:
  - session_replication_role='replica' 로 FK 일시 비활성화 → 순서 유연
  - JSON/JSONB 컬럼: %s::json cast, BOOLEAN: %s::boolean cast
  - SERIAL 시퀀스: 이전 후 MAX(id)+1 로 setval 재설정
  - 5,000 row 청크 단위 commit (대용량 TMDB cache 대응)
  - ON CONFLICT DO NOTHING (--truncate 없을 때 멱등 실행 가능)
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras

CHUNK = 5_000

# 삽입 순서 (부모→자식, FK 의존성 기준)
# session_replication_role='replica' 로 FK 비활성화하므로 순서 위반 시에도 안전
TABLE_ORDER = [
    "genre_codes",           # self-ref parent_id (무관, FK 비활성)
    "tag_codes",
    "person_master",         # self-ref canonical_id
    "cp_email_logs",         # contents.cp_email_id → cp_email_logs
    "metadata_candidates",   # field_suggestions, match_edges, seed_candidates → here
    "contents",              # self-ref parent_id
    "content_metadata",
    "content_ai_results",
    "content_credits",
    "content_genres",
    "content_tags",
    "content_images",
    "content_seeds",
    "content_audit_logs",
    "content_action_logs",
    "content_batch_jobs",
    "dam_events",
    "external_meta_sources",
    "external_sync_log",
    "field_resolutions",
    "field_suggestions",
    "match_edges",
    "seed_candidates",
    "seed_discovery_log",
    "content_distributions",
    "service_categories",
    "service_category_items",
    "device_variants",
    "tmdb_movie_cache",
    "tmdb_tv_cache",
    "tmdb_person_cache",
    "kmdb_movie_cache",
    "web_search_cache",
    "web_search_quota_log",
]

SKIP_TABLES = {"alembic_version"}


def _get_sqlite_tables(sq_conn: sqlite3.Connection) -> set:
    rows = sq_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {r[0] for r in rows}


def _get_pg_column_types(pg_cur, table: str) -> dict:
    """컬럼명 → Postgres data_type 매핑. JSON/JSONB/BOOLEAN 캐스팅에 사용."""
    pg_cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return {row[0]: row[1].lower() for row in pg_cur.fetchall()}


def _get_serial_columns(pg_cur, table: str) -> list:
    pg_cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_default LIKE 'nextval%%'
        """,
        (table,),
    )
    return [r[0] for r in pg_cur.fetchall()]


def _reset_sequences(pg_cur, pg_conn, table: str, serial_cols: list) -> None:
    for col in serial_cols:
        pg_cur.execute(f'SELECT MAX("{col}") FROM "{table}"')
        max_val = pg_cur.fetchone()[0]
        if max_val is not None:
            pg_cur.execute(
                "SELECT pg_get_serial_sequence(%s, %s)",
                (table, col),
            )
            seq = pg_cur.fetchone()[0]
            if seq:
                pg_cur.execute(f"SELECT setval('{seq}', %s, true)", (max_val,))
    pg_conn.commit()


def _build_template(columns: list, col_types: dict) -> str:
    """execute_values template — JSON/BOOLEAN 컬럼에 명시적 cast 적용."""
    parts = []
    for col in columns:
        t = col_types.get(col, "")
        if t in ("json", "jsonb"):
            parts.append("%s::json")
        elif t == "boolean":
            parts.append("%s::boolean")
        else:
            parts.append("%s")
    return f"({', '.join(parts)})"


def _migrate_table(
    sq_conn: sqlite3.Connection,
    pg_conn,
    pg_cur,
    table: str,
    dry_run: bool,
    verbose: bool = True,
) -> tuple[int, int]:
    """(sqlite_count, inserted_count) 반환."""
    sq_cur = sq_conn.cursor()
    sq_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    total = sq_cur.fetchone()[0]

    if total == 0:
        if verbose:
            print(f"  {table}: 0건 — 스킵")
        return 0, 0

    sq_cur.execute(f'SELECT * FROM "{table}" LIMIT 1')
    if not sq_cur.description:
        return total, 0
    columns = [d[0] for d in sq_cur.description]

    if dry_run:
        pg_cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        pg_count = pg_cur.fetchone()[0]
        print(f"  {table}: SQLite {total:>8,}건  |  PG {pg_count:>8,}건")
        return total, 0

    col_types = _get_pg_column_types(pg_cur, table)
    template = _build_template(columns, col_types)
    col_sql = ", ".join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO "{table}" ({col_sql}) VALUES %s ON CONFLICT DO NOTHING'

    inserted = 0
    offset = 0
    while True:
        sq_cur.execute(f'SELECT * FROM "{table}" LIMIT {CHUNK} OFFSET {offset}')
        rows = sq_cur.fetchall()
        if not rows:
            break
        psycopg2.extras.execute_values(
            pg_cur, insert_sql, rows, template=template, page_size=CHUNK
        )
        pg_conn.commit()
        inserted += len(rows)
        offset += CHUNK
        if verbose:
            print(f"  {table}: {inserted:,}/{total:,} ...", end="\r")

    serial_cols = _get_serial_columns(pg_cur, table)
    if serial_cols:
        _reset_sequences(pg_cur, pg_conn, table, serial_cols)

    if verbose:
        print(f"  {table}: {inserted:,}건 완료" + " " * 20)
    return total, inserted


def main() -> None:
    ap = argparse.ArgumentParser(description="SQLite → Postgres 데이터 이전")
    ap.add_argument("--sqlite-path", required=True, help="SQLite DB 파일 경로")
    ap.add_argument("--pg-url",      required=True, help="Postgres connection URL")
    ap.add_argument("--truncate",    action="store_true", help="이전 전 테이블 TRUNCATE")
    ap.add_argument("--dry-run",     action="store_true", help="row count 확인만")
    args = ap.parse_args()

    started = datetime.now()
    print(f"[{started:%H:%M:%S}] 시작")
    print(f"  SQLite : {args.sqlite_path}")
    host_part = args.pg_url.split("@")[-1] if "@" in args.pg_url else args.pg_url
    print(f"  PG     : {host_part}")
    print(f"  dry-run: {args.dry_run}  truncate: {args.truncate}")
    print()

    sq_conn = sqlite3.connect(args.sqlite_path)
    sq_tables = _get_sqlite_tables(sq_conn)

    pg_conn = psycopg2.connect(args.pg_url)
    pg_cur  = pg_conn.cursor()

    if not args.dry_run:
        # FK 제약 일시 비활성화
        pg_cur.execute("SET session_replication_role = 'replica'")
        pg_conn.commit()

        if args.truncate:
            print("  TRUNCATE 시작...")
            # Postgres는 FK로 인해 개별 TRUNCATE 불가 → 한 번에 처리
            pg_cur.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            pg_tables = {r[0] for r in pg_cur.fetchall()}
            targets = [
                f'"{t}"' for t in TABLE_ORDER
                if t not in SKIP_TABLES and t in pg_tables
            ]
            if targets:
                pg_cur.execute(f"TRUNCATE TABLE {', '.join(targets)}")
            pg_conn.commit()
            print("  TRUNCATE 완료\n")

    total_sq = total_pg = 0
    for table in TABLE_ORDER:
        if table in SKIP_TABLES:
            continue
        if table not in sq_tables:
            print(f"  {table}: SQLite에 없음 — 스킵")
            continue
        sq_n, pg_n = _migrate_table(sq_conn, pg_conn, pg_cur, table,
                                     dry_run=args.dry_run)
        total_sq += sq_n
        total_pg += pg_n

    if not args.dry_run:
        # FK 제약 복원
        pg_cur.execute("SET session_replication_role = 'origin'")
        pg_conn.commit()

    pg_conn.close()
    sq_conn.close()

    elapsed = (datetime.now() - started).total_seconds()
    if args.dry_run:
        print(f"\n[dry-run] SQLite 합계: {total_sq:,}건  |  경과: {elapsed:.1f}s")
    else:
        print(f"\n[완료] 이전: {total_pg:,}건  |  경과: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
