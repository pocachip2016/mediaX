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

  *)
    echo "ERROR: 알 수 없는 step-id '$STEP'"
    echo "사용 가능한 step: meta-intelligence-step1 ~ step9"
    exit 1
    ;;
esac
