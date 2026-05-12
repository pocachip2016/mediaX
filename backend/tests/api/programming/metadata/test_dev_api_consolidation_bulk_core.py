"""
Step 1: Bulk Core Actions — 5개 엔드포인트 함수 테스트
"""

import pytest


def test_bulk_reprocess_importable():
    """bulk_reprocess 함수 import 가능"""
    from api.programming.metadata.service import bulk_reprocess
    assert callable(bulk_reprocess)


def test_bulk_enrich_importable():
    """bulk_enrich 함수 import 가능"""
    from api.programming.metadata.service import bulk_enrich
    assert callable(bulk_enrich)


def test_bulk_process_importable():
    """bulk_process 함수 import 가능"""
    from api.programming.metadata.service import bulk_process
    assert callable(bulk_process)


def test_bulk_recall_importable():
    """bulk_recall 함수 import 가능"""
    from api.programming.metadata.service import bulk_recall
    assert callable(bulk_recall)


def test_bulk_delete_importable():
    """bulk_delete 함수 import 가능"""
    from api.programming.metadata.service import bulk_delete
    assert callable(bulk_delete)


def test_schemas_importable():
    """5개 bulk action 스키마 import 가능"""
    from api.programming.metadata.schemas import (
        BulkActionConsolidatedRequest,
        BulkActionResponse,
        JobStatusOut,
    )
    assert BulkActionConsolidatedRequest is not None
    assert BulkActionResponse is not None
    assert JobStatusOut is not None


def test_routes_exist():
    """5개 라우터가 정의되어 있음"""
    import pathlib
    src = pathlib.Path("api/programming/metadata/router.py").read_text()

    routes = [
        "api_bulk_reprocess",
        "api_bulk_enrich",
        "api_bulk_process",
        "api_bulk_recall",
        "api_bulk_delete",
    ]

    for route in routes:
        assert f"def {route}" in src, f"{route} 라우터 미정의"


def test_content_model_has_is_deleted():
    """Content 모델에 is_deleted 컬럼 존재"""
    from api.programming.metadata.models import Content
    assert hasattr(Content, "is_deleted"), "Content.is_deleted 컬럼 없음"


def test_content_batch_job_exists():
    """ContentBatchJob 모델 import 가능"""
    from api.programming.metadata.models import ContentBatchJob
    assert ContentBatchJob is not None
