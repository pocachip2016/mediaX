# backend/alembic/ — DB 마이그레이션

## 역할
SQLAlchemy 모델 변경사항을 PostgreSQL에 반영하는 Alembic 마이그레이션 관리.

## 실행 방법

```bash
# Docker (PostgreSQL) 실행 후
alembic upgrade head          # 최신 마이그레이션 적용
alembic downgrade -1          # 한 단계 롤백

# 새 모델 추가 후 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "설명"

# 오프라인 SQL 확인 (DB 없이)
alembic upgrade head --sql
```

## 로컬 개발 (Docker 없이)
`.env`의 `DATABASE_URL`을 SQLite로 변경:
```
DATABASE_URL=sqlite:///./media_ax_dev.db
```
그 후 Python으로 직접 테이블 생성:
```bash
python3 -c "from shared.database import Base, engine; import api.programming.metadata.models; Base.metadata.create_all(engine)"
```

## 마이그레이션 파일 목록
| 파일 | 내용 |
|------|------|
| `0001_init_metadata_module.py` | contents, content_metadata, cp_email_logs, external_meta_cache |

## 새 모듈 추가 시
`env.py` 상단 import 주석 해제:
```python
import api.programming.catalog.models  # noqa
```
