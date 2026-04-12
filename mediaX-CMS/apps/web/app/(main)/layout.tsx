import { SidebarProvider, SidebarInset } from "@workspace/ui/components/sidebar"
import { AppSidebar } from "@/components/layout/sidebar"
import { Header } from "@/components/layout/header"

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <Header />
        <div className="flex flex-1 flex-col gap-4 p-6 overflow-y-auto">
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
