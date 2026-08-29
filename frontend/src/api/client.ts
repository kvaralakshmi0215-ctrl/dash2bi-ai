import type {
  DatasetAnalysis, DashboardAnalysis, FieldMapping, PreviewSummary, ConversionReport,
} from '../types'

const BASE = '/api'

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export async function uploadDataset(file: File, sessionId: string | null) {
  const form = new FormData()
  if (sessionId) form.append('session_id', sessionId)
  form.append('file', file)
  const res = await fetch(`${BASE}/upload/dataset`, { method: 'POST', body: form })
  return handleJson<{ session_id: string; file_id: string; filename: string }>(res)
}

export async function uploadDashboard(file: File, sessionId: string) {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('file', file)
  const res = await fetch(`${BASE}/upload/dashboard`, { method: 'POST', body: form })
  return handleJson<{ session_id: string; file_id: string; filename: string }>(res)
}

export async function analyze(sessionId: string) {
  const form = new FormData()
  form.append('session_id', sessionId)
  const res = await fetch(`${BASE}/analyze`, { method: 'POST', body: form })
  return handleJson<{
    session_id: string
    dataset_analysis: DatasetAnalysis
    dashboard_analysis: DashboardAnalysis
  }>(res)
}

export async function mapVisuals(sessionId: string) {
  const form = new FormData()
  form.append('session_id', sessionId)
  const res = await fetch(`${BASE}/map`, { method: 'POST', body: form })
  return handleJson<{ session_id: string; mappings: FieldMapping[] }>(res)
}

export async function updateMapping(sessionId: string, visualId: string, updates: Partial<FieldMapping>) {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('visual_id', visualId)
  form.append('field_updates', JSON.stringify(updates))
  const res = await fetch(`${BASE}/map/update`, { method: 'POST', body: form })
  return handleJson<{ session_id: string; mappings: FieldMapping[] }>(res)
}

export async function preview(sessionId: string) {
  const form = new FormData()
  form.append('session_id', sessionId)
  const res = await fetch(`${BASE}/preview`, { method: 'POST', body: form })
  return handleJson<PreviewSummary>(res)
}

export async function convert(sessionId: string, projectName: string) {
  const form = new FormData()
  form.append('session_id', sessionId)
  form.append('project_name', projectName)
  const res = await fetch(`${BASE}/convert`, { method: 'POST', body: form })
  return handleJson<ConversionReport>(res)
}

export function downloadUrl(conversionId: string) {
  return `${BASE}/download/${conversionId}`
}

export async function getHistory() {
  const res = await fetch(`${BASE}/history`)
  return handleJson<{ conversion_id: string; session_id: string; status: string; created_at: string }[]>(res)
}
