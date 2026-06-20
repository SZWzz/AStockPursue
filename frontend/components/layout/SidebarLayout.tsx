// frontend/components/layout/SidebarLayout.tsx
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function SidebarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <Sidebar />
      <Header />
      <main
        className="pt-[var(--header-height)] transition-all"
        style={{ paddingLeft: 'var(--sidebar-width)', padding: 'var(--header-height) 0 0 var(--sidebar-width)' }}
      >
        <div className="p-[var(--page-padding)]">
          {children}
        </div>
      </main>
    </div>
  )
}
