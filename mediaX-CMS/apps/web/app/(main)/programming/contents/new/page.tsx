"use client"

import { ContentForm } from "@/components/contents/ContentForm"
import { ArrowLeft } from "lucide-react"
import Link from "next/link"

export default function NewContentPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link
          href="/programming/contents"
          className="p-1.5 rounded-lg hover:bg-accent transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">콘텐츠 등록</h1>
          <p className="text-sm text-muted-foreground">단일 콘텐츠를 직접 입력해 등록합니다</p>
        </div>
      </div>
      <ContentForm />
    </div>
  )
}
