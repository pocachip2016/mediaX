"use client"

import { SingleContentForm } from "@/components/contents/SingleContentForm"

export default function NewContentPage() {
  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <SingleContentForm />
      </div>
    </div>
  )
}
