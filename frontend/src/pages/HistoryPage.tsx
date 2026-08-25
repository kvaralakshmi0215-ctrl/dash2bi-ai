import { useEffect, useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import { Card, Badge, Button } from '../components/ui'
import * as api from '../api/client'

interface HistoryItem {
  conversion_id: string
  session_id: string
  status: string
  created_at: string
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getHistory().then(setItems).finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Conversion history</h1>
      <p className="text-slate-400 mt-1 text-sm">Past Power BI project generations from this backend.</p>

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 mt-8"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
      ) : items.length === 0 ? (
        <Card className="mt-6 text-center text-slate-500 text-sm">No conversions yet.</Card>
      ) : (
        <Card className="mt-6 !p-0 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-white/5 text-slate-400 text-xs">
                <th className="text-left px-4 py-3 font-medium">Conversion ID</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.conversion_id} className="border-t border-white/5">
                  <td className="px-4 py-3 text-slate-300 font-mono text-xs">{it.conversion_id.slice(0, 8)}…</td>
                  <td className="px-4 py-3">
                    <Badge tone={it.status === 'completed' ? 'success' : it.status === 'failed' ? 'danger' : 'warn'}>{it.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{new Date(it.created_at).toLocaleString()}</td>
                  <td className="px-4 py-3 text-right">
                    {it.status === 'completed' && (
                      <Button variant="ghost" onClick={() => window.open(api.downloadUrl(it.conversion_id), '_blank')}>
                        <Download className="w-4 h-4" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
