---
name: services-ssot
description: mediaX 에서 OTT/IPTV 출처 식별은 services 테이블을 SSOT 로 사용. service_id FK 로 통일. 컬럼에 문자열("ott_watcha") 직접 박지 말 것.
metadata:
  type: feedback
---

mediaX 의 OTT/IPTV "출처" 개념은 `services` 테이블(`id, code, name, kind`) 을 단일 진실원천(SSOT)으로 사용한다. 다음 두 테이블 모두 string 컬럼 대신 `service_id` FK 로 출처를 참조한다:
- `service_categories.service_id` (이전: `platform VARCHAR(50)`)
- `content_distributions.service_id` (이전: `channel VARCHAR(50)` + `channel_type`)

OttSource 어댑터 클래스도 `channel = "ott_watcha"` 같은 ClassVar 대신 `service_code = "ott_watcha"` 를 가지고 writer 에서 services 테이블 lookup 후 service_id 변환.

**Why:** dev-service-distribution Step 3 설계 시 사용자가 명시적으로 결정 — 컬럼에 OTT 코드 문자열을 박는 구조는 정규화 위반이며, 큐레이션 트리 / OTT popularity / IPTV 채널 등 모든 분배 메타가 동일한 출처 식별자를 공유해야 한다. 새 OTT 추가 시 services 한 행만 추가하면 끝.

**How to apply:**
- 새 분배 채널 추가 시 → `services` 에 row 먼저 추가, 다른 테이블은 `service_id` FK 로 참조.
- bulk CSV 업로드 / API 입력에서 service 를 받을 때 → `service_code` 문자열로 받되 즉시 services 테이블 lookup 으로 `service_id` 변환. 매칭 실패 시 row skip + error_log.
- OTT 어댑터(`watcha.py`, `netflix.py` 등) 신규 작성 시 → `service_code` ClassVar 만 정의, channel/channel_type 같은 string field 사용 금지.
- 마이그레이션 시 기존 string 컬럼은 백필 후 DROP. 백필 매핑 실패 row 가 있으면 마이그레이션 중단.
- 관련 결정: [[recursive-category-tree]] (services 와 같이 도입된 카테고리 재귀 구조)
