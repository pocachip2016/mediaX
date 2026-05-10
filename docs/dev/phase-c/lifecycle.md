# §1. SEED 라이프사이클 (5단계)

> 소속: Phase C ADR — `_index.md` | 인접: §3 [promotion-guard.md](promotion-guard.md), §4 [dedup.md](dedup.md)

외부 발굴 → 내부 Content 까지의 흐름을 5개 상태로 분리한다.
각 상태는 **테이블 컬럼 1개로 표현 가능한 단일 의미** 를 갖는다.
Phase B 의 5단계 데이터 변환(source_item → candidate → suggestion → resolution → Content)
과는 다른 축 — 본 §1 은 *시간상의 라이프사이클* 이고, Phase B §1 은 *데이터 변환 단계* 다.

## 1.1 `discovered` — 발굴 (raw 1건)

DiscoverySource 가 외부 API 호출로 1 항목을 발견한 직후의 상태.

- 저장 위치: `seed_discovery_log` 1행 (raw payload + source_url + discovered_at)
- 후속 처리: 정규화 시도 → 성공 시 `candidate` 로 전이, 실패 시 로그만 남고 종료
- 보존 기간: 30일 (운영 진단 목적, 이후 partition drop)

**이게 아닌 것**: 정규화된 메타. raw 만 보존.

## 1.2 `candidate` — 후보 적재

raw 를 mediaX 스키마(title_norm, year, content_type, …)로 정규화하고
**기존 Content 와 매칭되지 않음을 확인한 뒤** content_seeds 행을 생성한 상태.

- 저장 위치: `content_seeds` 행 (status=`candidate`)
- 진입 조건: 정규화 성공 + dedup 통과 (§4 참조)
- 재방문 처리: 같은 (source_type, source_external_id) 는 UPSERT — 중복 행 금지

**이게 아닌 것**: 매칭된 후보 (= Phase B `metadata_candidate` 는 content_id 가 있고,
SEED candidate 는 content_id 가 아직 없음).

## 1.3 `under_review` — 검토 진행 중

운영자가 검수 화면에서 "검토 시작" 을 누른 시점부터 결정 전까지의 상태.

- 컬럼: `locked_by` (user_id), `locked_at` (timestamp)
- TTL: 15분 무행동 시 자동 unlock → `candidate` 로 복귀
- 동시 편집 방지: 다른 사용자가 같은 행을 열면 409 Conflict + 잠금자 표시

**이게 아닌 것**: 결정 완료 상태. lock 은 *의도 표시* 일 뿐, 결정은 accept/reject 로만.

## 1.4 `accepted` — 승인 → Content 승격

운영자가 "승인" 을 누른 순간 트랜잭션 내에서:
1. `Content` 행 생성 (title, content_type, production_year, …)
2. `ExternalMetaSource` 자동 작성 (source_type=발굴 소스, external_id=원본 ID)
3. `content_seeds.status` → `accepted`, `promoted_content_id` FK 기록
4. Phase B aggregator 트리거 — 신규 Content 의 첫 메타 채움 비동기 실행

**이게 아닌 것**: confidence 100% 의 자동 승인. accept 는 *인간 판단* 의 결과만.

## 1.5 `rejected` — 거부 (재검토 가능)

운영자가 "거부" 를 누른 상태. content_seeds 행은 유지된다.

- 재검토 트리거: 운영자가 "재오픈" 클릭 → `candidate` 로 복귀
- 재발굴 정책: 같은 source_external_id 가 다시 들어오면 UPSERT 로 metadata 만 갱신,
  `rejected` 상태는 유지 (sticky reject)
- sticky 해제: 운영자가 "재오픈" 했을 때만 해제

**이게 아닌 것**: 영구 삭제. 거부 사유와 컨텍스트는 추후 학습 데이터.

## 1.6 상태 전이도

```
discovered ──정규화 OK + dedup pass──▶ candidate
                                          │
                                          ▼
                                     under_review (lock TTL 15m)
                                       │      │
                              accept   │      │  reject
                                 ▼      ▼      ▼
                              (Content     rejected
                               생성)         │
                                             │ 운영자 재오픈
                                             ▼
                                         candidate
```

자동 전이는 `discovered → candidate` 1개뿐. 나머지는 모두 인간 액션.
