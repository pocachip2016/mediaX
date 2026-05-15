# Step 2 — 3탭 패널 (글자/이미지/영상)

## 목표
Hero card 하단에 3탭 패널 추가 — 보조 콘텐츠 자산 선택 입력 (선택 사항).

## 변경 내용

### FormState 확장
```typescript
type FormState = {
  title: string
  original_title: string
  content_type: ContentType
  cp_name: string
  production_year: string
  runtime: string
  country: string
  director: string
  cast: string
  synopsis: string
  // NEW:
  extended_synopsis: string
  catchphrase: string
  keywords: string[]
  // image
  stills: File[]
  backgroundImage: File | null
  // video
  vodPath: string
  trailerPath: string
  format: "MP4" | "TS" | "HLS"
  resolution: "4K" | "1080p" | "720p"
}
```

### UI 추가
- `activeTab` state: `"text" | "image" | "video"`
- TabNav: 3개 탭 버튼 (hero card 바로 아래)
- 글자 탭:
  - `extended_synopsis`: textarea 6행
  - `catchphrase`: input 1줄
  - `keywords`: 장르태그와 동일 패턴 (Enter/쉼표 추가, 태그 UI)
- 이미지 탭:
  - `stills`: 파일 드롭존 (max 5, preview grid)
  - `backgroundImage`: 드롭존 (16:9, single)
- 영상 탭:
  - `vodPath`: text input
  - `trailerPath`: text input
  - `format`: select (MP4/TS/HLS)
  - `resolution`: select (4K/1080p/720p)

### handleSubmit 수정
- 스틸/배경이미지: 현 단계는 File 선택만, 업로드는 Later (POST body에는 포함 안 함)
- POST body: extended_synopsis, catchphrase, keywords(join), vodPath, trailerPath, format, resolution만 추가
- 리다이렉트: `/programming/contents/{id}?enrich=true` (기존 동일)

## 파일
- `mediaX-CMS/apps/web/app/(main)/programming/contents/new/page.tsx`

## 예상 코드 라인
- 페이지 전체 ~600줄 (hero ~200 + tabs ~350 + 로직 + style)

## 검증
- typecheck 0 errors
- 3탭 전환 작동
- 글자 탭: keywords 태그 입력·제거 작동
- 이미지 탭: stills 5장 제한 + preview
- 영상 탭: select 옵션 정상
- POST: title + cp_name 필수, 나머지 선택 사항
- 리다이렉트: /programming/contents/{id}?enrich=true
