"""
Step 0: Schemas + Foundation — 신규 스키마 직렬화 테스트
"""

import pytest
from datetime import datetime
from api.programming.metadata.schemas import (
    EnrichPreviewRequest,
    EnrichPreviewOut,
    BatchPreviewOut,
    SourceSearchOut,
    CreateFromSourcesRequest,
    CreateFromSourcesOut,
    PromoteAIResultRequest,
    PromoteAIResultOut,
    ApplyExternalFieldsRequest,
    ContentChangelogOut,
    ChangeLogItem,
    LockFieldsRequest,
    BulkActionConsolidatedRequest,
    BulkActionResponse,
    JobStatusOut,
    RetryFailedRequest,
    UndoActionRequest,
    UndoActionOut,
)


class TestContentAddFlowSchemas:
    """Content Add Flow 스키마 검증"""

    def test_enrich_preview_request(self):
        """EnrichPreviewRequest 직렬화"""
        req = EnrichPreviewRequest(fields=["synopsis", "genre"])
        assert req.fields == ["synopsis", "genre"]
        data = req.model_dump()
        assert data["fields"] == ["synopsis", "genre"]

    def test_enrich_preview_out(self):
        """EnrichPreviewOut 직렬화"""
        resp = EnrichPreviewOut(
            enriched_fields={"synopsis": "Test"},
            external_sources=[],
            errors=None,
        )
        data = resp.model_dump()
        assert "enriched_fields" in data
        assert "external_sources" in data

    def test_batch_preview_out(self):
        """BatchPreviewOut 직렬화"""
        resp = BatchPreviewOut(
            valid_count=10,
            missing_count=2,
            error_count=0,
            duplicate_count=1,
            estimated_cost="$0.05",
            estimated_duration_seconds=120,
        )
        data = resp.model_dump()
        assert data["valid_count"] == 10
        assert data["estimated_duration_seconds"] == 120

    def test_source_search_out(self):
        """SourceSearchOut 직렬화"""
        resp = SourceSearchOut(
            results=[
                {
                    "title": "Parasite",
                    "year": 2019,
                    "source": "TMDB",
                    "match_percent": 94.0,
                }
            ],
            errors=None,
        )
        data = resp.model_dump()
        assert len(data["results"]) == 1
        assert data["results"][0]["match_percent"] == 94.0

    def test_create_from_sources_request(self):
        """CreateFromSourcesRequest 직렬화"""
        req = CreateFromSourcesRequest(
            source_id=1,
            selected_fields=["synopsis", "genre"],
            cp_name="CJ ENM",
        )
        data = req.model_dump()
        assert data["source_id"] == 1
        assert len(data["selected_fields"]) == 2

    def test_create_from_sources_out(self):
        """CreateFromSourcesOut 직렬화"""
        resp = CreateFromSourcesOut(id=42, title="기생충", status="processing")
        data = resp.model_dump()
        assert data["id"] == 42
        assert data["status"] == "processing"


class TestContentDetailSchemas:
    """Content Detail 스키마 검증"""

    def test_promote_ai_result_request(self):
        """PromoteAIResultRequest 직렬화"""
        req = PromoteAIResultRequest(ai_result_id=99)
        data = req.model_dump()
        assert data["ai_result_id"] == 99

    def test_promote_ai_result_out(self):
        """PromoteAIResultOut 직렬화"""
        resp = PromoteAIResultOut(id=1, is_final=True)
        data = resp.model_dump()
        assert data["is_final"] is True

    def test_apply_external_fields_request(self):
        """ApplyExternalFieldsRequest 직렬화"""
        req = ApplyExternalFieldsRequest(source_id=5, fields=["synopsis"])
        data = req.model_dump()
        assert data["source_id"] == 5

    def test_changelog_item(self):
        """ChangeLogItem 직렬화"""
        now = datetime.now()
        item = ChangeLogItem(
            field="synopsis",
            old_value="old synopsis",
            new_value="new synopsis",
            changed_by="system",
            changed_at=now,
        )
        data = item.model_dump(mode="json")
        assert data["field"] == "synopsis"

    def test_content_changelog_out(self):
        """ContentChangelogOut 직렬화"""
        now = datetime.now()
        resp = ContentChangelogOut(
            changes=[
                ChangeLogItem(
                    field="synopsis",
                    old_value="old",
                    new_value="new",
                    changed_by="user1",
                    changed_at=now,
                )
            ]
        )
        data = resp.model_dump(mode="json")
        assert len(data["changes"]) == 1

    def test_lock_fields_request(self):
        """LockFieldsRequest 직렬화"""
        req = LockFieldsRequest(fields=["synopsis", "genre"], reason="Manual lock")
        data = req.model_dump()
        assert len(data["fields"]) == 2
        assert data["reason"] == "Manual lock"


class TestBulkActionSchemas:
    """Bulk Action 스키마 검증"""

    def test_bulk_action_request(self):
        """BulkActionConsolidatedRequest 직렬화"""
        req = BulkActionConsolidatedRequest(
            ids=[1, 2, 3],
            reason="Test reason",
            filter_query=None,
        )
        data = req.model_dump()
        assert len(data["ids"]) == 3
        assert data["reason"] == "Test reason"

    def test_bulk_action_response(self):
        """BulkActionResponse 직렬화"""
        resp = BulkActionResponse(
            job_id="job-123",
            ids_accepted=3,
            ids_rejected=0,
            errors=None,
        )
        data = resp.model_dump()
        assert data["job_id"] == "job-123"
        assert data["ids_accepted"] == 3

    def test_job_status_out(self):
        """JobStatusOut 직렬화"""
        now = datetime.now()
        resp = JobStatusOut(
            id=1,
            status="processing",
            action_type="bulk_reprocess",
            target_count=10,
            completed_count=5,
            failed_count=0,
            progress_percent=50,
            created_at=now,
            started_at=now,
            completed_at=None,
            errors=None,
        )
        data = resp.model_dump(mode="json")
        assert data["progress_percent"] == 50
        assert data["status"] == "processing"

    def test_retry_failed_request(self):
        """RetryFailedRequest 직렬화"""
        req = RetryFailedRequest()
        data = req.model_dump()
        assert isinstance(data, dict)

    def test_undo_action_request(self):
        """UndoActionRequest 직렬화"""
        req = UndoActionRequest(action_id="action-456")
        data = req.model_dump()
        assert data["action_id"] == "action-456"

    def test_undo_action_out(self):
        """UndoActionOut 직렬화"""
        resp = UndoActionOut(id=1, status="review", reverted_count=3)
        data = resp.model_dump()
        assert data["reverted_count"] == 3


def test_all_schemas_importable():
    """모든 신규 스키마가 import 가능한지 확인"""
    import api.programming.metadata.schemas as schemas

    assert hasattr(schemas, "EnrichPreviewRequest")
    assert hasattr(schemas, "EnrichPreviewOut")
    assert hasattr(schemas, "BatchPreviewOut")
    assert hasattr(schemas, "SourceSearchOut")
    assert hasattr(schemas, "CreateFromSourcesRequest")
    assert hasattr(schemas, "CreateFromSourcesOut")
    assert hasattr(schemas, "PromoteAIResultRequest")
    assert hasattr(schemas, "PromoteAIResultOut")
    assert hasattr(schemas, "ApplyExternalFieldsRequest")
    assert hasattr(schemas, "ContentChangelogOut")
    assert hasattr(schemas, "LockFieldsRequest")
    assert hasattr(schemas, "BulkActionConsolidatedRequest")
    assert hasattr(schemas, "BulkActionResponse")
    assert hasattr(schemas, "JobStatusOut")
    assert hasattr(schemas, "RetryFailedRequest")
    assert hasattr(schemas, "UndoActionRequest")
    assert hasattr(schemas, "UndoActionOut")
