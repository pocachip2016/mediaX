import { redirect } from "next/navigation"

export default async function RecommendRedirect({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}) {
  const { id } = await params
  const sp = await searchParams
  const qs = new URLSearchParams()
  qs.set("mode", "review")
  for (const [k, v] of Object.entries(sp)) {
    if (k === "mode") continue
    if (typeof v === "string") qs.set(k, v)
    else if (Array.isArray(v)) v.forEach((vv) => qs.append(k, vv))
  }
  redirect(`/programming/contents/${id}?${qs.toString()}`)
}
