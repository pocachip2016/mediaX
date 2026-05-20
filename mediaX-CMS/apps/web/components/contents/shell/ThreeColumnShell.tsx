"use client"

interface ThreeColumnShellProps {
  poster: React.ReactNode
  current: React.ReactNode
  right: React.ReactNode
  footer?: React.ReactNode
}

export function ThreeColumnShell({ poster, current, right, footer }: ThreeColumnShellProps) {
  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-4">
      <div className="grid grid-cols-[200px_1fr_1fr] gap-4 items-start">
        <div>{poster}</div>
        <div>{current}</div>
        <div>{right}</div>
      </div>
      {footer && <div>{footer}</div>}
    </div>
  )
}
