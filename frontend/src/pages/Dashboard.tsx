import { useNavigate } from 'react-router-dom'
import { useWorkflow } from '../state/WorkflowContext'
import { Card, Button, Badge } from '../components/ui'
import { Upload, ScanSearch, Eye, RefreshCw, ArrowRight } from 'lucide-react'

export default function Dashboard() {
  const navigate = useNavigate()
  const { sessionId, datasetFileName, dashboardFileName, mappings, conversionReport } = useWorkflow()

  const steps = [
    { label: 'Upload files', done: !!datasetFileName && !!dashboardFileName, icon: Upload, to: '/upload' },
    { label: 'Analyze', done: mappings.length > 0 || !!datasetFileName, icon: ScanSearch, to: '/analyze' },
    { label: 'Preview mappings', done: mappings.length > 0, icon: Eye, to: '/preview' },
    { label: 'Generate Power BI project', done: !!conversionReport, icon: RefreshCw, to: '/conversion' },
  ]

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Welcome back</h1>
      <p className="text-slate-400 mt-1 text-sm">
        {sessionId ? `Active session: ${sessionId.slice(0, 8)}…` : 'No active session yet — start a new conversion.'}
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-8">
        {steps.map((s) => (
          <Card key={s.label} className="flex items-center justify-between !p-5">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-brand-500/15 flex items-center justify-center">
                <s.icon className="w-4 h-4 text-brand-300" />
              </div>
              <div>
                <div className="text-white text-sm font-medium">{s.label}</div>
                <Badge tone={s.done ? 'success' : 'default'}>{s.done ? 'Complete' : 'Not started'}</Badge>
              </div>
            </div>
            <Button variant="ghost" onClick={() => navigate(s.to)}>
              <ArrowRight className="w-4 h-4" />
            </Button>
          </Card>
        ))}
      </div>

      <Card className="mt-8">
        <h2 className="text-white font-medium mb-2">How the pipeline works</h2>
        <ol className="text-sm text-slate-400 space-y-1.5 list-decimal list-inside">
          <li>Upload your Excel/CSV dataset and your HTML (or zipped) dashboard.</li>
          <li>The backend statically parses both — real pandas profiling + real HTML/JS AST parsing, no execution of your JavaScript.</li>
          <li>AI (or a deterministic fallback) matches each detected visual to dataset columns and drafts DAX measures.</li>
          <li>You review the Conversion Preview and confirm or correct low-confidence mappings.</li>
          <li>A real Power BI Project (PBIP: TMDL semantic model + report definition) is generated and zipped for download.</li>
        </ol>
      </Card>

      <div className="mt-8">
        <Button onClick={() => navigate('/upload')}>Start a new conversion</Button>
      </div>
    </div>
  )
}
