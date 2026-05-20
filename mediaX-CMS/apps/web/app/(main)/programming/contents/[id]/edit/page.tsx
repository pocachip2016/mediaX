import { redirect } from "next/navigation"

export default async function EditRedirect({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  redirect(`/programming/contents/${id}?mode=edit`)
}
