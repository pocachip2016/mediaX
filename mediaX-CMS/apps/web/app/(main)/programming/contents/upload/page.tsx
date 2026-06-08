"use client"

import { ArrowLeft } from "lucide-react"
import Link from "next/link"
import { BulkUploadForm } from "@/components/contents/upload/BulkUploadForm"

export default function UploadPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/programming/contents" className="p-1.5 rounded-lg hover:bg-accent transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold">일괄 업로드</h1>
          <p className="text-sm text-muted-foreground">CSV 또는 Excel 파일로 여러 콘텐츠를 한 번에 등록합니다</p>
        </div>
      </div>

      <BulkUploadForm />
    </div>
  )
}
