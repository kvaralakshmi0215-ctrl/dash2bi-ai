import { useNavigate } from 'react-router-dom'
import { ArrowRight, Sparkles, LayoutGrid, Table, BarChart3, Gauge } from 'lucide-react'
import { Button, Card } from '../components/ui'

export default function Landing() {
  const navigate = useNavigate()
  return (
    <div className="min-h-full flex flex-col items-center px-6 py-20 text-center">
      <div className="flex items-center gap-2 mb-6 px-3 py-1 rounded-full border border-white/10 bg-white/5 text-xs text-slate-300">
        <Sparkles className="w-3.5 h-3.5 text-brand-400" />
        AI-assisted dashboard conversion
      </div>
      <h1 className="text-4xl md:text-5xl font-semibold text-white max-w-3xl leading-tight tracking-tight">
        Turn AI-Generated Dashboards into Power BI Projects
      </h1>
      <p className="mt-5 max-w-xl text-slate-400 text-base">
        Upload your Excel dataset and HTML dashboard. Let AI analyze, map, and reconstruct
        your dashboard for Power BI — without rebuilding everything manually.
      </p>
      <div className="mt-8 flex gap-3">
        <Button onClick={() => navigate('/upload')}>
          Start Converting <ArrowRight className="w-4 h-4" />
        </Button>
        <Button variant="secondary" onClick={() => navigate('/dashboard')}>
          View Demo
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-20 max-w-4xl w-full text-left">
        <Card className="!p-5">
          <Gauge className="w-5 h-5 text-brand-400 mb-3" />
          <h3 className="text-white font-medium text-sm">KPI &amp; Card detection</h3>
          <p className="text-slate-500 text-xs mt-1">Auto-maps HTML metric cards to Power BI Card visuals.</p>
        </Card>
        <Card className="!p-5">
          <BarChart3 className="w-5 h-5 text-brand-400 mb-3" />
          <h3 className="text-white font-medium text-sm">Chart mapping</h3>
          <p className="text-slate-500 text-xs mt-1">Line, bar, column, pie &amp; donut charts mapped from Chart.js configs.</p>
        </Card>
        <Card className="!p-5">
          <Table className="w-5 h-5 text-brand-400 mb-3" />
          <h3 className="text-white font-medium text-sm">Tables &amp; slicers</h3>
          <p className="text-slate-500 text-xs mt-1">HTML tables and dropdown filters become Power BI tables and slicers.</p>
        </Card>
        <Card className="!p-5">
          <LayoutGrid className="w-5 h-5 text-brand-400 mb-3" />
          <h3 className="text-white font-medium text-sm">Real PBIP output</h3>
          <p className="text-slate-500 text-xs mt-1">Generates a genuine Power BI Project (TMDL + report definition) — never a renamed HTML file.</p>
        </Card>
      </div>
    </div>
  )
}
