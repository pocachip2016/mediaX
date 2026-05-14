#!/bin/bash
# mediaX 마이그레이션 & seed API 검증

echo "=== Checking Database Migration ===" 
LATEST=$(docker-compose exec -T postgres psql -U media_ax -d media_ax -c "SELECT version_num FROM alembic_version ORDER BY version_num DESC LIMIT 1;" 2>/dev/null | tail -1 | tr -d ' ')
if [ "$LATEST" = "0012" ]; then
  echo "✓ Migration complete (0012)"
else
  echo "✗ Migration incomplete (got $LATEST, expected 0012)"
  exit 1
fi

echo "=== Checking API Router ===" 
ROUTES=$(docker-compose exec -T backend python3 -c "from main import app; print(len([r for r in app.routes if hasattr(r, 'path') and '/seeds' in r.path]))" 2>/dev/null | tail -1)
if [ "$ROUTES" -gt 0 ]; then
  echo "✓ Seed API routes registered ($ROUTES routes)"
else
  echo "✗ Seed API not registered"
  exit 1
fi

echo "=== Checking TestClient ===" 
docker-compose exec -T backend python3 << 'PYTHON' > /dev/null 2>&1
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)
resp = client.get("/api/meta-core/seeds")
assert resp.status_code == 200, f"Got {resp.status_code}"
PYTHON
if [ $? -eq 0 ]; then
  echo "✓ API functional (TestClient 200 OK)"
else
  echo "✗ API error"
  exit 1
fi

echo ""
echo "✅ All validations passed"
