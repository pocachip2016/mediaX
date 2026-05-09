from datetime import datetime


def setup_changefeed_events():
    """SQLAlchemy Content mapper 이벤트 등록 — 중복 등록 방지를 위해 1회만 호출."""
    from sqlalchemy import event
    from api.programming.metadata.models.content import Content

    def _enqueue(event_type: str, target):
        from workers.tasks.metadata import send_dam_webhook
        try:
            send_dam_webhook.apply_async(
                args=[
                    event_type,
                    target.id,
                    target.title,
                    target.content_type.value if target.content_type else "",
                    datetime.utcnow().isoformat(),
                ],
                countdown=2,
            )
        except Exception:
            pass  # broker 미연결 시 무시 (best-effort)

    @event.listens_for(Content, "after_insert")
    def _on_insert(mapper, connection, target):
        _enqueue("insert", target)

    @event.listens_for(Content, "after_update")
    def _on_update(mapper, connection, target):
        _enqueue("update", target)

    @event.listens_for(Content, "after_delete")
    def _on_delete(mapper, connection, target):
        _enqueue("delete", target)
