"use client"

import { useState } from "react"
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core"
import type { DragEndEvent, DragStartEvent } from "@dnd-kit/core"
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Pin, PinOff, Trash2, Check, X } from "lucide-react"
import { schedulingApi } from "@/lib/api"
import type { ProgrammingLink, LinkStatus } from "@/lib/api"
import { cn } from "@workspace/ui/lib/utils"

const STATUS_LABELS: Record<LinkStatus, string> = {
  active: "활성",
  suggested: "추천",
  rejected: "거부",
}

const STATUS_CLASSES: Record<LinkStatus, string> = {
  active: "bg-green-100 text-green-700",
  suggested: "bg-amber-100 text-amber-700",
  rejected: "bg-red-100 text-red-600",
}

function LinkRow({ link, onReload }: { link: ProgrammingLink; onReload: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: link.id,
  })
  const [busy, setBusy] = useState(false)

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  }

  const label =
    link.child_content_id != null
      ? `콘텐츠 #${link.child_content_id}`
      : `노드 #${link.child_node_id}`

  async function act(fn: () => Promise<unknown>) {
    setBusy(true)
    await fn().catch(() => {})
    setBusy(false)
    onReload()
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2 bg-card hover:bg-accent/30 group",
        link.status === "rejected" && "opacity-50"
      )}
    >
      <button
        {...attributes}
        {...listeners}
        className="text-muted-foreground cursor-grab active:cursor-grabbing flex-shrink-0"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <span className="flex-1 truncate text-sm">{label}</span>

      {(link.window_start || link.window_end) && (
        <span className="text-xs text-muted-foreground whitespace-nowrap">
          {link.window_start?.slice(0, 10) ?? "…"}–{link.window_end?.slice(0, 10) ?? "…"}
        </span>
      )}

      <span className={cn("text-xs px-1.5 py-0.5 rounded-full font-medium flex-shrink-0", STATUS_CLASSES[link.status])}>
        {STATUS_LABELS[link.status]}
      </span>

      {link.status === "suggested" && (
        <>
          <button
            disabled={busy}
            onClick={() => act(() => schedulingApi.confirmLink(link.id))}
            title="확정"
            className="p-0.5 rounded hover:bg-green-100 text-green-600 disabled:opacity-50 flex-shrink-0"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
          <button
            disabled={busy}
            onClick={() => act(() => schedulingApi.rejectLink(link.id))}
            title="거부"
            className="p-0.5 rounded hover:bg-red-100 text-red-600 disabled:opacity-50 flex-shrink-0"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </>
      )}

      <button
        disabled={busy}
        onClick={() => act(() => schedulingApi.updateLink(link.id, { is_pinned: !link.is_pinned }))}
        title={link.is_pinned ? "고정 해제" : "고정"}
        className={cn(
          "p-0.5 rounded transition-opacity disabled:opacity-50 flex-shrink-0",
          link.is_pinned
            ? "text-amber-500 hover:bg-amber-50"
            : "text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-accent"
        )}
      >
        {link.is_pinned ? <Pin className="h-3.5 w-3.5" /> : <PinOff className="h-3.5 w-3.5" />}
      </button>

      <button
        disabled={busy}
        onClick={() => act(() => schedulingApi.deleteLink(link.id))}
        title="삭제"
        className="p-0.5 rounded text-muted-foreground opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 transition-opacity flex-shrink-0"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}

type Props = {
  nodeId: number | null
  links: ProgrammingLink[]
  onReload: () => void
}

export function LinkCanvas({ nodeId, links, onReload }: Props) {
  const [dragging, setDragging] = useState(false)
  const [localIds, setLocalIds] = useState<number[]>([])

  const sortedLinks = [...links].sort((a, b) => a.sort_order - b.sort_order)
  const displayIds = dragging ? localIds : sortedLinks.map((l) => l.id)
  const displayLinks = displayIds
    .map((id) => links.find((l) => l.id === id))
    .filter(Boolean) as ProgrammingLink[]

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  )

  function handleDragStart(_event: DragStartEvent) {
    setLocalIds(sortedLinks.map((l) => l.id))
    setDragging(true)
  }

  async function handleDragEnd(event: DragEndEvent) {
    setDragging(false)
    const { active, over } = event
    if (!over || active.id === over.id || !nodeId) return

    const oldIndex = localIds.indexOf(Number(active.id))
    const newIndex = localIds.indexOf(Number(over.id))
    const newIds = arrayMove(localIds, oldIndex, newIndex)
    setLocalIds(newIds)

    await schedulingApi.reorderLinks(nodeId, newIds).catch(() => {})
    onReload()
  }

  if (!nodeId) {
    return (
      <div className="h-full flex items-center justify-center border rounded-xl bg-card">
        <p className="text-sm text-muted-foreground">노드를 선택하세요</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col border rounded-xl bg-card overflow-hidden">
      <div className="px-4 py-2.5 border-b flex items-center justify-between flex-shrink-0">
        <span className="text-sm font-medium">링크 목록</span>
        <span className="text-xs text-muted-foreground">{links.length}개</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
        {links.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            링크가 없습니다. 왼쪽 팔레트에서 추가하세요.
          </p>
        ) : (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <SortableContext items={displayIds} strategy={verticalListSortingStrategy}>
              {displayLinks.map((link) => (
                <LinkRow key={link.id} link={link} onReload={onReload} />
              ))}
            </SortableContext>
          </DndContext>
        )}
      </div>
    </div>
  )
}
