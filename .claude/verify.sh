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

  *)
    echo "ERROR: 알 수 없는 step-id '$STEP'"
    echo "사용 가능한 step: meta-intelligence-step1 ~ step9, phase-c-step0 ~ phase-c-step9, quota-adr-step1 ~ step3, sources-step0 ~ step3"
    exit 1
    ;;
esac
