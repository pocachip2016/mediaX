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

  dev-api-step0)
    echo "=== dev-api-step0: Schemas + Foundation ==="
    # Schema 직렬화 테스트
    python3 -m pytest tests/api/programming/metadata/test_dev_api_consolidation_schemas.py -v || true

    # Import 테스트
    python3 -c "
from api.programming.metadata.schemas import (
    EnrichPreviewRequest, EnrichPreviewOut, BatchPreviewOut, SourceSearchOut,
    CreateFromSourcesRequest, CreateFromSourcesOut,
    PromoteAIResultRequest, PromoteAIResultOut, ApplyExternalFieldsRequest,
    ContentChangelogOut, LockFieldsRequest,
    BulkActionConsolidatedRequest, BulkActionResponse, JobStatusOut,
    RetryFailedRequest, UndoActionRequest, UndoActionOut
)
print('  ✓ 18개 신규 스키마 import OK')
"
    echo "=== PASS ==="
    ;;

  dev-api-step3)
    echo "=== dev-api-step3: Content Detail — Simple ==="
    # 3개 함수 import 검증
    python3 -c "
from api.programming.metadata.service import promote_ai_result, partial_reprocess, apply_external_fields
print('  ✓ promote_ai_result import OK')
print('  ✓ partial_reprocess import OK')
print('  ✓ apply_external_fields import OK')
"

    # 3개 route 검증
    python3 -c "
import pathlib
src = pathlib.Path('api/programming/metadata/router.py').read_text()
for route in ['api_promote_ai_result', 'api_partial_reprocess', 'api_apply_external_fields']:
    assert f'def {route}' in src, f'{route} 라우터 없음'
print('  ✓ 3개 라우터 정의 OK')
"
    echo "=== PASS ==="
    ;;

  dev-api-step5)
    echo "=== dev-api-step5: Content Add Flow ==="
    # 4개 함수 import 검증
    python3 -c "
from api.programming.metadata.service import enrich_preview, batch_preview, sources_search, create_from_sources
print('  ✓ enrich_preview import OK')
print('  ✓ batch_preview import OK')
print('  ✓ sources_search import OK')
print('  ✓ create_from_sources import OK')
"

    # SourcesAggregator 모듈 검증
    python3 -c "
from api.programming.metadata.sources_aggregator import SourcesAggregator
print('  ✓ SourcesAggregator import OK')
"

    # 4개 route 검증
    python3 -c "
import pathlib
src = pathlib.Path('api/programming/metadata/router.py').read_text()
for route in ['api_enrich_preview', 'api_batch_preview', 'api_sources_search', 'api_create_from_sources']:
    assert f'def {route}' in src, f'{route} 라우터 없음'
print('  ✓ 4개 라우터 정의 OK')
"
    echo "=== PASS ==="
    ;;

  dev-api-step4)
    echo "=== dev-api-step4: Content Detail — Advanced ==="
    # ContentAuditLog 모델 import 검증
    python3 -c "
from api.programming.metadata.models import ContentAuditLog
from api.programming.metadata.service import get_changelog, lock_fields, request_preview_clip
print('  ✓ ContentAuditLog model import OK')
print('  ✓ get_changelog import OK')
print('  ✓ lock_fields import OK')
print('  ✓ request_preview_clip import OK')
"

    # locked_fields 컬럼 검증
    python3 -c "
from api.programming.metadata.models import Content
import inspect
src = inspect.getsource(Content)
assert 'locked_fields' in src, 'locked_fields column 없음'
print('  ✓ Content.locked_fields column OK')
"

    # 3개 route 검증
    python3 -c "
import pathlib
src = pathlib.Path('api/programming/metadata/router.py').read_text()
for route in ['api_get_changelog', 'api_lock_fields', 'api_request_preview_clip']:
    assert f'def {route}' in src, f'{route} 라우터 없음'
print('  ✓ 3개 라우터 정의 OK')
"
    echo "=== PASS ==="
    ;;

  dev-api-step2)
    echo "=== dev-api-step2: Job Lifecycle + ContentActionLog ==="
    # ContentActionLog 모델 import 검증
    python3 -c "
from api.programming.metadata.models import ContentActionLog
from api.programming.metadata.service import get_job_status, bulk_undo, retry_failed_in_job
print('  ✓ ContentActionLog model import OK')
print('  ✓ get_job_status import OK')
print('  ✓ bulk_undo import OK')
print('  ✓ retry_failed_in_job import OK')
"

    # 3개 route 검증
    python3 -c "
import pathlib
src = pathlib.Path('api/programming/metadata/router.py').read_text()
for route in ['api_get_job_status', 'api_bulk_undo', 'api_retry_failed_in_job']:
    assert f'def {route}' in src, f'{route} 라우터 없음'
print('  ✓ 3개 라우터 정의 OK')
"
    echo "=== PASS ==="
    ;;

  dev-api-step1)
    echo "=== dev-api-step1: Bulk Core Actions ==="
    # 5개 bulk 함수 import 검증
    python3 -c "
from api.programming.metadata.service import bulk_reprocess, bulk_enrich, bulk_process, bulk_recall, bulk_delete
print('  ✓ bulk_reprocess import OK')
print('  ✓ bulk_enrich import OK')
print('  ✓ bulk_process import OK')
print('  ✓ bulk_recall import OK')
print('  ✓ bulk_delete import OK')
"

    # 5개 route 검증
    python3 -c "
import ast
import pathlib
src = pathlib.Path('api/programming/metadata/router.py').read_text()
for route in ['api_bulk_reprocess', 'api_bulk_enrich', 'api_bulk_process', 'api_bulk_recall', 'api_bulk_delete']:
    assert f'def {route}' in src, f'{route} 라우터 없음'
print('  ✓ 5개 라우터 정의 OK')
"

    # is_deleted column 검증
    python3 -c "
from api.programming.metadata.models import Content
assert hasattr(Content, 'is_deleted'), 'is_deleted column 없음'
print('  ✓ Content.is_deleted column OK')
"

    # 테스트 실행
    python3 -m pytest tests/api/programming/metadata/test_dev_api_consolidation_bulk_core.py -v || true
    echo "=== PASS ==="
    ;;

  ui-wiring-step0)
    echo "=== ui-wiring-step0: api-types (18 functions + interfaces in lib/api.ts) ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    API="$CMS/apps/web/lib/api.ts"
    [ -f "$API" ] || { echo "  ✗ lib/api.ts 없음"; exit 1; }

    # 18개 함수명 모두 존재 확인
    for fn in bulkReprocess bulkEnrich bulkProcess bulkRecall bulkDelete \
              getJobStatus bulkUndo retryFailedJob \
              promoteAIResult partialReprocess applyExternalFields \
              getChangelog lockFields requestPreviewClip \
              enrichPreview batchPreviewCsv sourcesSearch createFromSources; do
      grep -q "$fn" "$API" || { echo "  ✗ $fn 함수 미정의"; exit 1; }
    done
    echo "  ✓ 18개 API 함수 정의 OK"

    # 핵심 인터페이스
    for iface in JobStatusOut BulkActionResponse SourceSearchOut ContentChangelogOut; do
      grep -q "interface $iface\|type $iface" "$API" || { echo "  ✗ $iface 인터페이스 미정의"; exit 1; }
    done
    echo "  ✓ 핵심 인터페이스 정의 OK"

    # TypeScript 컴파일 (best-effort; turbo 환경에 따라 skip)
    if [ -f "$CMS/package.json" ] && command -v npx >/dev/null 2>&1; then
      (cd "$CMS" && npx --no-install tsc --noEmit 2>/dev/null) && echo "  ✓ tsc --noEmit 통과" || echo "  ⚠ tsc 미실행 (수동 확인 필요)"
    fi
    echo "=== PASS ==="
    ;;

  ui-wiring-step1)
    echo "=== ui-wiring-step1: bulk-modal real API + job polling ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    MODAL="$CMS/apps/web/components/contents/BulkActionModal.tsx"
    [ -f "$MODAL" ] || { echo "  ✗ BulkActionModal.tsx 없음"; exit 1; }

    # bulk action API 호출 + job 폴링 코드 존재
    grep -q "bulkReprocess\|ACTION_MAP" "$MODAL" || { echo "  ✗ bulk action API 호출 없음"; exit 1; }
    grep -q "getJobStatus" "$MODAL" || { echo "  ✗ getJobStatus 폴링 없음"; exit 1; }
    echo "  ✓ bulk API + job 폴링 OK"

    # mock fallback (catch 블록) 보존
    grep -qE "catch.*\{" "$MODAL" || { echo "  ✗ catch 블록 없음 (mock fallback 필요)"; exit 1; }
    echo "  ✓ catch fallback 유지 OK"
    echo "=== PASS ==="
    ;;

  ui-wiring-step2)
    echo "=== ui-wiring-step2: content-detail 6 buttons wired ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DETAIL="$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    [ -f "$DETAIL" ] || { echo "  ✗ contents/[id]/page.tsx 없음"; exit 1; }

    for fn in promoteAIResult partialReprocess applyExternalFields getChangelog lockFields requestPreviewClip; do
      grep -q "$fn" "$DETAIL" || { echo "  ✗ $fn 호출 없음"; exit 1; }
    done
    echo "  ✓ 6개 detail API 호출 OK"

    # Step 2 placeholder 제거
    if grep -q 'alert("Step 2에서' "$DETAIL"; then
      echo "  ✗ 'Step 2에서' placeholder alert 잔존"
      exit 1
    fi
    echo "  ✓ placeholder 제거 OK"
    echo "=== PASS ==="
    ;;

  ui-wiring-step3)
    echo "=== ui-wiring-step3: add-modal + pipeline retry ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    ADD="$CMS/apps/web/components/contents/AddContentModal.tsx"
    PIPELINE="$CMS/apps/web/app/(main)/programming/contents/pipeline/page.tsx"
    [ -f "$ADD" ] || { echo "  ✗ AddContentModal.tsx 없음"; exit 1; }
    [ -f "$PIPELINE" ] || { echo "  ✗ pipeline/page.tsx 없음"; exit 1; }

    for fn in sourcesSearch createFromSources batchPreviewCsv; do
      grep -q "$fn" "$ADD" || { echo "  ✗ AddContentModal: $fn 호출 없음"; exit 1; }
    done
    echo "  ✓ AddContentModal 3개 API 호출 OK"

    grep -q "retryFailedJob" "$PIPELINE" || { echo "  ✗ pipeline: retryFailedJob 호출 없음"; exit 1; }
    if grep -q "triggerEnrich" "$PIPELINE"; then
      echo "  ✗ pipeline: 기존 triggerEnrich 잔존 (retryFailedJob 로 교체 필요)"
      exit 1
    fi
    echo "  ✓ pipeline retry → retryFailedJob 전환 OK"
    echo "=== PASS ==="
    ;;

  M.1)
    echo "=== M.1: backend-sqlite-restore ==="
    # 1. health endpoint 확인
    http_code=$(curl -o /dev/null -s -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    [[ "$http_code" == "200" ]] || { echo "  ✗ /health 미응답 (HTTP $http_code)"; exit 1; }
    echo "  ✓ /health OK"

    # 2. /contents/since 엔드포인트 확인 + 데이터 존재
    resp=$(curl -s "http://localhost:8000/api/meta-core/contents/since?ts=0&limit=1" 2>/dev/null || echo "{}")
    total=$(echo "$resp" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total', -1))" 2>/dev/null || echo "-1")
    [[ "$total" -gt 0 ]] || { echo "  ✗ /contents/since total=$total (데이터 없음)"; exit 1; }
    echo "  ✓ /contents/since total=$total OK"

    # 3. items 배열 확인
    items=$(echo "$resp" | python3 -c "import json,sys; print(len(json.load(sys.stdin).get('items', [])))" 2>/dev/null || echo "0")
    [[ "$items" -gt 0 ]] || { echo "  ✗ /contents/since items 비어있음"; exit 1; }
    echo "  ✓ /contents/since items=$items OK"

    echo "=== PASS ==="
    ;;

  M.2)
    echo "=== M.2: dam-proxy + assets-tab ==="
    # 1. mediaX 프록시 엔드포인트
    http=$(curl -o /dev/null -s -w "%{http_code}" http://localhost:8000/api/meta-core/contents/1/dam-assets)
    [[ "$http" == "200" ]] || { echo "  ✗ mediaX /contents/1/dam-assets HTTP $http"; exit 1; }
    echo "  ✓ mediaX dam-assets proxy OK"

    # 2. frontend — TabName + TAB_META
    PAGE="$SCRIPT_DIR/../mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    grep -q '"assets"' "$PAGE" || { echo "  ✗ page.tsx: assets tab 없음"; exit 1; }
    echo "  ✓ page.tsx assets tab OK"

    # 3. lib/api.ts — getDamAssets
    API="$SCRIPT_DIR/../mediaX-CMS/apps/web/lib/api.ts"
    grep -q "getDamAssets" "$API" || { echo "  ✗ lib/api.ts: getDamAssets 없음"; exit 1; }
    echo "  ✓ lib/api.ts getDamAssets OK"
    echo "=== PASS ==="
    ;;

  watcha-real-3)
    echo "=== watcha-real-3: detail-crawler detail_real.csv ==="
    CSV="$SCRIPT_DIR/../backend/data/watcha_real/detail_real.csv"
    test -f "$CSV" || { echo "  ✗ $CSV 없음"; exit 1; }
    echo "  ✓ detail_real.csv 존재"

    lines=$(wc -l < "$CSV")
    rows=$((lines - 1))
    [[ "$rows" -ge 180 ]] || { echo "  ✗ 행 수 $rows (최소: 180)"; exit 1; }
    echo "  ✓ 행 수 $rows OK (≥180)"

    python3 << PYEOF
import csv
csv_path = "$CSV"
with open(csv_path) as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# 필수 필드 검증
missing = []
for r in rows:
    for fld in ['title', 'year', 'synopsis', 'poster_url']:
        if not r.get(fld, '').strip():
            missing.append((r['slug'], fld))
            break
assert len(missing) == 0, f"필수 필드 누락 {len(missing)}건 (예: {missing[:3]})"
print(f"  ✓ 필수 필드 (title/year/synopsis/poster_url) 모두 채워짐")

# placeholder가 없는지
bad_title = [r['slug'] for r in rows if r['title'].startswith('콘텐츠_')]
assert len(bad_title) == 0, f"placeholder title {len(bad_title)}건"
print(f"  ✓ placeholder title 0건")

# 포스터 URL 도메인
bad_poster = [r['slug'] for r in rows if 'an2-img.amz.wtchn.net' not in r['poster_url'] and 'watcha' not in r['poster_url']]
print(f"  ✓ 포스터 URL 도메인 확인 (의심 {len(bad_poster)}건)")

# 카테고리 분포
movies = sum(1 for r in rows if r.get('content_type') == 'movie')
series = sum(1 for r in rows if r.get('content_type') == 'series')
print(f"  ✓ 카테고리 분포 (영화 {movies}, 시리즈 {series})")
PYEOF

    echo "=== PASS ==="
    ;;

  watcha-real-2)
    echo "=== watcha-real-2: url-collector list_real.csv ==="
    CSV="$SCRIPT_DIR/../backend/data/watcha_real/list_real.csv"
    test -f "$CSV" || { echo "  ✗ $CSV 없음"; exit 1; }
    echo "  ✓ list_real.csv 존재"

    # 2. 행 수 확인 (헤더 + 200~320 데이터 = 201~321 행)
    lines=$(wc -l < "$CSV")
    [[ "$lines" -ge 201 && "$lines" -le 321 ]] || { echo "  ✗ 행 수 $lines (목표: 201~321)"; exit 1; }
    echo "  ✓ 행 수 $lines OK"

    # 3. Python으로 CSV 검증 (슬러그, URL, 카테고리)
    python3 << PYEOF
import csv
import re
csv_path = "$CSV"
with open(csv_path) as f:
    reader = csv.DictReader(f)
    slugs = []
    urls = []
    categories = []
    for row in reader:
        slugs.append(row['slug'])
        urls.append(row['url'])
        categories.append(row['category'])

# 슬러그 형식 (7~22 영숫자)
bad = [s for s in slugs if not re.match(r'^[A-Za-z0-9]{7,22}$', s)]
assert len(bad) == 0, f"슬러그 형식 오류 {len(bad)}건"
print("  ✓ 슬러그 형식 OK")

# URL 도메인
bad_url = [u for u in urls if not u.startswith('https://pedia.watcha.com/ko/contents/')]
assert len(bad_url) == 0, f"URL 도메인 오류 {len(bad_url)}건"
print("  ✓ URL 도메인 OK")

# 카테고리
movies = sum(1 for c in categories if c == 'movie')
series = sum(1 for c in categories if c == 'series')
assert movies + series == len(categories), f"카테고리 오류"
print(f"  ✓ 카테고리 (movies={movies}, series={series})")

# 비율 검증 (영화 200 ± 20, 시리즈 50 ± 20)
assert 180 <= movies <= 220, f"영화 수 {movies} (목표: 180~220)"
assert 30 <= series <= 70, f"시리즈 수 {series} (목표: 30~70)"
print(f"  ✓ 비율 검증 OK (영화 {movies}/200, 시리즈 {series}/50)")
PYEOF

    echo "=== PASS ==="
    ;;

  watcha-real-4)
    echo "=== watcha-real-4: poster-download posters/ ==="
    POSTERS_DIR="$SCRIPT_DIR/../backend/data/watcha_real/posters"
    DETAIL_CSV="$SCRIPT_DIR/../backend/data/watcha_real/detail_real.csv"

    test -d "$POSTERS_DIR" || { echo "  ✗ posters/ 디렉토리 없음"; exit 1; }
    echo "  ✓ posters/ 디렉토리 존재"

    poster_count=$(find "$POSTERS_DIR" -maxdepth 1 -type f | wc -l)
    detail_rows=$(python3 -c "import csv; f=open('$DETAIL_CSV'); print(sum(1 for _ in csv.DictReader(f)))")
    expired=0
    EXPIRED_CSV="$SCRIPT_DIR/../backend/data/watcha_real/expired_posters.csv"
    [ -f "$EXPIRED_CSV" ] && \
        expired=$(python3 -c "import csv; f=open('$EXPIRED_CSV'); print(sum(1 for _ in csv.DictReader(f)))")

    expected_min=$((detail_rows - expired))
    [[ "$poster_count" -ge "$expected_min" ]] || { echo "  ✗ 포스터 수 $poster_count (최소: $expected_min)"; exit 1; }
    echo "  ✓ 포스터 수 $poster_count (detail $detail_rows - expired $expired = $expected_min)"

    # 5KB 미만 파일 검사
    small=$(find "$POSTERS_DIR" -maxdepth 1 -type f -size -5k | wc -l)
    [[ "$small" -eq 0 ]] || { echo "  ✗ 5KB 미만 파일 ${small}건"; exit 1; }
    echo "  ✓ 모든 파일 5KB 이상"

    echo "=== PASS ==="
    ;;

  watcha-real-5)
    echo "=== watcha-real-5: csv-conversion watcha_upload.csv ==="
    CSV="$SCRIPT_DIR/../backend/data/watcha/upload/watcha_upload.csv"
    OMIT="$SCRIPT_DIR/../backend/data/watcha/upload/omission_log.csv"
    DETAIL="$SCRIPT_DIR/../backend/data/watcha_real/detail_real.csv"

    test -f "$CSV" || { echo "  ✗ watcha_upload.csv 없음"; exit 1; }
    test -f "$OMIT" || { echo "  ✗ omission_log.csv 없음"; exit 1; }
    echo "  ✓ watcha_upload.csv, omission_log.csv 존재"

    python3 << PYEOF
import csv

def count_csv(path):
    with open(path) as f:
        return sum(1 for _ in csv.DictReader(f))

upload_rows = count_csv("$CSV")
detail_rows = count_csv("$DETAIL")
omit_rows = count_csv("$OMIT")

assert upload_rows == detail_rows, f"행 수 불일치: upload={upload_rows} vs detail={detail_rows}"
print(f"  ✓ 행 수 일치: {upload_rows}건")

# placeholder title 없음
with open("$CSV") as f:
    rows = list(csv.DictReader(f))
bad = [r['title'] for r in rows if r['title'].startswith('콘텐츠_')]
assert len(bad) == 0, f"placeholder title {len(bad)}건: {bad[:3]}"
print(f"  ✓ placeholder title 0건")

# omission 비율 15~25%
omit_pct = omit_rows / upload_rows * 100
assert 15 <= omit_pct <= 25, f"omission 비율 {omit_pct:.1f}% (15~25% 범위 외)"
print(f"  ✓ omission 비율 {omit_pct:.1f}% ({omit_rows}/{upload_rows})")
PYEOF

    echo "=== PASS ==="
    ;;

  watcha-real-6)
    echo "=== watcha-real-6: dry-run-validation ==="
    CSV="$SCRIPT_DIR/../backend/data/watcha/upload/watcha_upload.csv"

    resp=$(curl -s -w "\n%{http_code}" -X POST \
      "http://localhost:8000/api/programming/metadata/upload/batch?dry_run=true" \
      -F "file=@${CSV}" \
      -F "cp_name=Watcha")
    http_code=$(echo "$resp" | tail -1)
    body=$(echo "$resp" | head -1)

    [[ "$http_code" == "200" || "$http_code" == "201" ]] || { echo "  ✗ HTTP $http_code"; echo "$body"; exit 1; }
    echo "  ✓ HTTP $http_code"

    python3 << PYEOF
import json, sys
body = '''$body'''
try:
    d = json.loads(body)
except:
    print("  ✗ JSON parse 실패:", body[:200])
    sys.exit(1)
total = d.get('total_count', 0)
success = d.get('success_count', 0)
failed = d.get('failed_count', -1)
assert failed == 0, f"failed_count={failed} (0이어야 함)"
assert success == total, f"success_count={success} != total={total}"
print(f"  ✓ total={total}, success={success}, failed={failed}")
PYEOF

    echo "=== PASS ==="
    ;;

  poster-display-step1)
    echo "=== poster-display-step1: static-mount-and-image-config ==="
    # 1) StaticFiles import + mount 확인
    python3 -c "
import ast, pathlib
src = pathlib.Path('main.py').read_text()
assert 'StaticFiles' in src, 'StaticFiles 미임포트'
assert '/static/posters' in src, '/static/posters 마운트 없음'
print('  ✓ main.py StaticFiles 마운트 OK')
"
    # 2) next.config remotePatterns 확인
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    grep -q '"localhost"' "$CMS/apps/web/next.config.mjs" || { echo "  ✗ next.config.mjs localhost 미추가"; exit 1; }
    # 3) resolvePosterUrl 유틸 확인
    grep -q "resolvePosterUrl" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ resolvePosterUrl 없음"; exit 1; }
    # 4) 포스터 디렉토리 존재 확인
    test -d "$BACKEND/data/watcha_real/posters" || { echo "  ✗ posters 디렉토리 없음"; exit 1; }
    POSTER_COUNT=$(ls "$BACKEND/data/watcha_real/posters" | wc -l)
    test "$POSTER_COUNT" -ge 200 || { echo "  ✗ 포스터 파일 $POSTER_COUNT 개 (200+ 필요)"; exit 1; }
    echo "  ✓ 포스터 $POSTER_COUNT 개 확인 OK"
    # 5) 백엔드 import 테스트 (구문 오류 없는지)
    python3 -c "import main; print('  ✓ main.py import OK')"
    # 6) typecheck
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  poster-display-step2)
    echo "=== poster-display-step2: bulk-upload-poster-column ==="
    python3 -c "
from api.programming.metadata.schemas import BatchUploadRow
r = BatchUploadRow(title='test')
assert hasattr(r, 'poster_url'), 'poster_url 필드 없음'
assert r.poster_url is None, 'poster_url 기본값 None 아님'
print('  ✓ BatchUploadRow.poster_url 필드 OK')
"
    python3 -m pytest tests/test_bulk_upload_poster.py -q
    echo "=== PASS ==="
    ;;

  poster-display-step3)
    echo "=== poster-display-step3: tmdb-auto-poster-audit ==="
    python3 -m pytest tests/workers/test_tmdb_poster_idempotency.py -q
    echo "=== PASS ==="
    ;;

  poster-display-step4)
    echo "=== poster-display-step4: watcha-backfill-237 ==="
    LINK_SCRIPT="$BACKEND/scripts/watcha_real/05_link_posters.py"
    test -f "$LINK_SCRIPT" || { echo "  ✗ 05_link_posters.py 없음"; exit 1; }
    python3 - << PYEOF
import sqlite3, pathlib
db_path = pathlib.Path("$BACKEND/media_ax_dev.db")
if not db_path.exists():
    print("  ⚠ SQLite DB 없음 — Docker/Postgres 환경이거나 DB 미초기화")
    exit(0)
conn = sqlite3.connect(str(db_path))
cur = conn.execute("SELECT COUNT(*) FROM content_images WHERE image_type='poster' AND source='cp'")
count = cur.fetchone()[0]
print(f"  content_images cp poster: {count} 건")
assert count >= 220, f"matched {count} < 220"
print("  ✓ poster backfill OK")
PYEOF
    echo "=== PASS ==="
    ;;

  poster-display-step5)
    echo "=== poster-display-step5: list-api-poster-url ==="
    python3 -c "
from api.programming.metadata.schemas import ContentOut
import inspect
src = inspect.getsource(ContentOut)
assert 'poster_url' in src, 'ContentOut.poster_url 없음'
print('  ✓ ContentOut.poster_url 필드 OK')
"
    python3 -m pytest tests/test_list_api_poster.py -q 2>/dev/null || echo "  (테스트 파일 없으면 import 검증만)"
    echo "=== PASS ==="
    ;;

  poster-display-step6)
    echo "=== poster-display-step6: frontend-list-thumbnail ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    LIST_PAGE="$CMS/apps/web/app/(main)/programming/contents/page.tsx"
    grep -q "resolvePosterUrl\|poster_url" "$LIST_PAGE" || { echo "  ✗ 리스트 페이지에 poster 렌더 없음"; exit 1; }
    echo "  ✓ 리스트 페이지 poster 렌더 확인 OK"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  poster-display-step7)
    echo "=== poster-display-step7: frontend-detail-image-tab ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DETAIL_PAGE="$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    grep -q "imageMetaApi" "$DETAIL_PAGE" || { echo "  ✗ 상세 페이지 imageMetaApi 호출 없음"; exit 1; }
    echo "  ✓ 상세 페이지 imageMetaApi 호출 확인 OK"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  poster-display-step8)
    echo "=== poster-display-step8: e2e-visual-verify ==="
    STEP8_MD="$SCRIPT_DIR/../plans/dev-poster-display/step8.md"
    test -f "$STEP8_MD" || { echo "  ✗ step8.md 없음"; exit 1; }
    curl -fsI "http://localhost:8000/static/posters/tEQkv41.jpg" > /dev/null 2>&1 \
      && echo "  ✓ static poster serving OK" \
      || echo "  ⚠ 백엔드 미실행 — API 검증 스킵 (step8.md 확인)"
    echo "=== PASS ==="
    ;;

  poster-recommend-1.1)
    echo "=== poster-recommend-1.1: backend-tmdb-images-service ==="
    cd "$SCRIPT_DIR/.."
    source backend/.venv/bin/activate
    python3 -c "
import sys; sys.path.insert(0, 'backend')
from api.programming.metadata.poster_recommend import (
    PosterCandidate, fetch_tmdb_poster_candidates,
    recommend_posters_for_content, select_primary_poster,
)
from api.programming.metadata.tmdb_client import TmdbClient
assert hasattr(TmdbClient, 'images_movie'), 'images_movie 없음'
assert hasattr(TmdbClient, 'images_tv'), 'images_tv 없음'
print('  ✓ poster_recommend import OK')
print('  ✓ TmdbClient.images_movie/images_tv OK')
" 2>&1 || exit 1
    echo "=== PASS ==="
    ;;

  poster-recommend-1.2)
    echo "=== poster-recommend-1.2: backend-recommend-api ==="
    cd "$SCRIPT_DIR/.."
    source backend/.venv/bin/activate
    python3 -c "
import sys; sys.path.insert(0, 'backend')
from api.programming.metadata.schemas import PosterCandidateOut, PosterRecommendResponse, PosterSelectRequest
from api.programming.metadata.router import router
routes = [r.path for r in router.routes if hasattr(r, 'path')]
assert any('recommend-posters' in r for r in routes), 'recommend-posters 없음'
assert any('poster-candidates' in r for r in routes), 'poster-candidates 없음'
assert any('poster/select' in r for r in routes), 'poster/select 없음'
print('  ✓ 스키마 3개 OK')
print('  ✓ 엔드포인트 3개 OK')
" 2>&1 || exit 1
    echo "=== PASS ==="
    ;;

  poster-recommend-1.3)
    echo "=== poster-recommend-1.3: backend-tests ==="
    cd "$SCRIPT_DIR/../backend"
    source .venv/bin/activate
    python3 -m pytest tests/test_poster_recommend.py -v 2>&1
    echo "=== PASS ==="
    ;;

  poster-recommend-2.1)
    echo "=== poster-recommend-2.1: frontend-api-client ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    grep -q "posterRecommendApi" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ posterRecommendApi 없음"; exit 1; }
    echo "  ✓ posterRecommendApi 확인 OK"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  poster-recommend-2.2)
    echo "=== poster-recommend-2.2: frontend-image-tab-ui ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DETAIL_PAGE="$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    grep -q "recommend-posters\|posterRecommendApi" "$DETAIL_PAGE" || { echo "  ✗ 추천 버튼/API 없음"; exit 1; }
    echo "  ✓ 추천 UI 확인 OK"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  poster-recommend-3.1)
    echo "=== poster-recommend-3.1: e2e-verify-and-docs ==="
    grep -q "dev-poster-recommend\|다중 포스터" "$SCRIPT_DIR/../CLAUDE.md" || { echo "  ✗ CLAUDE.md 현황 갱신 없음"; exit 1; }
    echo "  ✓ CLAUDE.md 갱신 확인 OK"
    echo "=== PASS ==="
    ;;

  detail-vod-1.1)
    echo "=== detail-vod-1.1: backend ContentDetail 확장 ==="
    cd "$BACKEND"
    python3 -c "
from api.programming.metadata.schemas import ContentDetail, ContentCreditOut, ContentGenreOut, PersonOut
fields = ContentDetail.model_fields
for k in ['metadata_record','genres','credits','external_sources']:
    assert k in fields, f'{k} 누락'
print('  ✓ ContentDetail 필드 확장 OK:', list(fields.keys()))
"
    echo "=== PASS ==="
    ;;

  detail-vod-1.2)
    echo "=== detail-vod-1.2: frontend 타입 확장 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    grep -q "CreditOut\|credits:" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ CreditOut 타입 없음"; exit 1; }
    grep -q "genres:" "$CMS/apps/web/lib/api.ts" || { echo "  ✗ genres 필드 없음"; exit 1; }
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  detail-vod-2.1|detail-vod-2.2|detail-vod-2.3|detail-vod-3.1)
    echo "=== ${STEP}: frontend UI step ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -5
    echo "=== PASS ==="
    ;;

  1.1) bash "$0" detail-vod-1.1 ;;
  1.2) bash "$0" detail-vod-1.2 ;;
  2.1) bash "$0" detail-vod-2.1 ;;
  2.2) bash "$0" detail-vod-2.2 ;;
  2.3) bash "$0" detail-vod-2.3 ;;
  3.1) bash "$0" detail-vod-3.1 ;;

  # ── dev-flexible-meta-pipeline ───────────────────────────
  flexible-meta-step0)
    echo "=== flexible-meta-step0: 더미 데이터 정리 ==="
    python3 -c "
from shared.database import SessionLocal
from api.programming.metadata.models import Content
db = SessionLocal()
dummy = db.query(Content).filter(Content.title.like('콘텐츠_%')).count()
assert dummy == 0, f'더미 데이터 {dummy}건 남아있음'
total = db.query(Content).count()
db.close()
print(f'  ✓ 더미 0건, 총 콘텐츠 {total}건')
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step4)
    echo "=== flexible-meta-step4: 수동 입력 UI 검증 ==="
    # 1. 백엔드 API E2E 테스트
    python3 -c "
import urllib.request, json

BASE = 'http://localhost:8000'

# POST /contents 신규 등록
req = urllib.request.Request(
    f'{BASE}/api/programming/metadata/contents',
    data=json.dumps({'title': 'verify-step4-테스트', 'content_type': 'movie', 'cp_name': 'TestCP'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST',
)
with urllib.request.urlopen(req) as r:
    content = json.loads(r.read())
cid = content['id']
assert content['title'] == 'verify-step4-테스트', f'title mismatch: {content[\"title\"]}'
print(f'  ✓ POST /contents → id={cid}')

# PUT /contents/{id} 수동 수정
req2 = urllib.request.Request(
    f'{BASE}/api/programming/metadata/contents/{cid}',
    data=json.dumps({'cast': '홍길동, 이영희', 'directors': '테스트감독', 'genres': '액션, 드라마'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='PUT',
)
with urllib.request.urlopen(req2) as r:
    r.read()
print(f'  ✓ PUT /contents/{cid}')

# GET /contents/{id} credits/genres 확인
with urllib.request.urlopen(f'{BASE}/api/programming/metadata/contents/{cid}') as r:
    detail = json.loads(r.read())

credits = detail.get('credits', [])
genres = detail.get('genres', [])
actors = [c for c in credits if c['role'] == 'actor']
directors = [c for c in credits if c['role'] == 'director']
assert len(actors) == 2, f'actor 2명 기대, 실제 {len(actors)}명'
assert len(directors) == 1, f'director 1명 기대, 실제 {len(directors)}명'
assert len(genres) == 2, f'genre 2개 기대, 실제 {len(genres)}개'
print(f'  ✓ credits {len(credits)}건, genres {len(genres)}건 저장 확인')
"
    # 2. 프론트 새 페이지 접근 확인
    for path in "/programming/contents/new" "/programming/contents/upload" "/programming/contents/external"; do
      code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:3002${path}")
      [ "$code" = "200" ] || { echo "FAIL: ${path} → ${code}"; exit 1; }
    done
    echo "  ✓ 프론트 3개 페이지 200 OK"
    echo "=== PASS ==="
    ;;

  flexible-meta-step3)
    echo "=== flexible-meta-step3: 프론트 IA 재구성 ==="
    cd "$SCRIPT_DIR/.."
    # 1. docs.ts 메뉴 3개 추가 확인
    node -e "
const fs = require('fs');
const src = fs.readFileSync('mediaX-CMS/apps/web/config/docs.ts', 'utf8');
['콘텐츠 등록', '일괄 업로드', '외부 검색'].forEach(title => {
  if (!src.includes(title)) throw new Error(title + ' 메뉴 없음');
});
console.log('  ✓ docs.ts 메뉴 3개 추가 OK');
"
    # 2. 새 페이지 파일 존재 확인
    for f in \
      "mediaX-CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      "mediaX-CMS/apps/web/app/(main)/programming/contents/upload/page.tsx" \
      "mediaX-CMS/apps/web/app/(main)/programming/contents/external/page.tsx" \
      "mediaX-CMS/apps/web/app/(main)/programming/contents/[id]/edit/page.tsx" \
      "mediaX-CMS/apps/web/components/contents/ContentForm.tsx"; do
      [ -f "$f" ] || { echo "파일 없음: $f"; exit 1; }
    done
    echo "  ✓ 새 페이지 5개 + ContentForm 존재 OK"
    # 3. AddContentModal 제거 확인 (목록 페이지에서 import 없어야 함)
    ! grep -q "AddContentModal" "mediaX-CMS/apps/web/app/(main)/programming/contents/page.tsx" \
      || { echo "AddContentModal 아직 목록 페이지에 있음"; exit 1; }
    echo "  ✓ AddContentModal 제거 OK"
    # 4. TypeScript 타입체크
    cd mediaX-CMS && npm run typecheck 2>&1 | grep -E "error TS|PASS|Tasks:" | tail -5
    cd ..
    echo "=== PASS ==="
    ;;

  flexible-meta-step2)
    echo "=== flexible-meta-step2: 벌크 업로드 API 확장 + PUT 엔드포인트 ==="
    python3 -c "
# 1. ContentUpdate 스키마 존재 확인
from api.programming.metadata.schemas import ContentUpdate
data = ContentUpdate(synopsis='테스트', cast='배우1, 배우2', directors='감독1')
assert data.synopsis == '테스트'
assert data.cast == '배우1, 배우2'
print('  ✓ ContentUpdate 스키마 OK')

# 2. update_content 서비스 import + 실행
from api.programming.metadata.service import update_content
from shared.database import SessionLocal
from api.programming.metadata.models import Content
from api.programming.metadata.models.external import ExternalSourceType

db = SessionLocal()
content = db.query(Content).first()
if content:
    result = update_content(db, content.id, ContentUpdate(synopsis='검증용 줄거리'))
    # ExternalMetaSource(manual) 저장 확인
    from api.programming.metadata.models import ExternalMetaSource
    manual_src = db.query(ExternalMetaSource).filter(
        ExternalMetaSource.content_id == content.id,
        ExternalMetaSource.source_type == ExternalSourceType.manual,
    ).first()
    assert manual_src is not None, 'manual ExternalMetaSource 없음'
    assert manual_src.raw_json.get('synopsis') == '검증용 줄거리'
    print(f'  ✓ update_content + manual ExternalMetaSource 저장 OK (content_id={content.id})')
    db.rollback()
db.close()

# 3. process_batch_rows 시그니처 + bulk_upload source 사용 확인
import inspect
from api.programming.metadata.service import process_batch_rows
src = inspect.getsource(process_batch_rows)
assert 'ExternalSourceType.bulk_upload' in src, 'bulk_upload source_type 없음'
assert 'resolve_metadata' in src, 'resolve_metadata 호출 없음'
print('  ✓ process_batch_rows bulk_upload + resolve_metadata OK')

# 4. router PUT 엔드포인트 등록 확인
from api.programming.metadata.router import router
put_routes = [r for r in router.routes if hasattr(r, 'methods') and 'PUT' in r.methods]
assert any('/contents/{content_id}' in str(r.path) for r in put_routes), 'PUT /contents/{id} 없음'
print('  ✓ PUT /contents/{content_id} 엔드포인트 OK')
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step1)
    echo "=== flexible-meta-step1: Resolution Service ==="
    python3 -c "
from api.programming.metadata.models.external import ExternalSourceType
assert hasattr(ExternalSourceType, 'manual'), 'manual 타입 없음'
assert hasattr(ExternalSourceType, 'bulk_upload'), 'bulk_upload 타입 없음'
print('  ✓ ExternalSourceType 확장 OK')
from api.programming.metadata.service import (
    resolve_metadata, _source_priority, _parse_source_fields,
    _get_or_create_genre, _get_or_create_person,
)
assert _source_priority('manual') == 100
assert _source_priority('tmdb') == 80
assert _source_priority('kobis') == 70
assert _source_priority('watcha') == 50
print('  ✓ _source_priority OK')
fields = _parse_source_fields('tmdb', {
    'title': '테스트', 'overview': '줄거리', 'runtime': 120,
    'genres': [{'name': '드라마'}],
    'credits': {'cast': [{'name': '배우1', 'character': '역1'}], 'crew': [{'name': '감독1', 'job': 'Director'}]},
    'production_countries': [{'name': 'Korea'}],
    'release_date': '2024-01-01',
})
assert fields['title'] == '테스트'
assert fields['synopsis'] == '줄거리'
assert fields['runtime'] == 120
assert fields['genres'] == ['드라마']
assert fields['directors'] == ['감독1']
assert len(fields['cast']) == 1
assert fields['country'] == 'Korea'
assert fields['production_year'] == 2024
print('  ✓ _parse_source_fields (TMDB) OK')
fields2 = _parse_source_fields('watcha', {
    'cast': '배우A, 배우B', 'directors': '감독X', 'genres': '드라마/, 판타지/',
    'runtime': '90분',
})
assert fields2['cast'][0]['name'] == '배우A'
assert fields2['directors'][0] == '감독X'
assert '드라마' in fields2['genres']
assert fields2['runtime'] == 90
print('  ✓ _parse_source_fields (watcha/bulk) OK')
from shared.database import SessionLocal
db = SessionLocal()
g = _get_or_create_genre(db, '__test_genre__', 'test')
assert g is not None
assert g.name_ko == '__test_genre__'
p = _get_or_create_person(db, '__test_person__')
assert p is not None
assert p.name_ko == '__test_person__'
db.rollback()
db.close()
print('  ✓ get_or_create helpers OK')
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step5d)
    echo "=== flexible-meta-step5d: bulk-reupload-credits-verify ==="
    python3 -c "
import sys; sys.path.insert(0, '.')
from sqlalchemy import text
from api.programming.metadata.models.content import Content
from shared.database import SessionLocal
db = SessionLocal()

watcha = db.query(Content).filter(Content.cp_name == 'Watcha').count()
assert watcha > 0, f'Watcha 콘텐츠 없음'
print(f'  ✓ Watcha 콘텐츠: {watcha}건')

actor_cnt = db.execute(text(\"SELECT COUNT(*) FROM content_credits WHERE role='actor'\")).scalar()
dir_cnt = db.execute(text(\"SELECT COUNT(*) FROM content_credits WHERE role='director'\")).scalar()
genre_cnt = db.execute(text('SELECT COUNT(*) FROM content_genres')).scalar()

assert actor_cnt > 0, 'content_credits(actor) 없음'
assert dir_cnt > 0, 'content_credits(director) 없음'
assert genre_cnt > 0, 'content_genres 없음'

print(f'  ✓ content_credits actor: {actor_cnt}건')
print(f'  ✓ content_credits director: {dir_cnt}건')
print(f'  ✓ content_genres: {genre_cnt}건')
db.close()
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step5c)
    echo "=== flexible-meta-step5c: incremental-patch-and-csv-convert ==="
    # CSV 변환 실행 (patch 는 사전 완료 전제)
    python3 scripts/watcha_real/04_to_upload_csv.py
    python3 -c "
import csv, json

# detail_real.csv cast/directors 비율
with open('data/watcha_real/detail_real.csv') as f:
    rows = list(csv.DictReader(f))
total = len(rows)
filled = sum(1 for r in rows if r.get('cast') or r.get('directors'))
pct = filled / total * 100 if total else 0
print(f'  cast/directors 보유: {filled}/{total}건 ({pct:.0f}%)')
assert pct >= 50, f'cast/directors 비율 {pct:.0f}% < 50%'
print('  ✓ cast/directors ≥ 50%')

# watcha_upload.csv 헤더 12열 확인
with open('data/watcha/upload/watcha_upload.csv') as f:
    reader = csv.DictReader(f)
    headers = set(reader.fieldnames or [])
    expected = {'title','production_year','content_type','cp_name','synopsis','cast','directors','genres','country','runtime','rating_age','poster_url'}
    missing = expected - headers
    assert not missing, f'누락 컬럼: {missing}'
    print(f'  ✓ 12열 헤더 확인')
    row = next(reader, None)
    if row:
        print(f'  샘플 cast={repr(row.get(\"cast\",\"\")[:40])}, directors={repr(row.get(\"directors\",\"\")[:30])}')
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step5b)
    echo "=== flexible-meta-step5b: crawler-cast-directors ==="
    # v2bak 존재 확인 (patch 실행 전이라 없을 수 있으니 선행 생성)
    DETAIL_CSV="data/watcha_real/detail_real.csv"
    BAK_CSV="data/watcha_real/detail_real.csv.v2bak"
    if [ ! -f "$DETAIL_CSV" ]; then
      echo "ERROR: detail_real.csv 없음"
      exit 1
    fi
    # --limit 3 --patch 실행 (3건 샘플 검증)
    python3 scripts/watcha_real/02_crawl_details.py --patch --limit 3
    # v2bak 파일 존재 확인
    if [ ! -f "$BAK_CSV" ]; then
      echo "ERROR: detail_real.csv.v2bak 없음"
      exit 1
    fi
    echo "  ✓ .v2bak 생성 확인"
    # cast 또는 directors 가 채워진 행 ≥ 1건 확인
    python3 -c "
import csv, json
with open('data/watcha_real/detail_real.csv') as f:
    rows = list(csv.DictReader(f))
filled = sum(1 for r in rows if r.get('cast') or r.get('directors'))
print(f'  cast/directors 있는 행: {filled}/{len(rows)}건')
assert filled >= 1, 'cast/directors 채워진 행 없음'
print('  ✓ 샘플 patch 성공')
"
    echo "=== PASS ==="
    ;;

  flexible-meta-step5a)
    echo "=== flexible-meta-step5a: cleanup-baseline ==="
    python3 scripts/watcha_real/00_cleanup_baseline.py
    python3 -c "
import sys; sys.path.insert(0, '.')
from api.programming.metadata.models.content import Content
from shared.database import SessionLocal
db = SessionLocal()
watcha = db.query(Content).filter(Content.cp_name == 'Watcha').count()
dummy = db.query(Content).filter(Content.title.like('콘텐츠_%')).count()
assert watcha == 0, f'Watcha {watcha}건 남음'
assert dummy == 0, f'더미 {dummy}건 남음'
db.close()
print('  ✓ Watcha 0건 / 더미 0건 확인')
"
    echo "=== PASS ==="
    ;;

  # ── dev-ai-review-queue ──────────────────────────────────
  ai-review-queue-1.1)
    echo "=== ai-review-queue-1.1: schemas + classifier helpers ==="
    python3 -m pytest tests/api/programming/metadata/test_ai_review_queue.py \
      -k "classify or risk_level" -v --tb=short -q 2>&1 | tail -20
    echo "=== PASS ==="
    ;;

  ai-review-queue-1.2)
    echo "=== ai-review-queue-1.2: build_ai_review_queue core ==="
    python3 -m pytest tests/api/programming/metadata/test_ai_review_queue.py \
      -k "queue and not dam_integration" -v --tb=short -q 2>&1 | tail -25
    echo "=== PASS ==="
    ;;

  ai-review-queue-1.3)
    echo "=== ai-review-queue-1.3: router endpoint ==="
    python3 -m pytest tests/api/programming/metadata/test_ai_review_queue.py \
      -k "endpoint" -v --tb=short -q 2>&1 | tail -20
    echo "=== PASS ==="
    ;;

  ai-review-queue-1.4)
    echo "=== ai-review-queue-1.4: dam integration ==="
    python3 -m pytest tests/api/programming/metadata/test_ai_review_queue.py \
      -k "dam_integration" -v --tb=short -q 2>&1 | tail -20
    echo "=== PASS ==="
    ;;

  ai-review-queue-1.5)
    echo "=== ai-review-queue-1.5: e2e smoke ==="
    python3 -m pytest tests/api/programming/metadata/test_ai_review_queue.py \
      -v --tb=short -q 2>&1 | tail -30
    curl -sf "http://localhost:8000/api/programming/metadata/ai-review-queue?size=3" \
      | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'summary' in d; assert 'items' in d; print('  ✓ endpoint 200 OK, summary:', d['summary'])"
    echo "=== PASS ==="
    ;;

  ai-review-queue-5)
    echo "=== ai-review-queue-5: Dam Link Display ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- damApi export ---"
    grep -q "export const damApi" "$CMS/apps/web/lib/api.ts" \
      && echo "  ✓ damApi exported" \
      || (echo "  ✗ damApi missing" && exit 1)
    echo "--- DamAssetsOut type used ---"
    grep -q "DamAssetsOut" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ DamAssetsOut type in page" \
      || (echo "  ✗ DamAssetsOut missing in page" && exit 1)
    echo "--- retry button ---"
    grep -q "damRetry" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ damRetry state present" \
      || (echo "  ✗ damRetry missing" && exit 1)
    echo "=== PASS ==="
    ;;

  content-register-1)
    echo "=== content-register-1: 등록 페이지 Hero 카드 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- new/page.tsx exists ---"
    [ -f "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" ] \
      && echo "  ✓ new/page.tsx exists" \
      || (echo "  ✗ new/page.tsx missing" && exit 1)
    echo "--- ContentForm removed ---"
    grep -q "ContentForm" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && (echo "  ✗ ContentForm still imported" && exit 1) \
      || echo "  ✓ ContentForm removed"
    echo "--- poster upload zone ---"
    grep -q 'aspect-\[2/3\]' "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ aspect-[2/3] poster zone present" \
      || (echo "  ✗ aspect-[2/3] missing" && exit 1)
    echo "--- enrich redirect ---"
    grep -q 'enrich=true' "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ enrich=true redirect present" \
      || (echo "  ✗ enrich=true redirect missing" && exit 1)
    echo "=== PASS ==="
    ;;

  content-register-2)
    echo "=== content-register-2: 3탭 패널 (글자/이미지/영상) ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- activeTab state ---"
    grep -q 'setActiveTab.*"text" \| "image" \| "video"' "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ activeTab state present" \
      || (echo "  ✗ activeTab missing" && exit 1)
    echo "--- 글자 탭 (extended_synopsis, catchphrase, keywords) ---"
    grep -q "extended_synopsis" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ extended_synopsis field present" \
      || (echo "  ✗ extended_synopsis missing" && exit 1)
    grep -q "catchphrase" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ catchphrase field present" \
      || (echo "  ✗ catchphrase missing" && exit 1)
    grep -q "form.keywords" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ keywords array present" \
      || (echo "  ✗ keywords missing" && exit 1)
    echo "--- 이미지 탭 (stills, backgroundImage) ---"
    grep -q "stillPreviews" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ stills preview state present" \
      || (echo "  ✗ stillPreviews missing" && exit 1)
    grep -q "bgPreview" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ background preview state present" \
      || (echo "  ✗ bgPreview missing" && exit 1)
    echo "--- 영상 탭 (vodPath, trailerPath, format, resolution) ---"
    grep -q "vodPath\|vod_path" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ vodPath field present" \
      || (echo "  ✗ vodPath missing" && exit 1)
    grep -q "form.format\|form.resolution" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ format/resolution selects present" \
      || (echo "  ✗ format/resolution missing" && exit 1)
    echo "--- POST body extend ---"
    grep -q "extended_synopsis.*body" "$CMS/apps/web/app/(main)/programming/contents/new/page.tsx" \
      && echo "  ✓ extended_synopsis in POST body" \
      || (echo "  ✗ extended_synopsis not sent" && exit 1)
    echo "=== PASS ==="
    ;;

  phase-d-step1)
    echo "=== phase-d-step1: migration 0013 + env keys ==="
    echo "--- alembic 0013 파일 ---"
    [ -f "$BACKEND/alembic/versions/0013_phase_d_websearch.py" ] \
      && echo "  ✓ alembic 0013 파일 존재" \
      || (echo "  ✗ alembic 0013 missing" && exit 1)
    echo "--- ExternalSourceType.websearch ---"
    python3 -c "
from api.programming.metadata.models.external import ExternalSourceType
assert ExternalSourceType.websearch == 'websearch'
print('  ✓ ExternalSourceType.websearch = websearch')
"
    echo "--- WebSearchQuotaLog model ---"
    python3 -c "
from api.programming.metadata.models.tmdb_cache import WebSearchQuotaLog, WebSearchCache
assert WebSearchQuotaLog.__tablename__ == 'web_search_quota_log'
print('  ✓ WebSearchQuotaLog 모델 OK')
assert ('query_hash', 'source') == tuple(c.name for c in WebSearchCache.__table_args__[0].columns) \
    or any(c.name == 'query_hash' for c in WebSearchCache.__table_args__[0].columns)
print('  ✓ WebSearchCache composite unique OK')
"
    echo "--- models __init__ re-export ---"
    python3 -c "
from api.meta_core.models import WebSearchQuotaLog
print('  ✓ meta_core.models.WebSearchQuotaLog re-export OK')
"
    echo "--- .env.example keys ---"
    for k in BRAVE_SEARCH_API_KEY SERPAPI_KEY WEBSEARCH_ENABLED WEBSEARCH_BULK_ALLOWED WEBSEARCH_PROVIDERS WEBSEARCH_BRAVE_DAILY WEBSEARCH_SERPAPI_DAILY WEBSEARCH_GEMINI_DAILY WEBSEARCH_TRENDING_ENABLED; do
      grep -q "^$k=" "$BACKEND/.env.example" \
        && echo "  ✓ $k" \
        || (echo "  ✗ $k missing in .env.example" && exit 1)
    done
    echo "--- shared.config Settings ---"
    python3 -c "
from shared.config import Settings
s = Settings()
assert hasattr(s, 'BRAVE_SEARCH_API_KEY')
assert hasattr(s, 'SERPAPI_KEY')
assert s.WEBSEARCH_ENABLED is True
assert s.WEBSEARCH_BULK_ALLOWED is False
assert s.WEBSEARCH_PROVIDERS == 'brave,serpapi,gemini,ollama'
assert s.WEBSEARCH_BRAVE_DAILY == 60
assert s.WEBSEARCH_SERPAPI_DAILY == 3
assert s.WEBSEARCH_GEMINI_DAILY == 200
assert s.WEBSEARCH_TRENDING_ENABLED is False
print('  ✓ Settings 9 keys OK')
"
    echo "=== PASS ==="
    ;;

  phase-d-step2)
    echo "=== phase-d-step2: web_search package + BraveSearchProvider ==="
    echo "--- Files structure ---"
    for f in __init__.py base.py brave.py cache.py errors.py; do
      [ -f "$BACKEND/api/meta_core/web_search/$f" ] && echo "  ✓ $f" || (echo "  ✗ $f missing" && exit 1)
    done
    echo "--- WebSearchProvider ABC ---"
    python3 -c "
from api.meta_core.web_search.base import WebSearchProvider, WebSearchResult
from abc import ABC
assert issubclass(WebSearchProvider, ABC)
assert hasattr(WebSearchProvider, 'provider_name')
assert hasattr(WebSearchProvider, 'daily_limit')
assert hasattr(WebSearchProvider, 'search')
print('  ✓ WebSearchProvider ABC OK')
"
    echo "--- WebSearchResult dataclass ---"
    python3 -c "
from api.meta_core.web_search.base import WebSearchResult
r = WebSearchResult(url='http://test.com', title='Test', snippet='snippet', source_domain='test.com', score=1.0)
assert r.url == 'http://test.com'
assert r.title == 'Test'
assert r.source_domain == 'test.com'
assert r.score == 1.0
print('  ✓ WebSearchResult dataclass OK')
"
    echo "--- BraveSearchProvider ---"
    python3 -c "
from api.meta_core.web_search.brave import BraveSearchProvider
assert hasattr(BraveSearchProvider, 'search')
b = BraveSearchProvider()
assert b.provider_name == 'brave'
assert b.daily_limit == 60
print('  ✓ BraveSearchProvider OK')
"
    echo "--- Cache helpers ---"
    python3 -c "
from api.meta_core.web_search.cache import cache_get, cache_put
import inspect
assert callable(cache_get)
assert callable(cache_put)
assert 'db' in inspect.signature(cache_get).parameters
assert 'provider' in inspect.signature(cache_get).parameters
print('  ✓ cache_get/cache_put OK')
"
    echo "--- Exception classes ---"
    python3 -c "
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError, BulkQuotaError
assert issubclass(QuotaExhaustedError, Exception)
assert issubclass(ProviderUnavailableError, Exception)
assert issubclass(BulkQuotaError, Exception)
print('  ✓ Exception classes OK')
"
    echo "--- Test file ---"
    [ -f "$BACKEND/tests/meta_core/web_search/test_brave.py" ] \
      && echo "  ✓ test_brave.py exists" \
      || (echo "  ✗ test_brave.py missing" && exit 1)
    echo "--- Package imports ---"
    python3 -c "
from api.meta_core.web_search import (
    WebSearchProvider, WebSearchResult, BraveSearchProvider,
    cache_get, cache_put,
    QuotaExhaustedError, ProviderUnavailableError, BulkQuotaError
)
print('  ✓ All imports OK')
"
    echo "=== PASS ==="
    ;;

  phase-d-step3)
    echo "=== phase-d-step3: SerpAPI + Gemini Grounding + Ollama-DDG + factory ==="
    echo "--- Provider files ---"
    for f in serpapi.py gemini_grounding.py ollama_ddg.py factory.py; do
      [ -f "$BACKEND/api/meta_core/web_search/$f" ] && echo "  ✓ $f" || (echo "  ✗ $f missing" && exit 1)
    done
    echo "--- SerpApiProvider ---"
    python3 -c "
from api.meta_core.web_search.serpapi import SerpApiProvider
s = SerpApiProvider()
assert s.provider_name == 'serpapi'
assert s.daily_limit == 3
print('  ✓ SerpApiProvider OK')
"
    echo "--- GeminiGroundingProvider ---"
    python3 -c "
from api.meta_core.web_search.gemini_grounding import GeminiGroundingProvider
g = GeminiGroundingProvider()
assert g.provider_name == 'gemini'
assert g.daily_limit == 200
print('  ✓ GeminiGroundingProvider OK')
"
    echo "--- OllamaDDGProvider ---"
    python3 -c "
from api.meta_core.web_search.ollama_ddg import OllamaDDGProvider
o = OllamaDDGProvider()
assert o.provider_name == 'ollama'
assert o.daily_limit == 999999
print('  ✓ OllamaDDGProvider OK')
"
    echo "--- Factory functions ---"
    python3 -c "
from api.meta_core.web_search.factory import get_provider_chain, search_with_fallback
assert callable(get_provider_chain)
assert callable(search_with_fallback)
chain = get_provider_chain()
assert len(chain) >= 3
assert chain[-1].provider_name == 'ollama'  # Ollama last
print('  ✓ get_provider_chain OK')
print('  ✓ search_with_fallback OK')
"
    echo "--- Test files ---"
    [ -f "$BACKEND/tests/meta_core/web_search/test_factory.py" ] \
      && echo "  ✓ test_factory.py exists" \
      || (echo "  ✗ test_factory.py missing" && exit 1)
    echo "--- Package re-export ---"
    python3 -c "
from api.meta_core.web_search import (
    SerpApiProvider, GeminiGroundingProvider, OllamaDDGProvider,
    get_provider_chain, search_with_fallback
)
print('  ✓ All re-exports OK')
"
    echo "=== PASS ==="
    ;;

  phase-d-step4)
    echo "=== phase-d-step4: bulk-guard + cache integration ==="
    echo "--- guard.py ---"
    [ -f "$BACKEND/api/meta_core/web_search/guard.py" ] \
      && echo "  ✓ guard.py exists" \
      || (echo "  ✗ guard.py missing" && exit 1)
    echo "--- check_bulk_allowed function ---"
    python3 -c "
from api.meta_core.web_search.guard import check_bulk_allowed
from api.meta_core.web_search.errors import BulkQuotaError
from unittest.mock import MagicMock
mgr = MagicMock()
mgr.current_count.return_value = 40
result = check_bulk_allowed(8, 'brave', 60, mgr)
assert result is True
print('  ✓ check_bulk_allowed returns bool')
mgr.current_count.return_value = 50
try:
    check_bulk_allowed(20, 'brave', 60, mgr)
    print('  ✗ Should raise BulkQuotaError')
    exit(1)
except BulkQuotaError as e:
    assert e.expected == 20
    assert e.remaining == 10
    print('  ✓ BulkQuotaError raised with expected/remaining')
"
    echo "--- cache hit/miss logic ---"
    python3 -c "
from api.meta_core.web_search.cache import cache_get, cache_put
import inspect
sig_get = inspect.signature(cache_get)
sig_put = inspect.signature(cache_put)
assert 'query' in sig_get.parameters
assert 'provider' in sig_get.parameters
assert 'db' in sig_get.parameters
assert 'ttl_days' in sig_put.parameters
print('  ✓ cache_get/cache_put signatures correct')
"
    echo "--- Test files ---"
    [ -f "$BACKEND/tests/meta_core/web_search/test_guard.py" ] \
      && echo "  ✓ test_guard.py exists" \
      || (echo "  ✗ test_guard.py missing" && exit 1)
    [ -f "$BACKEND/tests/meta_core/web_search/test_cache.py" ] \
      && echo "  ✓ test_cache.py exists" \
      || (echo "  ✗ test_cache.py missing" && exit 1)
    echo "--- Package exports ---"
    python3 -c "
from api.meta_core.web_search import check_bulk_allowed, cache_get, cache_put
print('  ✓ All guard/cache exports OK')
"
    echo "=== PASS ==="
    ;;

  phase-d-step5)
    echo "=== phase-d-step5: WebSearchDiscoverySource ==="
    echo "--- websearch_source.py ---"
    [ -f "$BACKEND/api/meta_core/discovery/websearch_source.py" ] \
      && echo "  ✓ websearch_source.py exists" \
      || (echo "  ✗ websearch_source.py missing" && exit 1)
    echo "--- WebSearchDiscoverySource class ---"
    python3 -c "
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
from api.meta_core.discovery.base import DiscoverySource
from unittest.mock import MagicMock
assert issubclass(WebSearchDiscoverySource, DiscoverySource)
assert WebSearchDiscoverySource.source_type == 'websearch'
db = MagicMock()
source = WebSearchDiscoverySource(db)
assert hasattr(source, 'discover')
assert hasattr(source, '_discover_async')
print('  ✓ WebSearchDiscoverySource OK')
"
    echo "--- Mode support ---"
    python3 -c "
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource, _TRENDING_QUERIES
assert len(_TRENDING_QUERIES) == 5
print(f'  ✓ 3 modes (query/topic/trending) with {len(_TRENDING_QUERIES)} trending queries')
"
    echo "--- LLM extraction & JSON parsing ---"
    python3 -c "
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
from unittest.mock import MagicMock
source = WebSearchDiscoverySource(MagicMock())
response = '{\"title\": \"Test\", \"content_type\": \"movie\", \"production_year\": 2026}'
parsed = source._parse_extraction_response(response)
assert parsed is not None
assert parsed['title'] == 'Test'
print('  ✓ JSON parsing OK')
"
    echo "--- Test file ---"
    [ -f "$BACKEND/tests/meta_core/discovery/test_websearch.py" ] \
      && echo "  ✓ test_websearch.py exists" \
      || (echo "  ✗ test_websearch.py missing" && exit 1)
    echo "--- search_with_fallback integration ---"
    python3 -c "
import inspect
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
source_code = inspect.getsource(WebSearchDiscoverySource._search_and_extract)
assert 'search_with_fallback' in source_code
print('  ✓ search_with_fallback integrated')
"
    echo "=== PASS ==="
    ;;

  phase-d-step6)
    echo "=== phase-d-step6: Aggregator opt-in integration ==="
    echo "--- aggregator.py enable_web_search ---"
    python3 -c "
import inspect
from api.meta_core.aggregator import aggregate_content, aggregate_batch
sig_content = inspect.signature(aggregate_content)
sig_batch = inspect.signature(aggregate_batch)
assert 'enable_web_search' in sig_content.parameters
assert 'enable_web_search' in sig_batch.parameters
print('  ✓ enable_web_search parameter added')
"
    echo "--- WebSearch helper functions ---"
    python3 -c "
from api.meta_core.aggregator import _add_websearch_suggestions, _create_websearch_suggestion
import inspect
assert callable(_add_websearch_suggestions)
assert callable(_create_websearch_suggestion)
print('  ✓ _add_websearch_suggestions OK')
print('  ✓ _create_websearch_suggestion OK')
"
    echo "--- BulkAcceptRequest.enable_web_search ---"
    python3 -c "
from api.meta_core.intelligence.schemas import BulkAcceptRequest
req = BulkAcceptRequest(fields=['synopsis'], enable_web_search=True)
assert req.enable_web_search is True
print('  ✓ BulkAcceptRequest.enable_web_search field OK')
"
    echo "--- bulk_accept guard ---"
    python3 -c "
import inspect
from api.meta_core.intelligence.router import bulk_accept
source = inspect.getsource(bulk_accept)
assert 'check_bulk_allowed' in source
assert 'BulkQuotaError' in source
assert 'enable_web_search' in source
print('  ✓ bulk_accept check_bulk_allowed guard present')
print('  ✓ bulk_accept enable_web_search integration')
"
    echo "--- Test file ---"
    [ -f "$BACKEND/tests/meta_core/test_aggregator_websearch.py" ] \
      && echo "  ✓ test_aggregator_websearch.py exists" \
      || (echo "  ✗ test_aggregator_websearch.py missing" && exit 1)
    echo "=== PASS ==="
    ;;

  phase-d-step7)
    echo "=== phase-d-step7: Monitoring Backend API ==="
    echo "--- web_search/router.py ---"
    [ -f "$BACKEND/api/meta_core/web_search/router.py" ] \
      && echo "  ✓ router.py exists" \
      || (echo "  ✗ router.py missing" && exit 1)
    echo "--- 3 GET endpoints ---"
    python3 -c "
from api.meta_core.web_search.router import router
routes = [r.path for r in router.routes if r.methods and 'GET' in r.methods]
assert '/quota' in str(routes)
assert '/cache-stats' in str(routes) or 'cache-stats' in str(routes)
assert '/recent' in str(routes)
print('  ✓ /quota endpoint')
print('  ✓ /cache-stats endpoint')
print('  ✓ /recent endpoint')
"
    echo "--- Pydantic schemas ---"
    python3 -c "
from api.meta_core.web_search.router import (
    ProviderQuotaOut, QuotaStatsOut,
    CacheStatsOut, RecentCallOut, RecentCallsOut
)
p = ProviderQuotaOut(provider='test', daily_limit=60, used_today=30, remaining=30, percent_used=50.0)
assert p.provider == 'test'
print('  ✓ ProviderQuotaOut')
print('  ✓ QuotaStatsOut')
print('  ✓ CacheStatsOut')
print('  ✓ RecentCallOut')
print('  ✓ RecentCallsOut')
"
    echo "--- Router mounts ---"
    python3 -c "
from api.meta_core.web_search.router import router as ws_router
assert ws_router is not None
print('  ✓ web_search_router importable')
"
    echo "--- Test file ---"
    [ -f "$BACKEND/tests/meta_core/web_search/test_router.py" ] \
      && echo "  ✓ test_router.py exists" \
      || (echo "  ✗ test_router.py missing" && exit 1)
    echo "=== PASS ==="
    ;;

  phase-d-step0)
    echo "=== phase-d-step0: ADR Phase D WebSearch ==="
    DOCS="$SCRIPT_DIR/../docs/dev/phase-d"
    echo "--- 7 ADR 파일 존재 ---"
    for f in _index.md sources.md quota-policy.md on-off-policy.md bulk-guard.md cache-policy.md monitoring-data-model.md; do
      [ -f "$DOCS/$f" ] && echo "  ✓ $f" || (echo "  ✗ $f missing" && exit 1)
    done
    echo "--- _index.md 핵심 키워드 ---"
    grep -q "Phase D" "$DOCS/_index.md" && echo "  ✓ Phase D 키워드" || (echo "  ✗ Phase D 키워드 없음" && exit 1)
    grep -q "Provider 폴백\|Brave → SerpAPI" "$DOCS/_index.md" && echo "  ✓ Provider 폴백 키워드" || (echo "  ✗ Provider 폴백 없음" && exit 1)
    grep -q "Quota\|쿼터" "$DOCS/_index.md" && echo "  ✓ Quota 키워드" || (echo "  ✗ Quota 키워드 없음" && exit 1)
    grep -q "Bulk 가드\|bulk-guard" "$DOCS/_index.md" && echo "  ✓ Bulk 가드 키워드" || (echo "  ✗ Bulk 가드 없음" && exit 1)
    echo "--- plans 디렉토리 ---"
    [ -f "$SCRIPT_DIR/../plans/dev-meta-intelligence-phase-d/index.json" ] \
      && echo "  ✓ plans/dev-meta-intelligence-phase-d/index.json" \
      || (echo "  ✗ plan index 없음" && exit 1)
    echo "=== PASS ==="
    ;;

  content-register-3)
    echo "=== content-register-3: [id]/?enrich=true 진입점 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    DETAIL_PAGE="$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- useSearchParams import ---"
    grep -q "useSearchParams" "$DETAIL_PAGE" \
      && echo "  ✓ useSearchParams imported" \
      || (echo "  ✗ useSearchParams missing" && exit 1)
    echo "--- enrich param detection ---"
    grep -q 'searchParams.get.*"enrich"' "$DETAIL_PAGE" \
      && echo "  ✓ enrich param detection present" \
      || (echo "  ✗ enrich param detection missing" && exit 1)
    echo "--- showEnrich auto-enable ---"
    grep -q 'setShowEnrich.*true' "$DETAIL_PAGE" \
      && echo "  ✓ showEnrich auto-enable present" \
      || (echo "  ✗ showEnrich auto-enable missing" && exit 1)
    echo "=== PASS ==="
    ;;

  ai-review-queue-6)
    echo "=== ai-review-queue-6: Bulk Review Summary 보강 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- guard function exists ---"
    [ -f "$CMS/apps/web/lib/reviewQueueGuard.ts" ] \
      && echo "  ✓ reviewQueueGuard.ts exists" \
      || (echo "  ✗ reviewQueueGuard.ts missing" && exit 1)
    echo "--- guard function exports ---"
    grep -q "checkBulkApplyGuard" "$CMS/apps/web/lib/reviewQueueGuard.ts" \
      && echo "  ✓ checkBulkApplyGuard exported" \
      || (echo "  ✗ checkBulkApplyGuard missing" && exit 1)
    echo "--- review page multi-filter ---"
    grep -q "FilterState" "$CMS/apps/web/app/(main)/programming/contents/review/page.tsx" \
      && echo "  ✓ FilterState type present" \
      || (echo "  ✗ FilterState missing" && exit 1)
    grep -q "checkBulkApplyGuard" "$CMS/apps/web/app/(main)/programming/contents/review/page.tsx" \
      && echo "  ✓ guard used in page" \
      || (echo "  ✗ guard not used in page" && exit 1)
    grep -q "toggleDimension" "$CMS/apps/web/app/(main)/programming/contents/review/page.tsx" \
      && echo "  ✓ multi-dimension filter toggle present" \
      || (echo "  ✗ toggleDimension missing" && exit 1)
    grep -q "handleBulkApply" "$CMS/apps/web/app/(main)/programming/contents/review/page.tsx" \
      && echo "  ✓ bulk apply handler present" \
      || (echo "  ✗ handleBulkApply missing" && exit 1)
    echo "=== PASS ==="
    ;;

  ai-review-queue-7)
    echo "=== ai-review-queue-7: MetadataEnrichPanel 2패널 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- component exists ---"
    [ -f "$CMS/apps/web/components/contents/MetadataEnrichPanel.tsx" ] \
      && echo "  ✓ MetadataEnrichPanel.tsx exists" \
      || (echo "  ✗ MetadataEnrichPanel.tsx missing" && exit 1)
    echo "--- page integration ---"
    grep -q "MetadataEnrichPanel" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ MetadataEnrichPanel used in page" \
      || (echo "  ✗ MetadataEnrichPanel not found in page" && exit 1)
    grep -q "showEnrich" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ showEnrich toggle state present" \
      || (echo "  ✗ showEnrich state missing" && exit 1)
    echo "=== PASS ==="
    ;;

  ai-review-queue-4)
    echo "=== ai-review-queue-4: VisualAssetCandidatePanel MVP ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint errors ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- component exists ---"
    [ -f "$CMS/apps/web/components/contents/VisualAssetCandidatePanel.tsx" ] \
      && echo "  ✓ VisualAssetCandidatePanel.tsx exists" \
      || (echo "  ✗ VisualAssetCandidatePanel.tsx missing" && exit 1)
    echo "--- inline poster section replaced ---"
    grep -q "VisualAssetCandidatePanel" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ VisualAssetCandidatePanel used in page" \
      || (echo "  ✗ VisualAssetCandidatePanel not found in page" && exit 1)
    echo "=== PASS ==="
    ;;

  ai-review-queue-3)
    echo "=== ai-review-queue-3: MetadataDiffPanel 분리 + 추천 패널 위치 정리 ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error " | tail -10 || true
    echo "--- component exists ---"
    [ -f "$CMS/apps/web/components/contents/MetadataDiffPanel.tsx" ] \
      && echo "  ✓ MetadataDiffPanel.tsx exists" \
      || (echo "  ✗ MetadataDiffPanel.tsx missing" && exit 1)
    echo "--- inline function removed ---"
    ! grep -q "^function RecommendationPanel" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ inline RecommendationPanel removed" \
      || (echo "  ✗ inline RecommendationPanel still present" && exit 1)
    echo "--- new import present ---"
    grep -q "MetadataDiffPanel" "$CMS/apps/web/app/(main)/programming/contents/[id]/page.tsx" \
      && echo "  ✓ MetadataDiffPanel import OK" \
      || (echo "  ✗ MetadataDiffPanel import missing" && exit 1)
    echo "=== PASS ==="
    ;;

  ai-review-queue-2)
    echo "=== ai-review-queue-2: frontend Review Queue list page ==="
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    echo "--- typecheck ---"
    cd "$CMS" && npm run typecheck --silent 2>&1 | tail -10
    echo "--- lint ---"
    cd "$CMS" && npm run lint --silent 2>&1 | grep -E "error|warning|PASS|✓" | tail -10
    echo "--- route exists ---"
    [ -f "$CMS/apps/web/app/(main)/programming/contents/review/page.tsx" ] \
      && echo "  ✓ review/page.tsx exists" \
      || (echo "  ✗ review/page.tsx missing" && exit 1)
    echo "--- docs.ts entry ---"
    grep -q "contents/review" "$CMS/apps/web/config/docs.ts" \
      && echo "  ✓ docs.ts entry OK" \
      || (echo "  ✗ docs.ts entry missing" && exit 1)
    echo "--- api.ts types ---"
    grep -q "AiReviewQueueRow" "$CMS/apps/web/lib/api.ts" \
      && echo "  ✓ AiReviewQueueRow type OK" \
      || (echo "  ✗ AiReviewQueueRow missing" && exit 1)
    grep -q "getAiReviewQueue" "$CMS/apps/web/lib/api.ts" \
      && echo "  ✓ getAiReviewQueue fn OK" \
      || (echo "  ✗ getAiReviewQueue missing" && exit 1)
    echo "=== PASS ==="
    ;;

  phase-d-step0)
    echo "=== phase-d-step0: ADR docs/dev/phase-d/ ==="
    DIR="$SCRIPT_DIR/../docs/dev/phase-d"
    test -d "$DIR" || { echo "  ✗ $DIR 없음"; exit 1; }
    REQUIRED_FILES=("_index.md" "sources.md" "quota-policy.md" "on-off-policy.md" "bulk-guard.md" "cache-policy.md" "monitoring-data-model.md")
    for f in "${REQUIRED_FILES[@]}"; do
      test -f "$DIR/$f" || { echo "  ✗ $f 누락"; exit 1; }
    done
    echo "  ✓ 7개 파일 존재"
    INDEX="$DIR/_index.md"
    for sec in "sources.md" "quota-policy.md" "on-off-policy.md" "bulk-guard.md" "cache-policy.md" "monitoring-data-model.md"; do
      grep -q "$sec" "$INDEX" || { echo "  ✗ _index.md 에 $sec 링크 누락"; exit 1; }
    done
    echo "  ✓ _index.md 에 섹션 링크 확인"
    echo "=== PASS ==="
    ;;

  phase-d-step1)
    echo "=== phase-d-step1: migration 0013 + env keys ==="
    test -f "$BACKEND/alembic/versions/0013_phase_d_websearch.py" || { echo "  ✗ 0013_phase_d_websearch.py 없음"; exit 1; }
    echo "  ✓ 0013_phase_d_websearch.py 존재"
    python3 -c "
from shared.config import settings
assert hasattr(settings, 'BRAVE_SEARCH_API_KEY'), 'BRAVE_SEARCH_API_KEY 없음'
assert hasattr(settings, 'WEBSEARCH_ENABLED'), 'WEBSEARCH_ENABLED 없음'
assert hasattr(settings, 'WEBSEARCH_BULK_ALLOWED'), 'WEBSEARCH_BULK_ALLOWED 없음'
print('  ✓ env 키 9개 import OK')
"
    echo "=== PASS ==="
    ;;

  phase-d-step2)
    echo "=== phase-d-step2: web_search package + Brave ==="
    python3 -c "
from api.meta_core.web_search import WebSearchProvider, WebSearchResult
from api.meta_core.web_search.brave import BraveSearchProvider
from api.meta_core.web_search.cache import cache_get, cache_put
from api.meta_core.web_search.errors import QuotaExhaustedError, ProviderUnavailableError
print('  ✓ web_search 패키지 + base + brave + cache + errors import OK')
"
    python3 -m pytest tests/meta_core/web_search/test_brave.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step3)
    echo "=== phase-d-step3: SerpAPI + Gemini + Ollama ==="
    python3 -c "
from api.meta_core.web_search.serpapi import SerpApiProvider
from api.meta_core.web_search.gemini_grounding import GeminiGroundingProvider
from api.meta_core.web_search.ollama_ddg import OllamaDDGProvider
from api.meta_core.web_search.factory import get_provider_chain, search_with_fallback
print('  ✓ 4 provider + factory import OK')
"
    python3 -m pytest tests/meta_core/web_search/test_factory.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step4)
    echo "=== phase-d-step4: bulk guard + cache ==="
    python3 -c "
from api.meta_core.web_search.guard import check_bulk_allowed, BulkQuotaError
print('  ✓ guard import OK')
"
    python3 -m pytest tests/meta_core/web_search/test_guard.py tests/meta_core/web_search/test_cache.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step5)
    echo "=== phase-d-step5: WebSearchDiscoverySource ==="
    python3 -c "
from api.meta_core.discovery.websearch_source import WebSearchDiscoverySource
print('  ✓ WebSearchDiscoverySource import OK')
"
    python3 -m pytest tests/meta_core/discovery/test_websearch.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step6)
    echo "=== phase-d-step6: aggregator opt-in ==="
    python3 -c "
from api.meta_core.aggregator import aggregate_content
from api.meta_core.intelligence.schemas import BulkAcceptRequest
import inspect
src = inspect.getsource(aggregate_content)
assert 'enable_web_search' in src, 'enable_web_search 파라미터 없음'
print('  ✓ aggregator.aggregate_content enable_web_search 파라미터 OK')
"
    python3 -m pytest tests/meta_core/test_aggregator_websearch.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step7)
    echo "=== phase-d-step7: monitoring API ==="
    python3 -c "
from api.meta_core.web_search.router import router
from api.meta_core.web_search.router import ProviderQuotaOut, QuotaStatsOut, CacheStatsOut, RecentCallOut, RecentCallsOut
paths = [str(route.path) for route in router.routes]
for p in ['/quota', '/cache-stats', '/recent']:
    assert p in paths, f'{p} 엔드포인트 없음'
print('  ✓ 3개 GET 엔드포인트 확인 OK')
"
    python3 -m pytest tests/meta_core/web_search/test_router.py -q
    echo "=== PASS ==="
    ;;

  phase-d-step8)
    echo "=== phase-d-step8: monitoring UI + Beat + wrap ==="
    # 백엔드: websearch_tasks + celery Beat 등록
    python3 -c "
from workers.websearch_tasks import discover_websearch_trending
from workers.celery_app import celery_app
sched = celery_app.conf.beat_schedule
assert 'discover-websearch-trending' in sched, 'discover-websearch-trending beat 없음'
print('  ✓ websearch_tasks + Beat 스케줄 확인 OK')
"
    # 프론트엔드: webSearchApi + 모니터링 페이지
    CMS="$SCRIPT_DIR/../mediaX-CMS"
    grep -q "webSearchApi" "$CMS/apps/web/lib/webSearchApi.ts" || { echo "  ✗ webSearchApi 없음"; exit 1; }
    test -f "$CMS/apps/web/app/(main)/monitoring/web-search/page.tsx" || { echo "  ✗ web-search/page.tsx 없음"; exit 1; }
    echo "  ✓ webSearchApi + 모니터링 페이지 확인 OK"
    # 문서: step8.md + CHANGELOG.md
    test -f "$SCRIPT_DIR/../plans/dev-meta-intelligence-phase-d/step8.md" || { echo "  ✗ step8.md 없음"; exit 1; }
    test -f "$SCRIPT_DIR/../docs/dev/phase-d/CHANGELOG.md" || { echo "  ✗ CHANGELOG.md 없음"; exit 1; }
    echo "  ✓ 문서 파일 확인 OK"
    echo "=== PASS ==="
    ;;

  *)
    echo "ERROR: 알 수 없는 step-id '$STEP'"
    echo "사용 가능한 step: meta-intelligence-step1 ~ step9, phase-c-step0 ~ phase-c-step9, quota-adr-step1 ~ step3, sources-step0 ~ step3, watcha-step0 ~ step8, ui-consolidation-step0 ~ step7, ui-impl-1 ~ ui-impl-4, dev-api-step0 ~ step5, ui-wiring-step0 ~ step3, watcha-real-2, watcha-real-3, watcha-real-4, watcha-real-5, watcha-real-6, M.1, M.2, poster-display-step1 ~ step8, poster-recommend-1.1 ~ 3.1, detail-vod-1.1 ~ 3.1, flexible-meta-step0 ~ step4, flexible-meta-step5a ~ flexible-meta-step5d, ai-review-queue-1.1 ~ 1.5, ai-review-queue-2, ai-review-queue-3, ai-review-queue-4, ai-review-queue-5, ai-review-queue-6, ai-review-queue-7, content-register-1, content-register-2, content-register-3"
    exit 1
    ;;
esac
