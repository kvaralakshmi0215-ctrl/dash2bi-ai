import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ArrowRight, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react'
import { Card, Button, Badge } from '../components/ui'
import { useWorkflow } from '../state/WorkflowContext'
import * as api from '../api/client'
import type { FieldMapping } from '../types'

const levelBadge: Record<FieldMapping['level'], { tone: 'success' | 'warn' | 'danger'; label: string; Icon: typeof CheckCircle2 }> = {
  automatic: { tone: 'success', label: 'Automatic', Icon: CheckCircle2 },
  ai_suggested: { tone: 'warn', label: 'AI Suggested', Icon: AlertTriangle },
  unsupported: { tone: 'danger', label: 'Unsupported', Icon: XCircle },
}

export default function PreviewPage() {
  const navigate = useNavigate()
  const { sessionId, mappings, setMappings, previewSummary, setPreviewSummary } = useWorkflow()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) { navigate('/upload'); return }
    if (mappings.length > 0 && previewSummary) return
    setLoading(true)
    api.mapVisuals(sessionId)
      .then((res) => setMappings(res.mappings))
      .then(() => api.preview(sessionId))
      .then((summary) => setPreviewSummary(summary))
      .catch((e) => setError(e instanceof Error ? e.message : 'Mapping failed'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const handleFieldEdit = async (visualId: string, field: string, value: string) => {
    if (!sessionId) return
    const res = await api.updateMapping(sessionId, visualId, { [field]: value } as Partial<FieldMapping>)
    setMappings(res.mappings)
    const summary = await api.preview(sessionId)
    setPreviewSummary(summary)
  }

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-3 text-slate-400 min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
        Mapping visuals to dataset columns…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <Card className="border-rose-500/30">
          <div className="flex items-center gap-2 text-rose-300 font-medium"><AlertTriangle className="w-4 h-4" /> Mapping failed</div>
          <p className="text-slate-400 text-sm mt-2">{error}</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Conversion preview</h1>
      <p className="text-slate-400 mt-1 text-sm">Step 3 — review AI-suggested mappings before generating your Power BI project.</p>

      {previewSummary && (
        <Card className="mt-6">
          <div className="flex flex-wrap gap-2">
            {Object.entries(previewSummary.counts).map(([k, v]) => (
              <Badge key={k} tone="success">✓ {v} {k}{v > 1 ? 's' : ''}</Badge>
            ))}
            {previewSummary.unsupported.length > 0 && (
              <Badge tone="danger">⚠ {previewSummary.unsupported.length} not directly mappable</Badge>
            )}
          </div>
          {previewSummary.unsupported.length > 0 && (
            <div className="mt-4 space-y-2">
              {previewSummary.unsupported.map((u, i) => (
                <div key={i} className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                  <span className="font-medium">{u.title}:</span> {u.reason} — suggested alternative: {u.suggested_alternative}
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      <Card className="mt-6 !p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-white/5 text-slate-400 text-xs">
              <th className="text-left px-4 py-3 font-medium">Visual</th>
              <th className="text-left px-4 py-3 font-medium">Power BI Type</th>
              <th className="text-left px-4 py-3 font-medium">Field(s)</th>
              <th className="text-left px-4 py-3 font-medium">Confidence</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => {
              const lvl = levelBadge[m.level]
              return (
                <tr key={m.visual_id} className="border-t border-white/5">
                  <td className="px-4 py-3 text-white">{m.title}</td>
                  <td className="px-4 py-3 text-slate-300">{m.power_bi_type}</td>
                  <td className="px-4 py-3 text-slate-400">
                    {m.level === 'ai_suggested' ? (
                      <input
                        defaultValue={m.field || m.category || m.x_axis || ''}
                        onBlur={(e) => handleFieldEdit(m.visual_id, m.field ? 'field' : m.category ? 'category' : 'x_axis', e.target.value)}
                        className="bg-white/5 border border-white/10 rounded-md px-2 py-1 text-xs text-white w-32"
                      />
                    ) : (
                      [m.field, m.category, m.x_axis, m.y_axis].filter(Boolean).join(', ') || '—'
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{m.confidence != null ? `${Math.round(m.confidence * 100)}%` : '—'}</td>
                  <td className="px-4 py-3">
                    <Badge tone={lvl.tone}><lvl.Icon className="w-3 h-3 inline mr-1" />{lvl.label}</Badge>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>

      <div className="mt-8 flex justify-end">
        <Button onClick={() => navigate('/conversion')}>
          Generate Power BI Project <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
