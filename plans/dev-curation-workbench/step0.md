# Step 0 — ADR: 큐레이션 워크벤치 설계

> 별도 branch: `feature/curation-workbench`
> phase: `dev-curation-workbench`

## 1. 배경

`dev-service-distribution` Step 3에서 ServiceCategory CRUD API 7개 + 20 pytest 완료 (PR #11). 그러나 운영자 측 요구사항은 단순 CRUD가 아닌 "큐레이션 설계 워크벤치":

1. **수동 묶음** — 보유 콘텐츠를 특정 테마로 묶음
2. **테마 제안** — 테마 특징(장르·무드·시간대 등) → AI가 카피와 콘텐츠 목록 제안 → 선택
3. **외부 참고** — 2번 과정에서 외부 OTT(Watcha/Netflix/Wave/Tving)의 유사 큐레이션(플랫폼·카테고리·카피·콘텐츠목록) 참고

본 ADR은 위 3가지 모드를 통합한 워크벤치 구조를 정의한다.

## 2. 핵심 결정

### 2.1 큐레이션 카피(Copy)의 정의

| 용어 | 의미 |
|------|------|
| **headline_copy** | 큐레이션 표지 마케팅 카피·태그라인 (예: "퇴근 후 90분의 위로") |
| **sub_copy** | 보조 설명 한 줄 (선택) |

⚠️ "Copyright(저작권)"가 아니라 **광고 카피·헤드라인 카피** 의미.

### 2.2 OTT 1-Depth Category == Copy

OTT 외부 서비스(Watcha/Netflix 등)의 화면에서 노출되는 **1-Depth 카테고리/섹션 이름**(예: "이번 주 TOP10", "신작", "장르 - 코미디")은 그 자체가 카피 역할을 한다.

→ 외부 큐레이션 참고 시:
- `section_name` 자체를 carry-over copy candidate로 표시
- LLM 생성 카피와 별도 섹션으로 후보 노출
- "그대로 가져오기" 선택 시 `headline_copy = section_name` + `source_mode = external_imported`

### 2.3 source_mode (3가지)

| 값 | 의미 | 카피 출처 |
|----|------|----------|
| `manual` | 운영자 수동 묶음 | 운영자 직접 입력 |
| `ai_proposed` | AI 위저드로 생성 | LLM 후보 또는 외부 section_name 후보 중 선택 |
| `external_imported` | 외부 OTT 큐레이션 그대로 가져옴 | 외부 section_name 그대로 |

### 2.4 ServiceCategory 모델 확장

```python
class ServiceCategory(Base):
    # 기존 필드 유지
    name = Column(String(100), nullable=False)              # 내부 식별명
    category_type = Column(String(50), nullable=False)
    platform = Column(String(50), nullable=False)
    position = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    # 신규 (alembic 0025)
    headline_copy = Column(String(200), nullable=True)      # 마케팅 카피
    sub_copy = Column(String(300), nullable=True)           # 보조 카피
    theme_features = Column(JSONB, nullable=True)           # 테마 메타(아래 스키마)
    source_mode = Column(String(20), default="manual")      # manual|ai_proposed|external_imported
    reference_external_id = Column(String(200), nullable=True)  # 외부 참고 출처 id
    is_draft = Column(Boolean, default=False)               # 임시 저장 플래그
```

### 2.5 theme_features JSONB 컨벤션

스키마-less 이지만 FE/BE가 합의하는 컨벤션:

```jsonc
{
  "genres": ["코미디", "드라마"],
  "moods": ["가벼운", "따뜻한"],
  "runtime_min": 80,
  "runtime_max": 120,
  "era_from": 2000,
  "era_to": 2026,
  "target": "30s_adults",
  "occasion": "weekday_evening",   // 평일저녁·주말·심야·무관
  "free_keywords": ["퇴근", "위로"]
}
```

추가 필드는 자유롭게 확장(읽는 쪽이 옵셔널 처리).

### 2.6 OttSource ABC 확장 — multi-section

기존:
```python
class OttSource(ABC):
    @abstractmethod
    def fetch_top(self, limit: int = 20) -> list[OttItem]: ...
```

확장 (Step 2):
```python
@dataclass
class OttSection:
    section_id: str          # 외부 안정 id (URL slug or hash)
    name: str                # "이번 주 TOP10" 등 ← Copy 후보
    category_type: str       # ranking | genre | recommendation | mood
    items: list[OttItem]

class OttSource(ABC):
    @abstractmethod
    def fetch_top(self, limit: int = 20) -> list[OttItem]: ...

    def fetch_sections(self) -> list[OttSection]:
        """기본은 fetch_top을 단일 section으로 래핑. 소스별로 multi-section override."""
        items = self.fetch_top()
        return [OttSection(
            section_id=f"{self.channel}:top",
            name="TOP",
            category_type="ranking",
            items=items,
        )]
```

→ Watcha/Netflix 등은 향후 다중 섹션 크롤링으로 override. 본 phase에서는 ABC + 기본 구현 + 1개 소스 multi-section 시범 구현(Watcha 우선).

### 2.7 LLM 카피 생성 체인

`meta_intelligence` 모듈의 기존 폴백 패턴 재사용:

```
1차: Gemini Flash (구조화 JSON 응답 → 3 후보)
폴백: Ollama llama3.2:3b (로컬, 무료, 응답 단순화)
실패: 카피 후보 0건 → FE는 "직접 입력" 폴백
```

프롬프트는 `theme_features` + 선택된 외부 참고 `section_names`를 입력으로 받는다.

### 2.8 매칭 점수 (보유 콘텐츠 → features)

`matcher.py`:
- 장르 일치 가중 0.30 (다중 일치 가산)
- 무드 키워드 가중 0.15
- 런타임 범위 내 0.20
- 시대(era) 범위 내 0.10
- 외부 참고에 포함된 콘텐츠 보너스 0.15
- 자유 키워드 LIKE 매칭 0.10
- 최종 0~1 normalized score → `ServiceCategoryItem.score`에 저장

(LLM 없이 결정적 알고리즘. 빠르고 재현 가능.)

### 2.9 API 추가

| 메서드 | 경로 | 용도 |
|--------|------|------|
| POST | `/api/distribution/curations/match-contents` | features → 보유 콘텐츠 매칭 후보 |
| GET | `/api/distribution/curations/external-references` | OttSection 기반 유사 큐레이션 카드 N개 |
| POST | `/api/distribution/curations/propose-copy` | features + selected_refs → 카피 후보 (LLM) |
| POST | `/api/distribution/categories/import-external` | OttSection → ServiceCategory + items 원샷 저장 |
| PUT | `/api/distribution/categories/{id}` (확장) | 신규 필드 수용 |

### 2.10 FE 라우팅

```
/programming/categories              # 진입(3 CTA + 리스트)
/programming/categories/new          # ?mode=manual|ai|external
/programming/categories/[id]         # 상세/편집
/programming/categories/external     # 외부 큐레이션 둘러보기
```

위저드 단계는 `?step=1..4` query로 URL SSOT.

## 3. 비결정 사항 (다음 단계에서 정함)

- Watcha multi-section 크롤링 셀렉터 — Step 2에서 실제 페이지 분석 후 결정
- "참고 후보 매칭" 알고리즘 가중치는 Step 3에서 실데이터로 튜닝
- 위저드 임시저장 UX (자동/명시)는 Step 7에서 결정

## 4. 단계별 산출물

| Step | 영역 | 산출물 | verify |
|------|------|--------|--------|
| 0 | DOC | 본 ADR | `/verify --skip "ADR"` |
| 1 | BE | alembic 0025 + 모델 확장 + 스키마 + PUT 확장 | pytest + alembic head |
| 2 | BE | OttSection + OttSource.fetch_sections + Watcha multi-section 시범 | pytest |
| 3 | BE | matcher + external-ref API + match-contents API | pytest + 매칭 정확도 |
| 4 | BE | propose-copy (Gemini + Ollama 폴백) | pytest mock + 통합 1건 |
| 5 | FE | nav 등록 + landing(3 CTA) + 리스트 표 | dev server 200 |
| 6 | FE | 모드 A — manual master-detail (확장 ServiceCategory 필드 반영) | CRUD e2e |
| 7 | FE | 모드 B 위저드 Step 1·2 (features + external refs) | 단계 이동 + cache |
| 8 | FE | 모드 B 위저드 Step 3·4 (copy + content candidates + 저장) | LLM mock 렌더 |
| 9 | FE | 모드 C 외부 import + 임시저장 | import e2e |
| 10 | FE | 빈/로딩/에러 + 반응형 + screenshot + wrap | verify + 스크린샷 |

## 5. 영향 범위

- **DB**: ServiceCategory 6 컬럼 추가, 마이그레이션 0025
- **OTT 동기화**: OttSource ABC 호환 유지(기본 fetch_sections 구현 제공)
- **meta_intelligence**: 신규 모듈 의존성 추가, 기존 코드 변경 없음
- **FE 네비**: `/programming` 섹션에 "큐레이션" 항목 추가
- **백워드 호환**: PR #11의 기존 CRUD 7 endpoint 그대로 유지, 응답 스키마는 새 필드 추가만(클라이언트 무영향).

## 6. 리스크 & 대응

| 리스크 | 대응 |
|--------|------|
| Watcha multi-section 크롤링 차단/변경 | OttSection 기본 구현(단일 TOP) 폴백 — 항상 기능 동작 |
| LLM 카피 품질 낮음/실패 | "직접 입력" 폴백 + 외부 section_name 후보가 항상 존재 |
| theme_features 스키마 드리프트 | JSONB + 컨벤션 문서화. 읽는 쪽 옵셔널 처리 |
| 매칭 결과 0건 | FE에서 조건 완화 가이드 + 슬라이더 reset |
