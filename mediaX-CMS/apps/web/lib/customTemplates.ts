import type { CategoryNode } from "@/lib/api"

export interface CustomTemplate {
  id: string
  label: string
  description: string
  text: string
}

const KEY = "mediax:category-templates"

export function getCustomTemplates(): CustomTemplate[] {
  if (typeof window === "undefined") return []
  try {
    const json = localStorage.getItem(KEY)
    return json ? JSON.parse(json) : []
  } catch {
    return []
  }
}

function _persist(all: CustomTemplate[]): void {
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, JSON.stringify(all))
    window.dispatchEvent(new CustomEvent("custom-templates-changed"))
  }
}

export function findTemplateByLabel(label: string): CustomTemplate | undefined {
  return getCustomTemplates().find(
    (t) => t.label.trim().toLowerCase() === label.trim().toLowerCase(),
  )
}

export function addCustomTemplate(
  t: Omit<CustomTemplate, "id">,
): CustomTemplate {
  const template: CustomTemplate = { ...t, id: Date.now().toString() }
  const all = getCustomTemplates()
  all.push(template)
  _persist(all)
  return template
}

export function upsertCustomTemplate(
  t: Omit<CustomTemplate, "id">,
): CustomTemplate {
  const all = getCustomTemplates()
  const idx = all.findIndex(
    (x) => x.label.trim().toLowerCase() === t.label.trim().toLowerCase(),
  )
  if (idx >= 0) {
    const updated: CustomTemplate = { id: all[idx]!.id, ...t }
    all[idx] = updated
    _persist(all)
    return updated
  }
  return addCustomTemplate(t)
}

export function deleteCustomTemplate(id: string): void {
  const filtered = getCustomTemplates().filter((t) => t.id !== id)
  _persist(filtered)
}

export function serializeTree(
  nodes: CategoryNode[],
  depth: number = 0,
): string {
  const indent = "  ".repeat(depth)
  return nodes
    .map((node) => {
      const line = `${indent}${node.name}`
      const childrenText =
        node.children && node.children.length > 0
          ? "\n" + serializeTree(node.children, depth + 1)
          : ""
      return line + childrenText
    })
    .join("\n")
}
