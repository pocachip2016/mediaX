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

export function addCustomTemplate(
  t: Omit<CustomTemplate, "id">,
): CustomTemplate {
  const template: CustomTemplate = {
    ...t,
    id: Date.now().toString(),
  }
  const all = getCustomTemplates()
  all.push(template)
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, JSON.stringify(all))
  }
  return template
}

export function deleteCustomTemplate(id: string): void {
  const all = getCustomTemplates()
  const filtered = all.filter((t) => t.id !== id)
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, JSON.stringify(filtered))
  }
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
