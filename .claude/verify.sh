#!/usr/bin/env bash
# mediaX 프로젝트 step 검증 스크립트
# 사용: bash .claude/verify.sh <step-id>
# 예:   bash .claude/verify.sh meta-intelligence-step1

set -euo pipefail
STEP="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$SCRIPT_DIR/../backend"
cd "$BACKEND"

source .venv/bin/activate 2>/dev/null || true

case "$STEP" in

  meta-intelligence-step1)
    echo "=== meta-intelligence-step1: migration 0011 + models ==="
    # 1. ENUM + 모델 import
    python3 -c "
from api.meta_core.models.intelligence import (
    MetadataCandidate, MatchEdge, FieldSuggestion, FieldResolution, SeedCandidate
)
from api.programming.metadata.models.external import ExternalSourceType
assert ExternalSourceType.kmdb == 'kmdb'
print('  ✓ import + kmdb ENUM OK')
"
    # 2. SQLite 마이그레이션 확인
    python3 -c "
import sqlite3
conn = sqlite3.connect('media_ax_dev.db')
tables = [t[0] for t in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
for t in ['metadata_candidates','match_edges','field_suggestions','field_resolutions','seed_candidates']:
    assert t in tables, f'{t} 테이블 없음'
sl_cols = [c[1] for c in conn.execute('PRAGMA table_info(external_sync_log)').fetchall()]
assert 'auto_resolved_count' in sl_cols
assert 'manual_review_count' in sl_cols
conn.close()
print('  ✓ 5 테이블 + external_sync_log 컬럼 OK')
"
    echo "=== PASS ==="
    ;;

  meta-intelligence-step2)
    echo "=== meta-intelligence-step2: scoring module ==="
    python3 -c "from api.meta_core.scoring import compute_match_score, classify_match; print('  ✓ import OK')"
    python3 -m pytest tests/meta_core/test_scoring.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step3)
    echo "=== meta-intelligence-step3: score disambiguation ==="
    python3 -c "
import ast, pathlib
src = pathlib.Path('api/meta_core/scoring.py').read_text()
assert '완성도' in src or 'quality_score' in src
src2 = pathlib.Path('api/programming/metadata/ai_engine.py').read_text()
assert '동일성' in src2 or 'match_score' in src2 or '_calculate_quality_score' in src2
print('  ✓ docstring 분리 확인 OK')
"
    echo "=== PASS ==="
    ;;

  meta-intelligence-step4)
    echo "=== meta-intelligence-step4: gap analyzer ==="
    python3 -c "from api.meta_core.gap import analyze_gap, analyze_gap_batch; print('  ✓ import OK')"
    python3 -m pytest tests/meta_core/test_gap.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step5)
    echo "=== meta-intelligence-step5: enrich + kmdb client ==="
    python3 -c "
from api.meta_core.enrich import enrich_content
from api.meta_core.clients.kmdb_client import KmdbClient, KmdbApiKeyMissing
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_enrich.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step6)
    echo "=== meta-intelligence-step6: field strategy catalog ==="
    python3 -c "
from api.meta_core.field_strategy import FIELD_STRATEGIES, FieldType
assert FIELD_STRATEGIES['director'].type == FieldType.A_SINGLE
assert FIELD_STRATEGIES['cast'].type == FieldType.B_MULTI
assert FIELD_STRATEGIES['synopsis'].type == FieldType.C_TEXT
assert FIELD_STRATEGIES['poster'].type == FieldType.D_ASSET
assert FIELD_STRATEGIES['tmdb_id'].type == FieldType.E_EXTERNAL_ID
print('  ✓ catalog OK')
"
    python3 -m pytest tests/meta_core/test_field_strategy.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step7)
    echo "=== meta-intelligence-step7: field aggregator ==="
    python3 -c "
from api.meta_core.aggregator import aggregate_content, aggregate_batch
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_aggregator.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step8)
    echo "=== meta-intelligence-step8: resolution API ==="
    python3 -c "
from api.meta_core.intelligence.router import router
from api.meta_core.intelligence.schemas import GapReportOut, ResolutionsByStatusOut
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_resolution_api.py -q
    echo "=== PASS ==="
    ;;

  meta-intelligence-step9)
    echo "=== meta-intelligence-step9: review backend (write endpoints) ==="
    python3 -c "
from api.meta_core.intelligence.router import accept_resolution, pick_resolution, merge_resolution, reject_resolution, bulk_accept
from api.meta_core.intelligence.schemas import PickRequest, MergeRequest, BulkAcceptRequest, ActionResultOut
from api.meta_core.aggregator import llm_merge_synopses
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_review_backend.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step0)
    echo "=== phase-c-step0: ADR docs/dev/phase-c/ ==="
    DIR="$SCRIPT_DIR/../docs/dev/phase-c"
    test -d "$DIR" || { echo "  ✗ $DIR 없음"; exit 1; }
    REQUIRED_FILES=("_index.md" "lifecycle.md" "sources.md" "promotion-guard.md" "dedup.md" "beat-schedule.md" "ops-cost.md")
    for f in "${REQUIRED_FILES[@]}"; do
      test -f "$DIR/$f" || { echo "  ✗ $f 누락"; exit 1; }
    done
    echo "  ✓ 7개 파일 존재 (_index + 6 섹션)"
    INDEX="$DIR/_index.md"
    for sec in "lifecycle.md" "sources.md" "promotion-guard.md" "dedup.md" "beat-schedule.md" "ops-cost.md"; do
      grep -q "$sec" "$INDEX" || { echo "  ✗ _index.md 에 $sec 링크 누락"; exit 1; }
    done
    echo "  ✓ _index.md 에 6개 섹션 링크 확인"
    grep -qi "phase d\|websearch" "$INDEX" && grep -qi "별도 task\|별도 phase" "$INDEX" \
      || echo "  ⚠ Phase D 경계 명시 권장"
    TOTAL=$(wc -l "$DIR"/*.md | tail -1 | awk '{print $1}')
    test "$TOTAL" -ge 200 || { echo "  ✗ ADR 총 분량 부족 ($TOTAL 줄, 최소 200)"; exit 1; }
    echo "  ✓ 총 분량 $TOTAL 줄"
    echo "=== PASS ==="
    ;;

  phase-c-step1)
    echo "=== phase-c-step1: migration 0012 + ContentSeed/SeedDiscoveryLog ORM ==="
    # 1. migration 파일 존재
    test -f "$BACKEND/alembic/versions/0012_seed_tables.py" \
      || { echo "  ✗ 0012_seed_tables.py 없음"; exit 1; }
    echo "  ✓ 0012_seed_tables.py 존재"
    # 2. ORM import
    python3 -c "
from api.meta_core.models.seed import ContentSeed, SeedDiscoveryLog
from api.meta_core.models import ContentSeed as CS, SeedDiscoveryLog as SDL
from api.programming.metadata.models.external import ExternalSourceType
assert hasattr(ExternalSourceType, 'omdb'), 'ExternalSourceType.omdb 없음 (migration 0012 upgrade 실행 필요)'
from api.meta_core.models.intelligence import MetadataCandidate
assert hasattr(MetadataCandidate, 'target_type'), 'MetadataCandidate.target_type 없음'
assert hasattr(MetadataCandidate, 'target_id'), 'MetadataCandidate.target_id 없음'
assert hasattr(ContentSeed, 'is_locked'), 'ContentSeed.is_locked property 없음'
print('  ✓ import + attribute OK')
"
    # 3. 임시 SQLite engine 으로 테이블 생성 검증 (.env DB 연결 불필요)
    python3 -c "
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
_engine = sa.create_engine('sqlite:////tmp/verify_0012.db', connect_args={'check_same_thread': False})
from shared.database import Base
import api.meta_core.models  # noqa
Base.metadata.create_all(_engine)
insp = sa.inspect(_engine)
tables = insp.get_table_names()
for t in ['content_seeds', 'seed_discovery_log']:
    assert t in tables, f'{t} 테이블 없음'
cols = {c['name'] for c in insp.get_columns('content_seeds')}
for col in ['status', 'locked_by', 'locked_at', 'suspected_match_content_id',
            'last_seen_at', 'alt_external_ids', 'promoted_to_content_id']:
    assert col in cols, f'content_seeds.{col} 컬럼 없음'
mc_cols = {c['name'] for c in insp.get_columns('metadata_candidates')}
assert 'target_type' in mc_cols, 'metadata_candidates.target_type 없음'
assert 'target_id' in mc_cols, 'metadata_candidates.target_id 없음'
print('  ✓ 테이블 + 컬럼 확인 OK')
import os; os.remove('/tmp/verify_0012.db')
"
    echo "=== PASS ==="
    ;;

  phase-c-step2)
    echo "=== phase-c-step2: discovery framework + TmdbDiscoverySource ==="
    python3 -c "
from api.meta_core.discovery import DiscoverySource, TmdbDiscoverySource, run_discovery
from api.meta_core.discovery.base import DiscoveryResult
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_discovery_tmdb.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step3)
    echo "=== phase-c-step3: KobisDiscoverySource ==="
    python3 -c "
from api.meta_core.discovery import KobisDiscoverySource
from api.meta_core.clients.kobis_client import KobisClient
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_discovery_kobis.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step4)
    echo "=== phase-c-step4: KmdbDiscoverySource ==="
    python3 -c "
from api.meta_core.discovery import KmdbDiscoverySource
from api.meta_core.clients.kmdb_client import KmdbClient
assert hasattr(KmdbClient, 'search_recent'), 'KmdbClient.search_recent 없음'
assert hasattr(KmdbClient, 'iter_collection'), 'KmdbClient.iter_collection 없음'
print('  ✓ import + 확장 메서드 OK')
"
    python3 -m pytest tests/meta_core/test_discovery_kmdb.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step5)
    echo "=== phase-c-step5: OmdbDiscoverySource ==="
    python3 -c "
from api.meta_core.discovery import OmdbDiscoverySource
from api.meta_core.clients.omdb_client import OmdbClient, OmdbApiKeyMissing
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_discovery_omdb.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step6)
    echo "=== phase-c-step6: seed-dedup-match ==="
    python3 -c "
from api.meta_core.discovery.dedup import match_or_create_seed
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_seed_dedup.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step7)
    echo "=== phase-c-step7: seed-promote-api ==="
    python3 -c "
from api.meta_core.discovery.promote import promote_seed, SeedNotFound, SeedAlreadyProcessed, SeedLockedByOther, PossibleDuplicate
from api.meta_core.intelligence.router import router
from api.meta_core.intelligence.schemas import PromoteRequest, PromoteResultOut
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_seed_promote.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step8)
    echo "=== phase-c-step8: seed-review-backend ==="
    python3 -c "
from api.meta_core.intelligence.seed_router import router as seed_router
from api.meta_core.intelligence.seed_schemas import SeedListResponse, SeedBulkPromoteRequest, SeedStatsOut
print('  ✓ import OK')
"
    python3 -m pytest tests/meta_core/test_seed_review.py -q
    echo "=== PASS ==="
    ;;

  phase-c-step9)
    echo "=== phase-c-step9: seed-beat-monitoring ==="
    python3 -c "
from workers.tasks.discovery_tasks import discover_tmdb, discover_kobis, discover_kmdb, discover_all_daily
from api.meta_core.intelligence.seed_router import discovery_log, discovery_stats, seed_funnel
# beat 스케줄 확인
from workers.celery_app import celery_app
sched = celery_app.conf.beat_schedule
assert 'discover-tmdb-daily' in sched, 'discover-tmdb-daily beat 없음'
assert 'discover-kobis-daily' in sched, 'discover-kobis-daily beat 없음'
assert 'discover-kmdb-daily' in sched, 'discover-kmdb-daily beat 없음'
assert 'discover-tmdb-weekly' in sched, 'discover-tmdb-weekly beat 없음'
print('  ✓ import + beat 4개 확인 OK')
"
    python3 -m pytest tests/workers/test_discovery_tasks.py tests/meta_core/test_discovery_monitoring.py -q
    echo "=== PASS ==="
    ;;

  quota-adr-step1)
    echo "=== quota-adr-step1: QuotaManager + tests ==="
    python3 -c "from shared.quota_manager import QuotaManager; QuotaManager().is_allowed; print('  ✓ import OK')"
    python3 -m pytest tests/shared/test_quota_manager.py -q
    echo "=== PASS ==="
    ;;

  quota-adr-step2)
    echo "=== quota-adr-step2: KOBIS migration ==="
    python3 -c "
import ast, pathlib
src = pathlib.Path('workers/tasks/metadata.py').read_text()
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_kobis_rate_allowed')
src_fn = ast.unparse(fn)
assert 'QuotaManager' in src_fn or 'is_allowed' in src_fn, 'QuotaManager not used'
assert 'utcnow' not in src_fn, 'utcnow still present (UTC bug)'
assert 'r.incr' not in src_fn, 'direct Redis call still present'
print('  ✓ KOBIS migrated cleanly')
"
    echo "=== PASS ==="
    ;;

  quota-adr-step3)
    echo "=== quota-adr-step3: KMDB rate limit + quota ==="
    python3 -c "
from api.meta_core.clients.kmdb_client import KmdbClient, KmdbDailyLimitExceeded
import inspect
src = inspect.getsource(KmdbClient)
assert '_MIN_INTERVAL' in src, 'rate limit missing'
assert 'QuotaManager' in src or 'is_allowed' in src, 'quota check missing'
print('  ✓ KMDB rate limit + quota wired')
"
    echo "=== PASS ==="
    ;;

  sources-step0)
    echo "=== sources-step0: KOBIS/KMDB 백엔드 엔드포인트 ==="
    python3 -c "
from api.programming.metadata import router
from api.programming.metadata.schemas import ExternalSourceStats, ExternalSourceItem, PaginatedExternalItems
from api.programming.metadata.service import get_external_source_stats, list_external_source_sync_log, search_external_sources
print('  ✓ import OK')
"
    python3 -c "
from api.programming.metadata.router import router as r
paths = [str(route.path) for route in r.routes]
for p in ['/kobis/stats', '/kobis/sync-log', '/kobis/search', '/kmdb/stats', '/kmdb/sync-log', '/kmdb/search']:
    assert p in paths, f'{p} 엔드포인트 없음'
print('  ✓ 6개 엔드포인트 확인 OK')
"
    echo "=== PASS ==="
    ;;

  sources-step1)
    echo "=== sources-step1: api.ts kobisApi/kmdbApi 타입 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    grep -q "kobisApi" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ kobisApi 없음"; exit 1; }
    grep -q "kmdbApi" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ kmdbApi 없음"; exit 1; }
    grep -q "ExternalSourceStats" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ ExternalSourceStats 타입 없음"; exit 1; }
    echo "  ✓ api.ts 확인 OK"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  sources-step2)
    echo "=== sources-step2: 프론트엔드 라우팅 + 페이지 파일 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS/apps/web/app/(main)/programming"
    for p in "sources/page.tsx" "sources/tmdb/page.tsx" "sources/tmdb-sync/page.tsx" "sources/kobis/page.tsx" "sources/kmdb/page.tsx"; do
      test -f "$CMS/$p" || { echo "  ✗ $p 없음"; exit 1; }
    done
    test ! -f "$CMS/tmdb/page.tsx" || { echo "  ✗ 기존 tmdb/page.tsx 남아 있음 — 삭제 필요"; exit 1; }
    test ! -f "$CMS/tmdb-sync/page.tsx" || { echo "  ✗ 기존 tmdb-sync/page.tsx 남아 있음 — 삭제 필요"; exit 1; }
    echo "  ✓ 페이지 파일 구조 OK"
    cd "$SCRIPT_DIR/../mediaX-CMS" && npm run build --silent 2>&1 | tail -10
    echo "=== PASS ==="
    ;;

  sources-step3)
    echo "=== sources-step3: 네비게이션 + metadata 대시보드 연결 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS/apps/web"
    grep -q '"/programming/sources"' "$CMS/config/docs.ts" || { echo "  ✗ docs.ts에 /programming/sources 없음"; exit 1; }
    grep -q "/programming/sources/tmdb" "$CMS/config/docs.ts" || { echo "  ✗ sources/tmdb 링크 없음"; exit 1; }
    grep -q "/programming/sources/kobis" "$CMS/config/docs.ts" || { echo "  ✗ sources/kobis 링크 없음"; exit 1; }
    grep -q '"/programming/sources"' "$CMS/app/(main)/programming/metadata/page.tsx" \
      || { echo "  ✗ metadata/page.tsx 이미지메타 href 미수정"; exit 1; }
    echo "  ✓ 네비게이션 + 대시보드 연결 OK"
    cd "$SCRIPT_DIR/../mediaX-CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  watcha-step0)
    echo "=== watcha-step0: project-setup ==="
    python3 -c "from playwright.sync_api import sync_playwright; print('  ✓ playwright import OK')"
    test -d "$BACKEND/scripts/watcha" || { echo "  ✗ scripts/watcha 없음"; exit 1; }
    test -f "$BACKEND/scripts/watcha/__init__.py" || { echo "  ✗ __init__.py 없음"; exit 1; }
    test -d "$BACKEND/data/watcha" || { echo "  ✗ data/watcha 없음"; exit 1; }
    test -f "$BACKEND/data/watcha/.gitignore" || { echo "  ✗ data/watcha/.gitignore 없음"; exit 1; }
    test -f "$BACKEND/requirements-dev.txt" || { echo "  ✗ requirements-dev.txt 없음"; exit 1; }
    grep -q "playwright" "$BACKEND/requirements-dev.txt" || { echo "  ✗ requirements-dev.txt에 playwright 없음"; exit 1; }
    grep -q "WATCHA_MIN_INTERVAL" "$BACKEND/.env.example" || { echo "  ✗ .env.example에 WATCHA 변수 없음"; exit 1; }
    PLAN="$SCRIPT_DIR/../plans/dev-watcha-sampling/index.json"
    test -f "$PLAN" || { echo "  ✗ plans/dev-watcha-sampling/index.json 없음"; exit 1; }
    python3 -c "import json; d=json.load(open('$PLAN')); assert len(d['steps'])==9, 'step 9개 아님'"
    echo "  ✓ 모든 구조 확인 OK"
    echo "=== PASS ==="
    ;;

  watcha-step1)
    echo "=== watcha-step1: category-discovery ==="
    test -f "$BACKEND/data/watcha/categories.json" || { echo "  ✗ categories.json 없음 (크롤링 먼저 실행)"; exit 1; }
    COUNT=$(python3 -c "import json; d=json.load(open('$BACKEND/data/watcha/categories.json')); print(len(d))")
    test "$COUNT" -ge 20 || { echo "  ✗ 카테고리 $COUNT 개 (최소 20 필요)"; exit 1; }
    echo "  ✓ 카테고리 $COUNT 개 확인 OK"
    echo "=== PASS ==="
    ;;

  watcha-step2)
    echo "=== watcha-step2: list-crawler ==="
    test -f "$BACKEND/data/watcha/list.csv" || { echo "  ✗ list.csv 없음 (크롤링 먼저 실행)"; exit 1; }
    LINES=$(tail -n +2 "$BACKEND/data/watcha/list.csv" | wc -l)
    test "$LINES" -ge 400 || { echo "  ✗ $LINES 건 (최소 400 필요)"; exit 1; }
    echo "  ✓ list.csv $LINES 건 확인 OK"
    echo "=== PASS ==="
    ;;

  watcha-step3)
    echo "=== watcha-step3: detail-crawler ==="
    test -f "$BACKEND/data/watcha/detail.csv" || { echo "  ✗ detail.csv 없음 (크롤링 먼저 실행)"; exit 1; }
    python3 "$BACKEND/scripts/watcha/verify_detail.py"
    echo "=== PASS ==="
    ;;

  watcha-step4)
    echo "=== watcha-step4: real-data-rebuild ==="
    test -d "$BACKEND/data/watcha/_mock_backup" || { echo "  ✗ _mock_backup 디렉토리 없음"; exit 1; }
    test -f "$BACKEND/data/watcha/categories.json" || { echo "  ✗ categories.json 없음"; exit 1; }
    CAT_COUNT=$(python3 -c "import json; d=json.load(open('$BACKEND/data/watcha/categories.json')); print(len(d))")
    test "$CAT_COUNT" -ge 20 || { echo "  ✗ 카테고리 $CAT_COUNT 개 (최소 20 필요)"; exit 1; }
    test -f "$BACKEND/data/watcha/list.csv" || { echo "  ✗ list.csv 없음"; exit 1; }
    LIST_COUNT=$(tail -n +2 "$BACKEND/data/watcha/list.csv" | wc -l)
    test "$LIST_COUNT" -ge 400 || { echo "  ✗ list.csv $LIST_COUNT 건 (최소 400 필요)"; exit 1; }
    test -f "$BACKEND/data/watcha/detail.csv" || { echo "  ✗ detail.csv 없음"; exit 1; }
    python3 "$BACKEND/scripts/watcha/verify_detail.py" || { echo "  ✗ verify_detail.py 실패"; exit 1; }
    STEP_COUNT=$(python3 -c "import json; d=json.load(open('$BACKEND/../plans/dev-watcha-sampling/index.json')); print(len(d['steps']))")
    test "$STEP_COUNT" -eq 9 || { echo "  ✗ index.json step 갯수 $STEP_COUNT (9 필요)"; exit 1; }
    echo "  ✓ real-data-rebuild 확인 OK (카테고리 $CAT_COUNT, list $LIST_COUNT, step 9개)"
    echo "=== PASS ==="
    ;;

  watcha-step5)
    echo "=== watcha-step5: poster-batch-download ==="
    test -f "$BACKEND/data/watcha/detail_final.csv" || { echo "  ✗ detail_final.csv 없음"; exit 1; }
    test -d "$BACKEND/data/watcha/posters" || { echo "  ✗ posters/ 디렉토리 없음"; exit 1; }
    POSTER_COUNT=$(ls "$BACKEND/data/watcha/posters/" | wc -l)
    DETAIL_LINES=$(tail -n +2 "$BACKEND/data/watcha/detail.csv" | wc -l)
    THRESHOLD=$(python3 -c "print(int($DETAIL_LINES * 0.9))")
    test "$POSTER_COUNT" -ge "$THRESHOLD" || { echo "  ✗ 포스터 $POSTER_COUNT 개 (detail 90% = $THRESHOLD 필요)"; exit 1; }
    echo "  ✓ 포스터 $POSTER_COUNT / $DETAIL_LINES (90% 이상) OK"
    echo "=== PASS ==="
    ;;

  watcha-step6)
    echo "=== watcha-step6: db-bulk-insert ==="
    python3 -c "
import os; os.chdir('$BACKEND')
from shared.database import SessionLocal
from api.programming.metadata.models.external import ExternalMetaSource, ExternalSourceType
db = SessionLocal()
count = db.query(ExternalMetaSource).filter(ExternalMetaSource.source_type == ExternalSourceType.watcha).count()
db.close()
assert count >= 400, f'watcha row {count}개 (최소 400 필요)'
print(f'  ✓ ExternalMetaSource watcha {count}개 확인 OK')
"
    echo "=== PASS ==="
    ;;

  watcha-step7)
    echo "=== watcha-step7: cross-source-verification ==="
    test -f "$BACKEND/data/watcha/verify_report.md" || { echo "  ✗ verify_report.md 없음"; exit 1; }
    grep -q "## 일치율" "$BACKEND/data/watcha/verify_report.md" || { echo "  ✗ 일치율 섹션 없음"; exit 1; }
    echo "  ✓ verify_report.md 확인 OK"
    echo "=== PASS ==="
    ;;

  watcha-step8)
    echo "=== watcha-step8: ai-fallback-validation ==="
    test -f "$BACKEND/data/watcha/fallback_test_report.md" || { echo "  ✗ fallback_test_report.md 없음"; exit 1; }
    echo "  ✓ fallback_test_report.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step0)
    echo "=== ui-consolidation-step0: page-inventory-analysis ==="
    test -f "$SCRIPT_DIR/../docs/dev/ui-consolidation/01_current_inventory.md" \
      || { echo "  ✗ 01_current_inventory.md 없음"; exit 1; }
    echo "  ✓ 01_current_inventory.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step1)
    echo "=== ui-consolidation-step1: menu-structure-redesign ==="
    test -f "$SCRIPT_DIR/../docs/dev/ui-consolidation/02_menu_lifecycle.md" \
      || { echo "  ✗ 02_menu_lifecycle.md 없음"; exit 1; }
    echo "  ✓ 02_menu_lifecycle.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step2)
    echo "=== ui-consolidation-step2: content-add-flow ==="
    test -f "$SCRIPT_DIR/../docs/dev/ui-consolidation/03_content_add.md" \
      || { echo "  ✗ 03_content_add.md 없음"; exit 1; }
    echo "  ✓ 03_content_add.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step3)
    echo "=== ui-consolidation-step3: content-detail-tabs ==="
    DOC="$SCRIPT_DIR/../docs/dev/ui-consolidation/04_content_detail.md"
    test -f "$DOC" || { echo "  ✗ 04_content_detail.md 없음"; exit 1; }
    # 5개 탭 + 핵심 패턴 섹션 헤더 존재 확인
    grep -q "탭 #1 — 글자" "$DOC" || { echo "  ✗ 글자 탭 섹션 없음"; exit 1; }
    grep -q "탭 #2 — 이미지" "$DOC" || { echo "  ✗ 이미지 탭 섹션 없음"; exit 1; }
    grep -q "탭 #3 — 영상" "$DOC" || { echo "  ✗ 영상 탭 섹션 없음"; exit 1; }
    grep -q "탭 #4 — 외부 소스" "$DOC" || { echo "  ✗ 외부 소스 탭 섹션 없음"; exit 1; }
    grep -q "탭 #5 — AI 이력" "$DOC" || { echo "  ✗ AI 이력 탭 섹션 없음"; exit 1; }
    echo "  ✓ 04_content_detail.md + 5개 탭 섹션 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step4)
    echo "=== ui-consolidation-step4: bulk-action-ux ==="
    test -f "$SCRIPT_DIR/../docs/dev/ui-consolidation/05_bulk_action.md" \
      || { echo "  ✗ 05_bulk_action.md 없음"; exit 1; }
    echo "  ✓ 05_bulk_action.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step5)
    echo "=== ui-consolidation-step5: ai-enrichment-flow ==="
    test -f "$SCRIPT_DIR/../docs/dev/ui-consolidation/06_ai_enrichment.md" \
      || { echo "  ✗ 06_ai_enrichment.md 없음"; exit 1; }
    echo "  ✓ 06_ai_enrichment.md 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step6)
    echo "=== ui-consolidation-step6: prototype-list-detail ==="
    PROTO_DIR="$SCRIPT_DIR/../mediaX-CMS/apps/web/app/(prototypes)"
    test -d "$PROTO_DIR/list" || { echo "  ✗ prototypes/list 디렉토리 없음"; exit 1; }
    test -d "$PROTO_DIR/detail" || { echo "  ✗ prototypes/detail 디렉토리 없음"; exit 1; }
    echo "  ✓ prototype list + detail 디렉토리 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-consolidation-step7)
    echo "=== ui-consolidation-step7: prototype-add-bulk ==="
    PROTO_DIR="$SCRIPT_DIR/../mediaX-CMS/apps/web/app/(prototypes)"
    test -d "$PROTO_DIR/add" || { echo "  ✗ prototypes/add 디렉토리 없음"; exit 1; }
    test -d "$PROTO_DIR/bulk" || { echo "  ✗ prototypes/bulk 디렉토리 없음"; exit 1; }
    echo "  ✓ prototype add + bulk 디렉토리 확인 OK"
    echo "=== PASS ==="
    ;;

  ui-impl-1)
    echo "=== ui-impl-1: sidebar + content list ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DOCS="$CMS/apps/web/config/docs.ts"
    PAGE="$CMS/apps/web/app/(main)/programming/contents/page.tsx"
    grep -q "메타데이터 (레거시)" "$DOCS" || { echo "  ✗ '메타데이터 (레거시)' 라벨 미반영"; exit 1; }
    grep -q "콘텐츠 목록" "$DOCS" || { echo "  ✗ '콘텐츠 목록' 메뉴 항목 없음"; exit 1; }
    echo "  ✓ docs.ts: 레거시 라벨 + 콘텐츠 목록 항목 OK"
    grep -q "UI_GROUPS" "$PAGE" || { echo "  ✗ UI 4 그룹 칩(UI_GROUPS) 미구현"; exit 1; }
    grep -q "selectedIds" "$PAGE" || { echo "  ✗ 다중선택(selectedIds) 미구현"; exit 1; }
    grep -q "sticky top" "$PAGE" || { echo "  ✗ sticky 액션 바(sticky top) 미구현"; exit 1; }
    grep -q "EnrichmentBadge" "$PAGE" || { echo "  ✗ EnrichmentBadge 미구현"; exit 1; }
    echo "  ✓ contents/page.tsx: UI 그룹 + 다중선택 + sticky bar + Enrichment 배지 OK"
    cd "$CMS" && npx tsc --noEmit -p apps/web/tsconfig.json
    echo "  ✓ apps/web typecheck PASS"
    echo "=== PASS ==="
    ;;

  ui-impl-2)
    echo "=== ui-impl-2: content detail 5탭 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DETAIL_PAGE="$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    [ -f "$DETAIL_PAGE" ] || { echo "  ✗ [id]/page.tsx 파일 없음"; exit 1; }
    grep -q "type TabName = \"text\" | \"image\" | \"video\" | \"sources\" | \"ai\"" "$DETAIL_PAGE" || { echo "  ✗ 5탭 구조 미정의"; exit 1; }
    grep -q "metadataApi.getContent" "$DETAIL_PAGE" || { echo "  ✗ metadataApi.getContent 호출 없음"; exit 1; }
    grep -q "activeTab === \"text\"" "$DETAIL_PAGE" || { echo "  ✗ text 탭 내용 미구현"; exit 1; }
    grep -q "activeTab === \"image\"" "$DETAIL_PAGE" || { echo "  ✗ image 탭 내용 미구현"; exit 1; }
    grep -q "activeTab === \"video\"" "$DETAIL_PAGE" || { echo "  ✗ video 탭 내용 미구현"; exit 1; }
    grep -q "activeTab === \"sources\"" "$DETAIL_PAGE" || { echo "  ✗ sources 탭 내용 미구현"; exit 1; }
    grep -q "activeTab === \"ai\"" "$DETAIL_PAGE" || { echo "  ✗ ai 탭 내용 미구현"; exit 1; }
    echo "  ✓ [id]/page.tsx: 5탭 구조 + 탭 내용 OK"
    cd "$CMS" && npx tsc --noEmit -p apps/web/tsconfig.json
    echo "  ✓ apps/web typecheck PASS"
    echo "=== PASS ==="
    ;;

  ui-impl-3)
    echo "=== ui-impl-3: Add/Bulk modals (shadcn Dialog) ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DIALOG="$CMS/packages/ui/src/components/dialog.tsx"
    ADD_MODAL="$CMS/apps/web/components/contents/AddContentModal.tsx"
    BULK_MODAL="$CMS/apps/web/components/contents/BulkActionModal.tsx"
    CONTENTS_PAGE="$CMS/apps/web/app/(main)/programming/contents/page.tsx"

    [ -f "$DIALOG" ] || { echo "  ✗ dialog.tsx 미설치"; exit 1; }
    grep -q "@radix-ui/react-dialog" "$CMS/package.json" || { echo "  ✗ @radix-ui/react-dialog 미설치"; exit 1; }
    echo "  ✓ shadcn Dialog 설치 OK"

    [ -f "$ADD_MODAL" ] || { echo "  ✗ AddContentModal.tsx 없음"; exit 1; }
    grep -q "type AddTab = \"single\" | \"csv\" | \"external\"" "$ADD_MODAL" || { echo "  ✗ AddContentModal 3탭 구조 미구현"; exit 1; }
    echo "  ✓ AddContentModal 컴포넌트 OK"

    [ -f "$BULK_MODAL" ] || { echo "  ✗ BulkActionModal.tsx 없음"; exit 1; }
    grep -q "type BulkStep = \"confirm\" | \"progress\" | \"result\"" "$BULK_MODAL" || { echo "  ✗ BulkActionModal 3단계 구조 미구현"; exit 1; }
    echo "  ✓ BulkActionModal 컴포넌트 OK"

    grep -q "setAddModalOpen(true)" "$CONTENTS_PAGE" || { echo "  ✗ contents 페이지에 AddContentModal 연결 미구현"; exit 1; }
    grep -q "setBulkModalOpen(true)" "$CONTENTS_PAGE" || { echo "  ✗ contents 페이지에 BulkActionModal 연결 미구현"; exit 1; }
    echo "  ✓ contents/page.tsx 모달 연결 OK"

    cd "$CMS" && npx tsc --noEmit -p apps/web/tsconfig.json
    echo "  ✓ apps/web typecheck PASS"
    echo "=== PASS ==="
    ;;

  ui-impl-4)
    echo "=== ui-impl-4: Pipeline page + cleanup (remove legacy) ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    PIPELINE="$CMS/apps/web/app/(main)/programming/contents/pipeline/page.tsx"
    DOCS="$CMS/apps/web/config/docs.ts"

    [ -f "$PIPELINE" ] || { echo "  ✗ pipeline/page.tsx 없음"; exit 1; }
    grep -q "MOCK_PIPELINE" "$PIPELINE" || { echo "  ✗ pipeline 페이지 미구현"; exit 1; }
    echo "  ✓ pipeline/page.tsx 존재 + KPI 카드 OK"

    ! grep -q "메타데이터 (레거시)" "$DOCS" || { echo "  ✗ docs.ts에 '메타데이터 (레거시)' 여전히 존재"; exit 1; }
    grep -q "처리 현황" "$DOCS" || { echo "  ✗ docs.ts에 '처리 현황' 항목 미추가"; exit 1; }
    echo "  ✓ docs.ts: 메타데이터 레거시 삭제 + 처리 현황 추가 OK"

    [ ! -d "$CMS/apps/web/app/(main)/programming/metadata" ] || { echo "  ✗ metadata 디렉토리 미삭제"; exit 1; }
    [ ! -d "$CMS/apps/web/app/(main)/monitoring/pipeline" ] || { echo "  ✗ monitoring/pipeline 디렉토리 미삭제"; exit 1; }
    [ ! -d "$CMS/apps/web/app/(prototypes)" ] || { echo "  ✗ prototypes 디렉토리 미삭제"; exit 1; }
    echo "  ✓ 레거시 디렉토리 삭제 OK"

    cd "$CMS" && npm run build > /tmp/build.log 2>&1 || { echo "  ✗ npm run build failed:"; tail -20 /tmp/build.log; exit 1; }
    echo "  ✓ npm run build PASS"
    echo "=== PASS ==="
    ;;

  *)
    echo "ERROR: 알 수 없는 step-id '$STEP'"
    echo "사용 가능한 step: meta-intelligence-step1 ~ step9, phase-c-step0 ~ phase-c-step9, quota-adr-step1 ~ step3, sources-step0 ~ step3, watcha-step0 ~ step8, ui-consolidation-step0 ~ step7, ui-impl-1, ui-impl-2, ui-impl-3, ui-impl-4"
    exit 1
    ;;
esac
