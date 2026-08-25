import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Upload, ScanSearch, Eye, RefreshCw, History, Settings, Sparkles,
} from 'lucide-react'

const items = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload', label: 'Upload', icon: Upload },
  { to: '/analyze', label: 'Analyze', icon: ScanSearch },
  { to: '/preview', label: 'Preview', icon: Eye },
  { to: '/conversion', label: 'Conversion', icon: RefreshCw },
  { to: '/history', label: 'History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 border-r border-white/5 bg-slate-950/60 backdrop-blur px-4 py-6">
      <div className="flex items-center gap-2 px-2 mb-8">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-brand-700 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="text-white font-semibold tracking-tight">Dash2BI AI</span>
      </div>
      <nav className="flex flex-col gap-1">
        {items.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-brand-500/15 text-brand-100 font-medium'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto px-2 text-xs text-slate-600">
        Excel + HTML → Power BI Project
      </div>
    </aside>
  )
}
