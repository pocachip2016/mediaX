"use client"

import { useState, useCallback } from "react"
import { metadataApi } from "@/lib/api"
import type { ContentDetail, FieldRecommendation, RecommendationsOut, SourceFieldRec } from "@/lib/api"
import type { BulkTarget } from "@/components/contents/BulkActionModal"

interface ModalState {
  open: boolean
  action: "approve" | "reject" | "reprocess" | "rematch"
  targets: BulkTarget[]
}

interface UseContentReviewActionsOpts {
  content: ContentDetail | null
  recommendations?: RecommendationsOut | null
  onRefetch?: () => Promise<void>
  onNavigateAfterDecision?: () => void
}

export function useContentReviewActions(
  contentId: number,
  opts: UseContentReviewActionsOpts
) {
  const { content, recommendations, onRefetch, onNavigateAfterDecision } = opts
  const [appliedFields, setAppliedFields] = useState<Set<string>>(new Set())
  const [modalState, setModalState] = useState<ModalState>({
    open: false,
    action: "approve",
    targets: [],
  })

  const refetch = useCallback(async () => {
    await onRefetch?.()
  }, [onRefetch])

  const applyRec = useCallback(
    async (rec: FieldRecommendation, source: SourceFieldRec) => {
      try {
        if (source.source_type === "ai") {
          await metadataApi.promoteAIResult(contentId, source.source_id)
        } else {
          await metadataApi.applyExternalFields(contentId, source.source_id, [rec.field])
        }
        setAppliedFields((prev) => new Set([...prev, rec.field]))
        await refetch()
      } catch (err) {
        console.error("applyRec failed", err)
      }
    },
    [contentId, refetch]
  )

  const applyAllAuto = useCallback(async () => {
    if (!recommendations) return
    for (const rec of recommendations.auto_fill) {
      const top = rec.recommendations[0]
      if (top) await applyRec(rec, top)
    }
  }, [recommendations, applyRec])

  const applyExternalFields = useCallback(
    async (sourceId: number, fields?: string[]) => {
      try {
        await metadataApi.applyExternalFields(contentId, sourceId, fields)
        await refetch()
      } catch (err) {
        console.error("applyExternalFields failed", err)
      }
    },
    [contentId, refetch]
  )

  const promoteAIResult = useCallback(
    async (resultId: number) => {
      try {
        await metadataApi.promoteAIResult(contentId, resultId)
        await refetch()
      } catch (err) {
        console.error("promoteAIResult failed", err)
      }
    },
    [contentId, refetch]
  )

  const regenerate = useCallback(async () => {
    try {
      await metadataApi.triggerEnrich(contentId)
      await refetch()
    } catch (err) {
      console.error("regenerate failed", err)
    }
  }, [contentId, refetch])

  const partialReprocess = useCallback(
    async (fields?: string[]) => {
      try {
        await metadataApi.partialReprocess(contentId, fields)
      } catch (err) {
        console.error("partialReprocess failed", err)
      }
    },
    [contentId]
  )

  const lockFields = useCallback(
    async (fields: string[], reason?: string) => {
      try {
        await metadataApi.lockFields(contentId, fields, reason)
      } catch (err) {
        console.error("lockFields failed", err)
      }
    },
    [contentId]
  )

  const requestPreviewClip = useCallback(async () => {
    try {
      await metadataApi.requestPreviewClip(contentId)
    } catch (err) {
      console.error("requestPreviewClip failed", err)
    }
  }, [contentId])

  const openModal = useCallback(
    (action: ModalState["action"]) => {
      if (!content) return
      setModalState({
        open: true,
        action,
        targets: [
          {
            id: content.id,
            title: content.title,
            cp_name: content.cp_name,
            status: content.status,
          },
        ],
      })
    },
    [content]
  )

  const approve = useCallback(() => openModal("approve"), [openModal])
  const reject = useCallback(() => openModal("reject"), [openModal])
  const reprocess = useCallback(() => openModal("reprocess"), [openModal])
  const rematch = useCallback(() => openModal("rematch"), [openModal])

  const dismissModal = useCallback(() => {
    setModalState((prev) => ({ ...prev, open: false }))
    onNavigateAfterDecision?.()
  }, [onNavigateAfterDecision])

  return {
    appliedFields,
    applyRec,
    applyAllAuto,
    applyExternalFields,
    promoteAIResult,
    regenerate,
    partialReprocess,
    lockFields,
    requestPreviewClip,
    approve,
    reject,
    reprocess,
    rematch,
    dismissModal,
    modalState,
  }
}
