import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Download, AlertTriangle, RefreshCw } from 'lucide-react'
import { Card, Button, Badge, ProgressStep } from '../components/ui'
import { useWorkflow } from '../state/WorkflowContext'
import * as api from '../api/client'

const STEP_LABELS = [
  'Reading Excel',
  'Analyzing HTML',
  'Detecting visuals',
  'Mapping dataset',
  'Generating DAX',
  'Building Power BI project',
  'Validation',
]

export default function ConversionPage() {
  const navigate = useNavigate()
  const { sessionId, conversionReport, setConversionReport } = useWorkflow()
  const [projectName, setProjectName] = useState('Dash2BI_Project')
  const [running, setRunning] = useState(false)
  const [stepIndex, setStepIndex] = useState(-1)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!sessionId) navigate('/upload')
  }, [sessionId, navigate])

  const runConversion = async () => {
    if (!sessionId) return
    setRunning(true)
    setError(null)
    setConversionReport(null)

    // Steps 1-5 already happened during analyze/map — reflect that instantly,
    // then make the real backend call for steps 6-7 (actual PBIP generation).
    for (let i = 0; i < 5; i++) {
      setStepIndex(i)
      await new Promise((r) => setTimeout(r, 120))
    }
    setStepIndex(5)

    try {
      const report = await api.convert(sessionId, projectName)
      setStepIndex(6)
      await new Promise((r) => setTimeout(r, 150))
      setStepIndex(7)
      setConversionReport(report)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Conversion failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Generate Power BI project</h1>
      <p className="text-slate-400 mt-1 text-sm">Step 4 — the final, real PBIP project build.</p>

      <Card className="mt-6">
        <label className="text-xs text-slate-400">Project name</label>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          disabled={running}
          className="mt-1 w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
        />
        <Button className="mt-4 w-full" onClick={runConversion} disabled={running}>
          <RefreshCw className={`w-4 h-4 ${running ? 'animate-spin' : ''}`} />
          {running ? 'Converting…' : 'Generate Power BI Project'}
        </Button>
      </Card>

      {stepIndex >= 0 && (
        <Card className="mt-6">
          {STEP_LABELS.map((label, i) => (
            <ProgressStep
              key={label}
              label={label}
              status={i < stepIndex ? 'done' : i === stepIndex ? 'running' : 'pending'}
            />
          ))}
        </Card>
      )}

      {error && (
        <Card className="mt-6 border-rose-500/30">
          <div className="flex items-center gap-2 text-rose-300 font-medium"><AlertTriangle className="w-4 h-4" /> Conversion could not complete</div>
          <p className="text-slate-400 text-sm mt-2">{error}</p>
        </Card>
      )}

      {conversionReport && (
        <Card className="mt-6">
          <h2 className="text-white font-medium mb-3">Conversion completed</h2>
          <div className="flex flex-wrap gap-2 mb-4">
            <Badge tone="success">✓ {conversionReport.visuals_converted} visuals converted</Badge>
            <Badge tone="success">✓ {conversionReport.data_mappings_created} data mappings</Badge>
            <Badge tone="success">✓ {conversionReport.dax_measures_generated} DAX measures</Badge>
            <Badge tone="success">✓ {conversionReport.slicers_created} slicers</Badge>
          </div>
          {conversionReport.warnings.length > 0 && (
            <div className="space-y-1.5 mb-4">
              {conversionReport.warnings.map((w, i) => (
                <div key={i} className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">⚠ {w}</div>
              ))}
            </div>
          )}
          <Button onClick={() => window.open(api.downloadUrl(conversionReport.conversion_id), '_blank')}>
            <Download className="w-4 h-4" /> Download Power BI Project (.zip)
          </Button>
          <p className="text-slate-500 text-xs mt-3">
            Unzip and open the .pbip file in Power BI Desktop (File → Open → Power BI Project).
          </p>
        </Card>
      )}
    </div>
  )
}
