export default function ContentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">콘텐츠 관리</h2>
        <p className="text-sm text-muted-foreground mt-1">
          VOD 콘텐츠를 등록하고 편성 상태를 관리합니다.
        </p>
      </div>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "전체 콘텐츠", value: "12,483", sub: "+124 이번 주" },
          { label: "편성 완료", value: "8,921", sub: "71.4%" },
          { label: "QC 대기", value: "342", sub: "처리 필요" },
          { label: "신규 입고", value: "56", sub: "오늘" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border bg-card p-5 shadow-sm"
          >
            <p className="text-xs text-muted-foreground">{stat.label}</p>
            <p className="mt-1 text-2xl font-bold">{stat.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{stat.sub}</p>
          </div>
        ))}
      </div>
      <div className="rounded-xl border bg-card p-6 shadow-sm">
        <p className="text-sm text-muted-foreground">콘텐츠 목록 테이블이 여기에 표시됩니다.</p>
      </div>
    </div>
  )
}
