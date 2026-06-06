import type { BulkCategoryNode, CategoryNode } from "./api"

// ── 타입 ─────────────────────────────────────────────────────────────────────

export interface LineError {
  line: number
  text: string
  message: string
}

export interface ParseResult {
  nodes: BulkCategoryNode[]
  errors: LineError[]
  format: "indent" | "path"
}

export interface DiffItem {
  node: BulkCategoryNode
  path: string[]       // 최상위부터의 전체 경로
  isNew: boolean       // false = 동일 경로 기존 존재 (중복)
}

export interface DiffResult {
  items: DiffItem[]
  newCount: number
  dupCount: number
}

// ── TEST 데이터 ───────────────────────────────────────────────────────────────

export const CATEGORY_TEST_DATA = `영화
  액션
    할리우드 액션
    아시아 액션
  코미디
    로맨틱 코미디
    블랙 코미디
  드라마
  SF/판타지
  공포/스릴러
  다큐멘터리
시리즈
  드라마 시리즈
    미니시리즈
    장편 시리즈
  예능/버라이어티
  애니메이션
    키즈 애니메이션
    성인 애니메이션
  다큐 시리즈
키즈
  교육
  엔터테인먼트
  애니메이션
외국 콘텐츠
  미국/캐나다
  영국/유럽
  일본
  중국/아시아`.trim()

// ── 파서 유틸 ─────────────────────────────────────────────────────────────────

function detectFormat(lines: string[]): "indent" | "path" {
  // 비어있지 않은 라인 중 하나라도 `/` 포함 & 들여쓰기 없으면 path 모드
  const nonEmpty = lines.filter((l) => l.trim())
  const hasSlash = nonEmpty.some((l) => l.trim().includes("/"))
  const hasIndent = nonEmpty.some((l) => l.match(/^[ \t]+/))
  return hasSlash && !hasIndent ? "path" : "indent"
}

function detectIndentUnit(lines: string[]): number {
  // 들여쓰기 있는 첫 라인의 공백 수를 기본 단위로 삼음 (탭=2)
  for (const line of lines) {
    const m = line.match(/^( +|\t+)/)
    if (m) {
      if (m[1]!.includes("\t")) return 2
      return m[1]!.length
    }
  }
  return 2
}

function parseIndent(text: string): ParseResult {
  const rawLines = text.split("\n")
  const errors: LineError[] = []
  const root: BulkCategoryNode[] = []
  const stack: Array<{ node: BulkCategoryNode; depth: number }> = []
  const unit = detectIndentUnit(rawLines)

  for (let i = 0; i < rawLines.length; i++) {
    const raw = rawLines[i]!
    if (!raw.trim()) continue

    const m = raw.match(/^([ \t]*)(.+)$/)
    if (!m) continue

    const indent = m[1]!.replace(/\t/g, " ".repeat(unit))
    const name = m[2]!.trim()
    const spaces = indent.length
    const depth = unit > 0 ? Math.floor(spaces / unit) : 0

    // 들여쓰기 불규칙 체크
    if (spaces % unit !== 0) {
      errors.push({
        line: i + 1,
        text: raw.trim(),
        message: `들여쓰기 불일치 (공백 ${spaces}개, 단위 ${unit})`,
      })
      continue
    }

    const node: BulkCategoryNode = { name, children: [] }

    if (depth === 0) {
      root.push(node)
      stack.length = 0
      stack.push({ node, depth: 0 })
    } else {
      // 스택에서 depth-1인 부모 찾기
      while (stack.length > 0 && stack[stack.length - 1]!.depth >= depth) {
        stack.pop()
      }
      if (stack.length === 0) {
        errors.push({
          line: i + 1,
          text: raw.trim(),
          message: `들여쓰기 과다 (depth ${depth}인데 부모 없음)`,
        })
        continue
      }
      const parent = stack[stack.length - 1]!.node
      if (!parent.children) parent.children = []
      parent.children.push(node)
      stack.push({ node, depth })
    }
  }

  return { nodes: root, errors, format: "indent" }
}

function parsePath(text: string): ParseResult {
  const rawLines = text.split("\n")
  const errors: LineError[] = []
  const root: BulkCategoryNode[] = []

  // path 노드를 중복 없이 머지하는 유틸
  function ensurePath(parts: string[], container: BulkCategoryNode[]): void {
    if (parts.length === 0) return
    const name = parts[0]!
    let found = container.find((n) => n.name === name)
    if (!found) {
      found = { name, children: [] }
      container.push(found)
    }
    if (parts.length > 1) {
      if (!found.children) found.children = []
      ensurePath(parts.slice(1), found.children)
    }
  }

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i]!.trim()
    if (!line) continue
    const parts = line.split("/").map((p) => p.trim()).filter(Boolean)
    if (parts.length === 0) {
      errors.push({ line: i + 1, text: line, message: "빈 경로" })
      continue
    }
    ensurePath(parts, root)
  }

  return { nodes: root, errors, format: "path" }
}

export function parseBulk(text: string): ParseResult {
  const trimmed = text.trim()
  if (!trimmed) return { nodes: [], errors: [], format: "indent" }
  const lines = trimmed.split("\n")
  const format = detectFormat(lines)
  return format === "path" ? parsePath(trimmed) : parseIndent(trimmed)
}

// ── diff ─────────────────────────────────────────────────────────────────────

function flattenTree(nodes: CategoryNode[], path: string[] = []): Set<string> {
  const paths = new Set<string>()
  for (const n of nodes) {
    const p = [...path, n.name]
    paths.add(p.join("\0"))
    if (n.children?.length) {
      flattenTree(n.children, p).forEach((s) => paths.add(s))
    }
  }
  return paths
}

function collectDiffItems(
  nodes: BulkCategoryNode[],
  existingPaths: Set<string>,
  path: string[],
  out: DiffItem[]
): void {
  for (const node of nodes) {
    const nodePath = [...path, node.name]
    const key = nodePath.join("\0")
    out.push({ node, path: nodePath, isNew: !existingPaths.has(key) })
    if (node.children?.length) {
      collectDiffItems(node.children, existingPaths, nodePath, out)
    }
  }
}

export function diffAgainstTree(parsed: BulkCategoryNode[], existingTree: CategoryNode[]): DiffResult {
  const existingPaths = flattenTree(existingTree)
  const items: DiffItem[] = []
  collectDiffItems(parsed, existingPaths, [], items)
  const newCount = items.filter((i) => i.isNew).length
  const dupCount = items.filter((i) => !i.isNew).length
  return { items, newCount, dupCount }
}
