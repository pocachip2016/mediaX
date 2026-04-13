"""extend content base — 장르/태그/인물/이미지/외부메타/AI결과 테이블 추가

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-12

변경 내용:
  - contents.content_type ENUM에 'season' 추가
  - 신규 테이블 9개: genre_codes, tag_codes, content_genres, content_tags,
      person_master, content_credits, content_images,
      external_meta_sources, content_ai_results
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── contents.content_type에 'season' 추가 ─────────────────
    if dialect == "postgresql":
        op.execute("ALTER TYPE contenttype ADD VALUE IF NOT EXISTS 'season'")
    # SQLite는 ENUM이 String으로 저장되므로 별도 처리 불필요

    # ── genre_codes ───────────────────────────────────────────
    op.create_table(
        "genre_codes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("name_ko", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("genre_codes.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), default=0),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── tag_codes ─────────────────────────────────────────────
    op.create_table(
        "tag_codes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tag_type", sa.String(20), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("created_by", sa.String(20), default="manual"),
        sa.Column("use_count", sa.Integer(), default=0),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── content_genres ────────────────────────────────────────
    op.create_table(
        "content_genres",
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("genre_id", sa.Integer(), sa.ForeignKey("genre_codes.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), default=False),
        sa.Column("source", sa.String(20), default="ai"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
        sa.PrimaryKeyConstraint("content_id", "genre_id"),
    )

    # ── content_tags ──────────────────────────────────────────
    op.create_table(
        "content_tags",
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tag_codes.id"), nullable=False),
        sa.Column("source", sa.String(20), default="ai"),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
        sa.PrimaryKeyConstraint("content_id", "tag_id"),
    )

    # ── person_master ─────────────────────────────────────────
    op.create_table(
        "person_master",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name_ko", sa.String(200), nullable=False, index=True),
        sa.Column("name_en", sa.String(200), nullable=True, index=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("tmdb_person_id", sa.Integer(), unique=True, nullable=True, index=True),
        sa.Column("kobis_person_nm", sa.String(200), nullable=True),
        sa.Column("canonical_id", sa.Integer(), sa.ForeignKey("person_master.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── content_credits ───────────────────────────────────────
    op.create_table(
        "content_credits",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False, index=True),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("person_master.id"), nullable=False, index=True),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("character_name", sa.String(300), nullable=True),
        sa.Column("cast_order", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), default="cp"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── content_images ────────────────────────────────────────
    op.create_table(
        "content_images",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False, index=True),
        sa.Column("image_type", sa.String(20), nullable=False, index=True),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(20), default="cp"),
        sa.Column("is_primary", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── external_meta_sources ─────────────────────────────────
    op.create_table(
        "external_meta_sources",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=True, index=True),
        sa.Column("source_type", sa.String(30), nullable=False, index=True),
        sa.Column("external_id", sa.String(200), nullable=True, index=True),
        sa.Column("title_on_source", sa.String(500), nullable=True),
        sa.Column("raw_json", sa.JSON(), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── content_ai_results ────────────────────────────────────
    op.create_table(
        "content_ai_results",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("content_id", sa.Integer(), sa.ForeignKey("contents.id"), nullable=False, index=True),
        sa.Column("engine", sa.String(100), nullable=False, index=True),
        sa.Column("task_type", sa.String(30), nullable=False, index=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("is_final", sa.Boolean(), default=False, index=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))" if dialect == "sqlite" else "now()")),
    )

    # ── 기본 장르 데이터 시딩 ────────────────────────────────
    op.bulk_insert(
        sa.table(
            "genre_codes",
            sa.column("code", sa.String),
            sa.column("name_ko", sa.String),
            sa.column("name_en", sa.String),
            sa.column("parent_id", sa.Integer),
            sa.column("sort_order", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            # 대분류
            {"code": "ACT", "name_ko": "액션", "name_en": "Action", "parent_id": None, "sort_order": 1, "is_active": True},
            {"code": "DRM", "name_ko": "드라마", "name_en": "Drama", "parent_id": None, "sort_order": 2, "is_active": True},
            {"code": "COM", "name_ko": "코미디", "name_en": "Comedy", "parent_id": None, "sort_order": 3, "is_active": True},
            {"code": "ROM", "name_ko": "로맨스", "name_en": "Romance", "parent_id": None, "sort_order": 4, "is_active": True},
            {"code": "THR", "name_ko": "스릴러", "name_en": "Thriller", "parent_id": None, "sort_order": 5, "is_active": True},
            {"code": "HOR", "name_ko": "공포", "name_en": "Horror", "parent_id": None, "sort_order": 6, "is_active": True},
            {"code": "SCI", "name_ko": "SF", "name_en": "Sci-Fi", "parent_id": None, "sort_order": 7, "is_active": True},
            {"code": "FAN", "name_ko": "판타지", "name_en": "Fantasy", "parent_id": None, "sort_order": 8, "is_active": True},
            {"code": "ANI", "name_ko": "애니메이션", "name_en": "Animation", "parent_id": None, "sort_order": 9, "is_active": True},
            {"code": "DOC", "name_ko": "다큐멘터리", "name_en": "Documentary", "parent_id": None, "sort_order": 10, "is_active": True},
            {"code": "VAR", "name_ko": "예능", "name_en": "Variety", "parent_id": None, "sort_order": 11, "is_active": True},
            {"code": "KID", "name_ko": "키즈", "name_en": "Kids", "parent_id": None, "sort_order": 12, "is_active": True},
            {"code": "EDU", "name_ko": "교육", "name_en": "Education", "parent_id": None, "sort_order": 13, "is_active": True},
            {"code": "SPT", "name_ko": "스포츠", "name_en": "Sports", "parent_id": None, "sort_order": 14, "is_active": True},
            {"code": "MUS", "name_ko": "음악", "name_en": "Music", "parent_id": None, "sort_order": 15, "is_active": True},
            {"code": "HIS", "name_ko": "역사", "name_en": "History", "parent_id": None, "sort_order": 16, "is_active": True},
            {"code": "CRM", "name_ko": "범죄", "name_en": "Crime", "parent_id": None, "sort_order": 17, "is_active": True},
            {"code": "MYS", "name_ko": "미스터리", "name_en": "Mystery", "parent_id": None, "sort_order": 18, "is_active": True},
            {"code": "ADV", "name_ko": "어드벤처", "name_en": "Adventure", "parent_id": None, "sort_order": 19, "is_active": True},
            {"code": "WAR", "name_ko": "전쟁", "name_en": "War", "parent_id": None, "sort_order": 20, "is_active": True},
        ],
    )

    # ── 기본 태그 데이터 시딩 ─────────────────────────────────
    op.bulk_insert(
        sa.table(
            "tag_codes",
            sa.column("tag_type", sa.String),
            sa.column("name", sa.String),
            sa.column("created_by", sa.String),
            sa.column("use_count", sa.Integer),
            sa.column("is_active", sa.Boolean),
        ),
        [
            # mood
            {"tag_type": "mood", "name": "따뜻한", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "긴장감", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "힐링", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "심야감성", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "액션몰입", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "웃음보장", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "mood", "name": "눈물주의", "created_by": "manual", "use_count": 0, "is_active": True},
            # theme
            {"tag_type": "theme", "name": "가족과함께", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "theme", "name": "청춘", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "theme", "name": "성장", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "theme", "name": "복수극", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "theme", "name": "사랑이야기", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "theme", "name": "인간드라마", "created_by": "manual", "use_count": 0, "is_active": True},
            # keyword
            {"tag_type": "keyword", "name": "반전있음", "created_by": "manual", "use_count": 0, "is_active": True},
            {"tag_type": "keyword", "name": "실화기반", "created_by": "manual", "use_count": 0, "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_table("content_ai_results")
    op.drop_table("external_meta_sources")
    op.drop_table("content_images")
    op.drop_table("content_credits")
    op.drop_table("person_master")
    op.drop_table("content_tags")
    op.drop_table("content_genres")
    op.drop_table("tag_codes")
    op.drop_table("genre_codes")
    # PostgreSQL ENUM에서 'season' 제거는 별도 처리 필요 (downgrade 시 수동)
