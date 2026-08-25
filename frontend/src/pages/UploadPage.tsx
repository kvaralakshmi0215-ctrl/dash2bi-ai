import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSpreadsheet, FileCode2, CheckCircle2, Loader2, ArrowRight } from 'lucide-react'
import { Card, Button, Badge } from '../components/ui'
import { useWorkflow } from '../state/WorkflowContext'
import * as api from '../api/client'

function Dropzone({
  accept, icon: Icon, title, hint, fileName, uploading, onFile,
}: {
  accept: string
  icon: typeof FileSpreadsheet
  title: string
  hint: string
  fileName: string | null
  uploading: boolean
  onFile: (f: File) => void
}) {
  const [dragOver, setDragOver] = useState(false)

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) onFile(f)
  }, [onFile])

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-2xl px-6 py-12 cursor-pointer transition-colors ${
        dragOver ? 'border-brand-400 bg-brand-500/5' : 'border-white/15 hover:border-white/30'
      }`}
    >
      <input type="file" accept={accept} className="hidden" onChange={(e) => {
        const f = e.target.files?.[0]
        if (f) onFile(f)
      }} />
      {uploading ? (
        <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
      ) : fileName ? (
        <CheckCircle2 className="w-8 h-8 text-emerald-400" />
      ) : (
        <Icon className="w-8 h-8 text-slate-500" />
      )}
      <div className="text-center">
        <div className="text-white text-sm font-medium">{fileName || title}</div>
        <div className="text-slate-500 text-xs mt-1">{fileName ? 'Click or drop to replace' : hint}</div>
      </div>
    </label>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const {
    sessionId, setSessionId, datasetFileName, setDatasetFileName,
    dashboardFileName, setDashboardFileName,
  } = useWorkflow()
  const [uploadingDataset, setUploadingDataset] = useState(false)
  const [uploadingDashboard, setUploadingDashboard] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleDatasetFile = async (file: File) => {
    setError(null)
    setUploadingDataset(true)
    try {
      const res = await api.uploadDataset(file, sessionId)
      setSessionId(res.session_id)
      setDatasetFileName(res.filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingDataset(false)
    }
  }

  const handleDashboardFile = async (file: File) => {
    if (!sessionId) {
      setError('Upload the Excel dataset first.')
      return
    }
    setError(null)
    setUploadingDashboard(true)
    try {
      const res = await api.uploadDashboard(file, sessionId)
      setDashboardFileName(res.filename)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploadingDashboard(false)
    }
  }

  const canContinue = !!datasetFileName && !!dashboardFileName

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Upload your files</h1>
      <p className="text-slate-400 mt-1 text-sm">Step 1 of the conversion pipeline.</p>

      {error && (
        <div className="mt-4 px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-6">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-medium text-sm">Excel Dataset</h2>
            <Badge>.xlsx · .xls · .csv</Badge>
          </div>
          <Dropzone
            accept=".xlsx,.xls,.csv"
            icon={FileSpreadsheet}
            title="Drop dataset here"
            hint="or click to browse"
            fileName={datasetFileName}
            uploading={uploadingDataset}
            onFile={handleDatasetFile}
          />
        </Card>

        <Card>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-white font-medium text-sm">HTML Dashboard</h2>
            <Badge>.html · .zip</Badge>
          </div>
          <Dropzone
            accept=".html,.htm,.zip"
            icon={FileCode2}
            title="Drop dashboard here"
            hint="or click to browse"
            fileName={dashboardFileName}
            uploading={uploadingDashboard}
            onFile={handleDashboardFile}
          />
        </Card>
      </div>

      <div className="mt-8 flex justify-end">
        <Button disabled={!canContinue} onClick={() => navigate('/analyze')}>
          Continue to Analysis <ArrowRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  )
}
