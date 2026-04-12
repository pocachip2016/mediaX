"use client"

import React, { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import Image from "next/image"
import {
  LayoutDashboard,
  Paintbrush,
  Upload,
  BarChart2,
  Megaphone,
  Activity,
  ChevronRight,
  type LucideIcon,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
} from "@workspace/ui/components/sidebar"
import { Collapsible, CollapsibleContent } from "@workspace/ui/components/collapsible"
import { Badge } from "@workspace/ui/components/badge"
import { cn } from "@workspace/ui/lib/utils"
import { docsNav, type NavSection } from "@/config/docs"
import { siteConfig } from "@/config/site-config"

/** 섹션 base → 아이콘 매핑 */
const SECTION_ICONS: Record<string, LucideIcon> = {
  "/programming": LayoutDashboard,
  "/design": Paintbrush,
  "/ingest": Upload,
  "/analytics": BarChart2,
  "/marketing": Megaphone,
  "/monitoring": Activity,
}

function NavGroup({
  section,
  pathname,
}: {
  section: NavSection
  pathname: string
}) {
  const isActive = pathname.startsWith(section.base)
  const [open, setOpen] = useState(isActive)
  const Icon = SECTION_ICONS[section.base] ?? LayoutDashboard
  // "LIVE" 뱃지: 섹션 내 아이템에 label 이 있으면 섹션에도 표시
  const sectionLabel = section.items.some((i) => i.label)
    ? section.items.find((i) => i.label)?.label
    : undefined

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="group/collapsible">
      <SidebarMenuItem>
        <SidebarMenuButton
          tooltip={section.title}
          isActive={isActive}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            isActive && "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
          )}
        >
          <Icon className="shrink-0" />
          <span className="flex-1 truncate">{section.title}</span>
          {sectionLabel && (
            <Badge variant="destructive" className="h-4 px-1 text-[10px] shrink-0">
              {sectionLabel}
            </Badge>
          )}
          <ChevronRight
            className={cn(
              "size-4 shrink-0 transition-transform duration-200",
              open && "rotate-90"
            )}
          />
        </SidebarMenuButton>

        <CollapsibleContent>
          <SidebarMenuSub>
            {section.items
              .filter((item) => !item.disabled)
              .map((item) => {
                const isItemActive = pathname === item.href
                return (
                  <SidebarMenuSubItem key={item.href ?? item.title}>
                    <SidebarMenuSubButton
                      asChild={!!item.href}
                      isActive={isItemActive}
                      className={cn(
                        "text-sidebar-foreground/60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                        isItemActive && "text-sidebar-accent-foreground font-medium"
                      )}
                    >
                      {item.href ? (
                        <Link
                          href={item.href}
                          target={item.external ? "_blank" : undefined}
                          rel={item.external ? "noopener noreferrer" : undefined}
                          className="flex w-full items-center justify-between"
                        >
                          <span>{item.title}</span>
                          {item.label && (
                            <Badge
                              variant={item.label === "LIVE" ? "destructive" : "secondary"}
                              className="h-4 px-1 text-[10px]"
                            >
                              {item.label}
                            </Badge>
                          )}
                        </Link>
                      ) : (
                        <span>{item.title}</span>
                      )}
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                )
              })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  )
}

export function AppSidebar() {
  const pathname = usePathname()

  return (
    <Sidebar collapsible="icon">
      {/* 로고 */}
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild tooltip={siteConfig.name}>
              <Link href={siteConfig.defaultPath} className="flex items-center gap-2">
                {/* 아이콘 영역 — collapsed 시 이것만 표시 */}
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground font-black text-xs tracking-tight select-none">
                  MX
                </div>
                {/* 텍스트 영역 — expanded 시 표시 */}
                <div className="grid flex-1 text-left leading-snug min-w-0">
                  <span className="truncate text-sm font-bold text-sidebar-foreground tracking-tight">
                    {siteConfig.name}
                  </span>
                  {/* made by kt alpha 로고 */}
                  <span className="flex items-center gap-1 text-[10px] text-sidebar-foreground/40 leading-none mt-0.5">
                    made by
                    <Image
                      src="/kt-alpha-logo.svg"
                      alt="kt alpha"
                      width={44}
                      height={14}
                      className="opacity-60 mt-px"
                      priority
                    />
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      {/* 네비게이션 — docsNav 데이터 기반 */}
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="uppercase text-[10px] tracking-widest">
            플랫폼 메뉴
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {docsNav.map((section) => (
                <NavGroup key={section.base} section={section} pathname={pathname} />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      {/* 푸터 */}
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton className="cursor-default text-[11px] text-sidebar-foreground/30 hover:bg-transparent">
              <span>
                {siteConfig.name} v{siteConfig.version} · {siteConfig.stage}
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
