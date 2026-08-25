import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, ArrowRight, AlertTriangle } from 'lucide-react'
import { Card, Button, Badge } from '../components/ui'
import { useWorkflow } from '../state/WorkflowContext'
import * as api from '../api/client'

const dtypeTone: Record<string, 'default' | 'success' | 'warn'> = {
  numeric: 'success',
  date: 'default',
  categorical: 'warn',
  text: 'default',
  boolean: 'default',
}

export default function AnalyzePage() {
  const navigate = useNavigate()
  const {
    sessionId, datasetAnalysis, setDatasetAnalysis, dashboardAnalysis, setDashboardAnalysis,
  } = useWorkflow()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) {
      navigate('/upload')
      return
    }
    if (datasetAnalysis && dashboardAnalysis) return
    setLoading(true)
    api.analyze(sessionId)
      .then((res) => {
        setDatasetAnalysis(res.dataset_analysis)
        setDashboardAnalysis(res.dashboard_analysis)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Analysis failed'))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  if (loading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center gap-3 text-slate-400 min-h-[60vh]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
        Analyzing dataset and dashboard…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <Card className="border-rose-500/30">
          <div className="flex items-center gap-2 text-rose-300 font-medium">
            <AlertTriangle className="w-4 h-4" /> Analysis failed
          </div>
          <p className="text-slate-400 text-sm mt-2">{error}</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Analysis results</h1>
      <p className="text-slate-400 mt-1 text-sm">Step 2 — dataset profile and detected dashboard visuals.</p>

      {datasetAnalysis && (
        <Card className="mt-6">
          <h2 className="text-white font-medium mb-4">Dataset: {datasetAnalysis.file_name}</h2>
          {datasetAnalysis.sheets.map((sheet) => (
            <div key={sheet.sheet_name} className="mb-6 last:mb-0">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-white text-sm font-medium">{sheet.sheet_name}</span>
                <Badge>{sheet.row_count} rows</Badge>
                <Badge>{sheet.columns.length} columns</Badge>
              </div>
              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-white/5 text-slate-400">
                      {sheet.columns.map((c) => (
                        <th key={c.name} className="text-left px-3 py-2 font-medium whitespace-nowrap">
                          {c.name} <Badge tone={dtypeTone[c.dtype]}>{c.dtype}</Badge>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sheet.preview_rows.slice(0, 5).map((row, i) => (
                      <tr key={i} className="border-t border-white/5 text-slate-300">
                        {sheet.columns.map((c) => (
                          <td key={c.name} className="px-3 py-2 whitespace-nowrap">{String(row[c.name] ?? '')}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </Card>
      )}

      {dashboardAnalysis && (
        <Card className="mt-6">
          <h2 className="text-white font-medium mb-4">Dashboard: {dashboardAnalysis.file_name}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {dashboardAnalysis.detected_visuals.map((v) => (
              <div key={v.visual_id} className="rounded-xl border border-white/10 p-4">
                <div className="text-white text-sm font-medium truncate">{v.raw_title || v.visual_id}</div>
                <div className="mt-2 flex gap-2 flex-wrap">
                  <Badge>{v.candidate_type}</Badge>
                  <Badge tone={v.source === 'unknown' ? 'warn' : 'default'}>{v.source}</Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="mt-8 flex justify-end">
        <Button onClick={() => navigate('/preview')}>
          Continue to Mapping &amp; Preview <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
