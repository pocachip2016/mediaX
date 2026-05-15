# Step 3: 프론트 IA 재구성 (메뉴 분해)

## 배경
현재: AddContentModal이 단일/CSV배치/외부검색을 한 다이얼로그에서 처리.
문제: 모달 내 3가지 플로우가 혼재되어 UX 복잡도 높음 + 작업 흐름이 부자연스러움.

목표 UX: 
- 목록 페이지 → [+ 콘텐츠 등록] → /new (단일 입력)
- 목록 페이지 → [일괄 업로드] → /upload (CSV/Excel)
- 목록 페이지 → [외부 검색] → /external (TMDB/KOBIS 검색 후 선택)
- 목록 페이지 → [편집] (각 행) → /[id]/edit
- 상세 페이지 → [편집] 버튼 → /[id]/edit

## 구현 상세

### 1. 메뉴 구조 변경 (docsNav)
```tsx
// apps/web/lib/docsNav.ts
export const metadataNav = [
  {
    title: "콘텐츠 관리",
    items: [
      {
        title: "콘텐츠 목록",
        href: "/metadata/contents",
        icon: "📋",
      },
      {
        title: "콘텐츠 등록",  // 새로 추가: 단일 입력
        href: "/metadata/new",
        icon: "➕",
      },
      {
        title: "일괄 업로드",  // 새로 추가: CSV/Excel
        href: "/metadata/upload",
        icon: "📤",
      },
      {
        title: "외부 검색",  // 새로 추가: TMDB/KOBIS
        href: "/metadata/external",
        icon: "🔍",
      },
      // ... 기존 항목들
    ],
  },
];
```

### 2. 라우트 추가
```tsx
// apps/web/app/metadata/new/page.tsx
// 단일 콘텐츠 등록 페이지 → ContentForm 컴포넌트

// apps/web/app/metadata/upload/page.tsx
// CSV/Excel 벌크 업로드 페이지 → UploadForm 컴포넌트

// apps/web/app/metadata/external/page.tsx
// TMDB/KOBIS 검색 → 결과 선택 → 벌크 추가 → /upload로 redirect

// apps/web/app/metadata/[id]/edit/page.tsx
// 기존 콘텐츠 수정 → ContentForm 컴포넌트
```

### 3. 목록 페이지 액션 버튼 추가
```tsx
// apps/web/components/metadata/ContentsTable.tsx
// 기존: 상세 보기, AI 처리, 승인
// 추가: [편집] → 클릭 → /metadata/[id]/edit

// apps/web/components/metadata/ContentsListPage.tsx
// 헤더에 추가 버튼 3개:
// [+ 콘텐츠 등록] → /metadata/new
// [일괄 업로드] → /metadata/upload
// [외부 검색] → /metadata/external
```

### 4. 상세 페이지 수정 버튼
```tsx
// apps/web/app/metadata/contents/[id]/page.tsx
// 헤더에 [편집] 버튼 추가 → /metadata/[id]/edit
```

### 5. AddContentModal.tsx 제거
```bash
# 삭제 대상
rm apps/web/components/metadata/AddContentModal.tsx
rm apps/web/components/metadata/AddContentDialog.tsx  # 있다면
# 기존 참조 제거:
# - ContentsListPage의 AddContentModal import/사용 제거
```

## 파일 구조
```
apps/web/
├── app/
│   └── metadata/
│       ├── new/
│       │   └── page.tsx           # 단일 등록 (ContentForm)
│       ├── upload/
│       │   └── page.tsx           # 벌크 업로드 (UploadForm)
│       ├── external/
│       │   └── page.tsx           # 외부 검색 + 결과 리스트
│       ├── [id]/
│       │   └── edit/
│       │       └── page.tsx       # 기존 콘텐츠 수정 (ContentForm)
│       └── contents/
│           └── [id]/
│               └── page.tsx       # 기존 상세 (편집 버튼 추가)
└── components/
    └── metadata/
        ├── ContentForm.tsx        # 공유 컴포넌트 (new/edit 모두 사용)
        ├── UploadForm.tsx         # 벌크 업로드 폼
        ├── ExternalSearch.tsx     # 외부 검색 페이지
        ├── ContentsListPage.tsx   # 목록 (헤더 버튼 3개 추가)
        └── (AddContentModal.tsx)  # 삭제
```

## 구현 세부 (예: ContentForm)
```tsx
// apps/web/components/metadata/ContentForm.tsx
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

interface ContentFormProps {
  contentId?: number;  // undefined = 신규, 있음 = 수정
  initialData?: Content;
}

export default function ContentForm({ contentId, initialData }: ContentFormProps) {
  const router = useRouter();
  const { register, handleSubmit, formState: { errors } } = useForm({
    defaultValues: initialData || {
      title: "",
      production_year: new Date().getFullYear(),
      content_type: "movie",
      cp_name: "",
      synopsis: "",
      cast: "",
      directors: "",
      genres: "",
      country: "",
      runtime: undefined,
      rating_age: "",
      poster_url: "",
    },
  });

  const onSubmit = async (data) => {
    if (contentId) {
      // PUT /contents/{id}
      await fetch(`/api/programming/metadata/contents/${contentId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      });
      router.push(`/metadata/contents/${contentId}`);
    } else {
      // POST /contents
      const res = await fetch("/api/programming/metadata/contents", {
        method: "POST",
        body: JSON.stringify(data),
      });
      const newContent = await res.json();
      router.push(`/metadata/contents/${newContent.id}`);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <input {...register("title", { required: true })} placeholder="제목" />
        <input {...register("production_year", { valueAsNumber: true })} type="number" placeholder="제작년도" />
        <select {...register("content_type")} defaultValue="movie">
          <option value="movie">영화</option>
          <option value="series">시리즈</option>
          <option value="season">시즌</option>
          <option value="episode">에피소드</option>
        </select>
        <input {...register("cp_name")} placeholder="CP사" />
      </div>
      
      <textarea {...register("synopsis")} placeholder="줄거리" rows={3} />
      <input {...register("cast")} placeholder="출연진 (쉼표 구분: 배우1, 배우2, ...)" />
      <input {...register("directors")} placeholder="감독 (쉼표 구분: 감독1, 감독2, ...)" />
      <input {...register("genres")} placeholder="장르 (쉼표 구분: 드라마, 판타지, ...)" />
      <input {...register("country")} placeholder="제작국가" />
      <input {...register("runtime", { valueAsNumber: true })} type="number" placeholder="런타임 (분)" />
      <input {...register("rating_age")} placeholder="시청등급" />
      <input {...register("poster_url")} placeholder="포스터 URL" />
      
      <button type="submit" className="btn btn-primary">
        {contentId ? "수정" : "등록"}
      </button>
    </form>
  );
}
```

## 검증 방법
```bash
# 1. 라우트 접근성 확인
- /metadata/new → ContentForm 렌더링 됨
- /metadata/upload → UploadForm 렌더링 됨
- /metadata/external → 검색 폼 렌더링 됨
- /metadata/[id]/edit → ContentForm + initialData 렌더링 됨

# 2. 목록/상세 페이지 버튼 클릭 동작
- 목록의 [편집] → /metadata/[id]/edit로 이동
- 상세의 [편집] → /metadata/[id]/edit로 이동

# 3. AddContentModal 제거 확인
- 목록 페이지에 더 이상 "+ 추가" 모달 버튼 없음
```

## 영향 범위
- 프론트: 4개 새 페이지 + 공유 컴포넌트 2개 + 기존 페이지 수정 2곳
- 백엔드: PUT 엔드포인트 추가 (step 2에서 이미 구현)
- UX: 더 이상 모달 3개 플로우, 전용 페이지로 분리 → 직관적
- 후속: Step 4에서 각 페이지 입력 양식 상세 구현

## 주의
- /new, /upload, /external은 정인증된 사용자만 접근 (middleware 확인)
- 초기 로드 시 기존 콘텐츠 fetch는 나중에 (step 4에서 상세 구현)
- ContentForm이 신규/수정을 모두 처리하므로, initialData 로직 신중히
