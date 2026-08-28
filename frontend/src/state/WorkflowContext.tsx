import React, { createContext, useContext, useState } from 'react'
import type { DatasetAnalysis, DashboardAnalysis, FieldMapping, PreviewSummary, ConversionReport } from '../types'

interface WorkflowState {
  sessionId: string | null
  setSessionId: (id: string | null) => void
  datasetFileName: string | null
  setDatasetFileName: (n: string | null) => void
  dashboardFileName: string | null
  setDashboardFileName: (n: string | null) => void
  datasetAnalysis: DatasetAnalysis | null
  setDatasetAnalysis: (d: DatasetAnalysis | null) => void
  dashboardAnalysis: DashboardAnalysis | null
  setDashboardAnalysis: (d: DashboardAnalysis | null) => void
  mappings: FieldMapping[]
  setMappings: (m: FieldMapping[]) => void
  previewSummary: PreviewSummary | null
  setPreviewSummary: (p: PreviewSummary | null) => void
  conversionReport: ConversionReport | null
  setConversionReport: (c: ConversionReport | null) => void
  reset: () => void
}

const WorkflowContext = createContext<WorkflowState | null>(null)

export function WorkflowProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [datasetFileName, setDatasetFileName] = useState<string | null>(null)
  const [dashboardFileName, setDashboardFileName] = useState<string | null>(null)
  const [datasetAnalysis, setDatasetAnalysis] = useState<DatasetAnalysis | null>(null)
  const [dashboardAnalysis, setDashboardAnalysis] = useState<DashboardAnalysis | null>(null)
  const [mappings, setMappings] = useState<FieldMapping[]>([])
  const [previewSummary, setPreviewSummary] = useState<PreviewSummary | null>(null)
  const [conversionReport, setConversionReport] = useState<ConversionReport | null>(null)

  const reset = () => {
    setSessionId(null)
    setDatasetFileName(null)
    setDashboardFileName(null)
    setDatasetAnalysis(null)
    setDashboardAnalysis(null)
    setMappings([])
    setPreviewSummary(null)
    setConversionReport(null)
  }

  return (
    <WorkflowContext.Provider value={{
      sessionId, setSessionId,
      datasetFileName, setDatasetFileName,
      dashboardFileName, setDashboardFileName,
      datasetAnalysis, setDatasetAnalysis,
      dashboardAnalysis, setDashboardAnalysis,
      mappings, setMappings,
      previewSummary, setPreviewSummary,
      conversionReport, setConversionReport,
      reset,
    }}>
      {children}
    </WorkflowContext.Provider>
  )
}

export function useWorkflow() {
  const ctx = useContext(WorkflowContext)
  if (!ctx) throw new Error('useWorkflow must be used within WorkflowProvider')
  return ctx
}
