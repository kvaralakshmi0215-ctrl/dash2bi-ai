import React from 'react'

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur p-6 shadow-xl shadow-black/20 ${className}`}>
      {children}
    </div>
  )
}

export function Badge({ tone = 'default', children }: { tone?: 'default' | 'success' | 'warn' | 'danger'; children: React.ReactNode }) {
  const tones: Record<string, string> = {
    default: 'bg-white/10 text-slate-200',
    success: 'bg-emerald-500/15 text-emerald-300',
    warn: 'bg-amber-500/15 text-amber-300',
    danger: 'bg-rose-500/15 text-rose-300',
  }
  return <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${tones[tone]}`}>{children}</span>
}

export function Button({
  children, onClick, disabled, variant = 'primary', className = '', type = 'button',
}: {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
  variant?: 'primary' | 'secondary' | 'ghost'
  className?: string
  type?: 'button' | 'submit'
}) {
  const variants: Record<string, string> = {
    primary: 'bg-gradient-to-r from-brand-500 to-brand-600 text-white hover:from-brand-400 hover:to-brand-500 shadow-lg shadow-brand-900/40',
    secondary: 'bg-white/10 text-white hover:bg-white/15',
    ghost: 'text-slate-300 hover:text-white hover:bg-white/5',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export function ProgressStep({ label, status }: { label: string; status: 'pending' | 'running' | 'done' | 'failed' }) {
  const icon = status === 'done' ? '✓' : status === 'failed' ? '✕' : status === 'running' ? '⏳' : '○'
  const color = status === 'done' ? 'text-emerald-400' : status === 'failed' ? 'text-rose-400' : status === 'running' ? 'text-amber-300' : 'text-slate-500'
  return (
    <div className="flex items-center gap-3 py-2">
      <span className={`w-6 text-center ${color}`}>{icon}</span>
      <span className={status === 'pending' ? 'text-slate-500' : 'text-slate-200'}>{label}</span>
    </div>
  )
}
