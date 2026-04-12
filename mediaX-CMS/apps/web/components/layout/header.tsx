"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Bell, User, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@workspace/ui/components/button"
import { SidebarTrigger } from "@workspace/ui/components/sidebar"
import { Separator } from "@workspace/ui/components/separator"
import { getBreadcrumbs } from "@/lib/nav"
import { siteConfig } from "@/config/site-config"

export function Header() {
  const pathname = usePathname()
  const { resolvedTheme, setTheme } = useTheme()
  const crumbs = getBreadcrumbs(pathname)

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mx-1 h-4" />

      {/* Breadcrumb */}
      <nav aria-label="breadcrumb" className="flex flex-1 items-center gap-1 text-sm min-w-0">
        {crumbs.length === 0 ? (
          <span className="font-medium">{siteConfig.name}</span>
        ) : (
          crumbs.map((crumb, i) => {
            const isLast = i === crumbs.length - 1
            return (
              <span key={`${i}-${crumb.href}`} className="flex items-center gap-1 min-w-0">
                {i > 0 && (
                  <span className="text-muted-foreground/50 shrink-0" aria-hidden>
                    /
                  </span>
                )}
                {isLast ? (
                  <span className="font-medium truncate" aria-current="page">
                    {crumb.title}
                  </span>
                ) : (
                  <Link
                    href={crumb.href}
                    className="text-muted-foreground hover:text-foreground truncate transition-colors"
                  >
                    {crumb.title}
                  </Link>
                )}
              </span>
            )
          })
        )}
      </nav>

      {/* 액션 */}
      <div className="flex items-center gap-1 shrink-0">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
          aria-label="테마 전환"
        >
          {resolvedTheme === "dark" ? (
            <Sun className="size-4" />
          ) : (
            <Moon className="size-4" />
          )}
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="알림">
          <Bell className="size-4" />
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="사용자">
          <User className="size-4" />
        </Button>
      </div>
    </header>
  )
}
