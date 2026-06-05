import type { ContentOut } from "@/lib/api"

export interface ContentTreeNode {
  item: ContentOut
  children: ContentTreeNode[]
}

export function buildContentTree(contents: ContentOut[]): {
  roots: ContentTreeNode[]
  idMap: Map<number, ContentTreeNode>
} {
  const idMap = new Map<number, ContentTreeNode>()
  for (const c of contents) idMap.set(c.id, { item: c, children: [] })

  const roots: ContentTreeNode[] = []
  for (const c of contents) {
    const node = idMap.get(c.id)!
    const parentNode = c.parent_id != null ? idMap.get(c.parent_id) : undefined
    if (parentNode) {
      parentNode.children.push(node)
    } else {
      roots.push(node)
    }
  }

  // series > season > episode 순으로 정렬
  const typeOrder: Record<string, number> = { series: 0, season: 1, episode: 2, movie: 3 }
  const sort = (nodes: ContentTreeNode[]) => {
    nodes.sort((a, b) => {
      const to = (typeOrder[a.item.content_type] ?? 9) - (typeOrder[b.item.content_type] ?? 9)
      if (to !== 0) return to
      const sn = (a.item.season_number ?? 0) - (b.item.season_number ?? 0)
      if (sn !== 0) return sn
      return (a.item.episode_number ?? 0) - (b.item.episode_number ?? 0)
    })
    nodes.forEach((n) => sort(n.children))
  }
  sort(roots)
  return { roots, idMap }
}

export function countDescendants(node: ContentTreeNode): number {
  return node.children.reduce((acc, c) => acc + 1 + countDescendants(c), 0)
}
