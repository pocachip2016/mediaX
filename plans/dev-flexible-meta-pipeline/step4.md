# Step 4: 수동 입력 페이지 구현

## 배경
Step 3에서 라우트와 IA 구조만 정의했으므로, 이제 각 페이지의 세부 UI 구현과 폼 검증 필요.
- /new: 단일 콘텐츠 등록
- /upload: CSV/Excel 벌크 업로드
- /external: TMDB/KOBIS 검색 후 선택
- /[id]/edit: 기존 콘텐츠 수정

## 목표
- ContentForm: 필드 검증 + UI (제목, CP사, 년도, 타입, 줄거리, 출연진, 감독, 장르, 국가, 런타임, 시청등급, 포스터)
- UploadForm: 파일 선택 + 미리보기 + 업로드 진행 표시
- ExternalSearch: TMDB/KOBIS 검색 → 결과 테이블 → 선택 → 벌크 추가
- 에러 처리 + 로딩 상태 + 성공 피드백

## 구현 상세

### 1. ContentForm 상세 구현
```tsx
// apps/web/components/metadata/ContentForm.tsx

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { Input, Select, Textarea, Button, Card, Badge } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";

interface ContentFormData {
  title: string;
  production_year: number;
  content_type: "movie" | "series" | "season" | "episode";
  cp_name: string;
  synopsis?: string;
  cast?: string;           // "배우1, 배우2, ..."
  directors?: string;      // "감독1, 감독2, ..."
  genres?: string;         // "드라마, 판타지, ..."
  country?: string;
  runtime?: number;        // 분 단위
  rating_age?: string;
  poster_url?: string;
}

interface ContentFormProps {
  contentId?: number;
  initialData?: Partial<ContentFormData>;
  onSuccess?: (contentId: number) => void;
}

export default function ContentForm({
  contentId,
  initialData,
  onSuccess,
}: ContentFormProps) {
  const router = useRouter();
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    watch,
  } = useForm<ContentFormData>({
    defaultValues: {
      production_year: new Date().getFullYear(),
      content_type: "movie",
      ...initialData,
    },
  });

  const onSubmit = async (data: ContentFormData) => {
    try {
      setLoading(true);

      const url = contentId
        ? `/api/programming/metadata/contents/${contentId}`
        : "/api/programming/metadata/contents";

      const method = contentId ? "PUT" : "POST";

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "요청 실패");
      }

      const result = await res.json();
      toast({
        title: contentId ? "수정 완료" : "등록 완료",
        description: `"${data.title}"이(가) ${contentId ? "수정" : "등록"}되었습니다.`,
      });

      if (onSuccess) {
        onSuccess(result.id);
      } else {
        router.push(`/metadata/contents/${result.id}`);
      }
    } catch (err) {
      toast({
        title: "오류",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">
        {contentId ? "콘텐츠 수정" : "콘텐츠 등록"}
      </h1>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* 필수 필드 */}
        <div className="space-y-2">
          <label className="block text-sm font-semibold">
            제목 <span className="text-red-500">*</span>
          </label>
          <Input
            {...register("title", {
              required: "제목은 필수입니다",
            })}
            placeholder="콘텐츠 제목"
            error={errors.title?.message}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="block text-sm font-semibold">
              제작년도 <span className="text-red-500">*</span>
            </label>
            <Input
              type="number"
              {...register("production_year", {
                required: "제작년도는 필수입니다",
                min: { value: 1900, message: "1900 이상이어야 합니다" },
              })}
              placeholder="2024"
              error={errors.production_year?.message}
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-semibold">
              콘텐츠 유형 <span className="text-red-500">*</span>
            </label>
            <Select {...register("content_type", { required: true })}>
              <option value="movie">영화</option>
              <option value="series">시리즈</option>
              <option value="season">시즌</option>
              <option value="episode">에피소드</option>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-semibold">
            CP사 <span className="text-red-500">*</span>
          </label>
          <Input
            {...register("cp_name", { required: "CP사는 필수입니다" })}
            placeholder="CP사명"
            error={errors.cp_name?.message}
          />
        </div>

        {/* 선택 필드 */}
        <div className="bg-gray-50 p-4 rounded-lg space-y-4">
          <h2 className="font-semibold text-sm">추가 메타데이터 (선택)</h2>

          <div className="space-y-2">
            <label className="text-sm">줄거리</label>
            <Textarea
              {...register("synopsis")}
              placeholder="콘텐츠 줄거리를 입력하세요"
              rows={3}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm">출연진 (쉼표 구분)</label>
              <Input
                {...register("cast")}
                placeholder="배우1, 배우2, ..."
              />
              <p className="text-xs text-gray-500">
                여러 명일 경우 쉼표로 구분하세요
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm">감독 (쉼표 구분)</label>
              <Input
                {...register("directors")}
                placeholder="감독1, 감독2, ..."
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm">장르 (쉼표 구분)</label>
            <Input
              {...register("genres")}
              placeholder="드라마, 판타지, ..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm">제작국가</label>
              <Input {...register("country")} placeholder="한국" />
            </div>

            <div className="space-y-2">
              <label className="text-sm">런타임 (분)</label>
              <Input
                type="number"
                {...register("runtime", { valueAsNumber: true })}
                placeholder="120"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm">시청등급</label>
              <Select {...register("rating_age")}>
                <option value="">선택 안함</option>
                <option value="전체이용가">전체이용가</option>
                <option value="12세이상">12세 이상</option>
                <option value="15세이상">15세 이상</option>
                <option value="18세이상">18세 이상</option>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm">포스터 URL</label>
              <Input
                {...register("poster_url")}
                placeholder="https://..."
              />
            </div>
          </div>
        </div>

        {/* 버튼 */}
        <div className="flex gap-2 pt-4">
          <Button
            type="submit"
            disabled={isSubmitting || loading}
            className="flex-1"
          >
            {isSubmitting || loading ? "저장 중..." : contentId ? "수정" : "등록"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
          >
            취소
          </Button>
        </div>
      </form>
    </Card>
  );
}
```

### 2. UploadForm 구현
```tsx
// apps/web/components/metadata/UploadForm.tsx

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Button, Badge, Progress } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";

export default function UploadForm() {
  const router = useRouter();
  const { toast } = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    // 파일 검증 (CSV, Excel)
    const isCSV = selectedFile.type === "text/csv";
    const isExcel =
      selectedFile.type ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" ||
      selectedFile.type === "application/vnd.ms-excel";

    if (!isCSV && !isExcel) {
      toast({
        title: "파일 형식 오류",
        description: "CSV 또는 Excel 파일만 업로드 가능합니다",
        variant: "destructive",
      });
      return;
    }

    setFile(selectedFile);

    // 미리보기: 첫 5행 파싱
    if (isCSV) {
      const text = await selectedFile.text();
      const lines = text.split("\n").slice(0, 6); // 헤더 + 5행
      const headers = lines[0].split(",");
      const rows = lines
        .slice(1)
        .filter((l) => l.trim())
        .map((line) => {
          const cells = line.split(",");
          return headers.reduce(
            (acc, h, i) => ({ ...acc, [h.trim()]: cells[i]?.trim() || "" }),
            {}
          );
        });
      setPreview(rows);
    } else {
      // Excel 미리보기는 라이브러리 필요 (xlsx)
      toast({
        title: "알림",
        description: "Excel 파일은 업로드 시 파싱됩니다",
      });
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    try {
      setUploading(true);
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(
        "/api/programming/metadata/upload/batch",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "업로드 실패");
      }

      const result = await res.json();
      toast({
        title: "업로드 완료",
        description: `${result.length}개 콘텐츠가 등록되었습니다`,
      });

      router.push("/metadata/contents");
    } catch (err) {
      toast({
        title: "오류",
        description: err.message,
        variant: "destructive",
      });
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <Card className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">일괄 업로드</h1>

      <div className="space-y-6">
        {/* 파일 선택 */}
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-gray-500 transition">
          <input
            type="file"
            accept=".csv,.xlsx"
            onChange={handleFileChange}
            className="hidden"
            id="fileInput"
          />
          <label htmlFor="fileInput" className="cursor-pointer">
            <div className="text-4xl mb-2">📤</div>
            <p className="font-semibold">CSV 또는 Excel 파일을 선택하세요</p>
            <p className="text-sm text-gray-500 mt-2">
              또는 파일을 여기에 드래그하세요
            </p>
          </label>
        </div>

        {/* 선택된 파일 정보 */}
        {file && (
          <div className="bg-blue-50 p-4 rounded-lg">
            <p className="font-semibold text-sm">
              선택된 파일: <Badge>{file.name}</Badge>
            </p>
            <p className="text-xs text-gray-600 mt-1">
              크기: {(file.size / 1024).toFixed(2)} KB
            </p>
          </div>
        )}

        {/* 미리보기 */}
        {preview.length > 0 && (
          <div className="space-y-2">
            <h2 className="font-semibold text-sm">미리보기</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse border border-gray-300">
                <thead className="bg-gray-100">
                  <tr>
                    {Object.keys(preview[0]).map((key) => (
                      <th
                        key={key}
                        className="border border-gray-300 px-3 py-2 text-left"
                      >
                        {key}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((val, j) => (
                        <td
                          key={j}
                          className="border border-gray-300 px-3 py-2"
                        >
                          {String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 필드 설명 */}
        <div className="bg-yellow-50 p-4 rounded-lg text-sm">
          <p className="font-semibold mb-2">필드 설명</p>
          <ul className="space-y-1 text-xs">
            <li>
              <strong>title</strong>: 콘텐츠 제목 (필수)
            </li>
            <li>
              <strong>production_year</strong>: 제작년도 (선택)
            </li>
            <li>
              <strong>content_type</strong>: movie/series/season/episode
              (필수)
            </li>
            <li>
              <strong>cp_name</strong>: CP사명 (필수)
            </li>
            <li>
              <strong>synopsis</strong>: 줄거리 (선택)
            </li>
            <li>
              <strong>cast</strong>: 출연진 (쉼표 구분) (선택)
            </li>
            <li>
              <strong>directors</strong>: 감독 (쉼표 구분) (선택)
            </li>
            <li>
              <strong>genres</strong>: 장르 (쉼표 구분) (선택)
            </li>
          </ul>
        </div>

        {/* 진행 표시 */}
        {uploading && (
          <div className="space-y-2">
            <Progress value={progress} className="w-full" />
            <p className="text-sm text-gray-600 text-center">
              업로드 중... {progress}%
            </p>
          </div>
        )}

        {/* 버튼 */}
        <div className="flex gap-2 pt-4">
          <Button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="flex-1"
          >
            {uploading ? "업로드 중..." : "업로드"}
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setFile(null);
              setPreview([]);
            }}
            disabled={uploading}
          >
            취소
          </Button>
        </div>
      </div>
    </Card>
  );
}
```

### 3. ExternalSearch 구현 (스케치)
```tsx
// apps/web/components/metadata/ExternalSearch.tsx

export default function ExternalSearch() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<"tmdb" | "kobis">("tmdb");
  const [results, setResults] = useState<any[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());

  const handleSearch = async () => {
    const res = await fetch(
      `/api/programming/metadata/search/external?q=${query}&source=${source}`
    );
    const data = await res.json();
    setResults(data);
  };

  const handleSelectMultiple = (indices: number[]) => {
    const newSet = new Set(selected);
    indices.forEach((i) => {
      if (newSet.has(i)) newSet.delete(i);
      else newSet.add(i);
    });
    setSelected(newSet);
  };

  const handleAddToUpload = async () => {
    // 선택된 결과를 external_meta_sources 형태로 변환 후
    // 백엔드에 /contents/import 엔드포인트로 전송
    // 또는 /upload/batch에 raw_json 목록 전송
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="검색어"
        />
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="tmdb">TMDB</option>
          <option value="kobis">KOBIS</option>
        </select>
        <button onClick={handleSearch}>검색</button>
      </div>
      {/* 결과 테이블 + 체크박스 */}
      {/* [선택 항목 추가] 버튼 → /upload로 이동 */}
    </div>
  );
}
```

## 검증 방법
```bash
# 1. /new 페이지 수동 테스트
curl http://localhost:3000/metadata/new
# → ContentForm 렌더링 확인

# 2. 폼 제출 테스트
curl -X POST http://localhost:8000/api/programming/metadata/contents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "테스트 영화",
    "production_year": 2024,
    "content_type": "movie",
    "cp_name": "테스트CP",
    "synopsis": "테스트 줄거리",
    "cast": "배우1, 배우2",
    "directors": "감독1"
  }'

# 3. /upload 페이지 CSV 업로드 테스트
# 메뉴얼 테스트: CSV 파일 선택 → 미리보기 → 업로드

# 4. /[id]/edit 페이지 로드 테스트
curl http://localhost:3000/metadata/1/edit
# → ContentForm with initialData 렌더링 확인
```

## 영향 범위
- 프론트: 4개 페이지 전체 UI 구현
- 백엔드: 검증 로직 (존재 확인), resolve_metadata 호출 (step 2에서 이미 구현)
- 사용자 경험: 전용 페이지로 분리된 자연스러운 워크플로우

## 주의
- 필드 검증: 필수/선택 명확히 (title, production_year, content_type, cp_name 필수)
- 쉼표 구분 파싱: 백엔드에서 _parse_list()로 정규화
- 로딩/에러 상태: toast 메시지로 명확한 피드백
- 미리보기: 파일 파싱 시 인코딩 주의 (UTF-8 기본)
