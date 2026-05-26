"use client"

interface AutoGateContextProps {
  gateId: string
}

const GATE_DESCRIPTIONS: Record<string, string> = {
  GATE_2: "LLM 추출 완료 콘텐츠를 S4(소스 매칭)로 자동 이동합니다.",
  GATE_4: "WebSearch 보강 완료 콘텐츠를 S7(스테이징)으로 자동 이동합니다.",
}

export function AutoGateContext({ gateId }: AutoGateContextProps) {
  return (
    <div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
      <p className="font-medium">🤖 자동 처리 게이트</p>
      <p>{GATE_DESCRIPTIONS[gateId] || "조건 충족 시 자동으로 다음 단계로 이동합니다."}</p>
    </div>
  )
}
