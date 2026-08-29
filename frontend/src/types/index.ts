export interface ColumnProfile {
  name: string
  dtype: 'numeric' | 'date' | 'categorical' | 'text' | 'boolean'
  missing_count: number
  unique_count: number
  sample_values: unknown[]
  stats?: Record<string, unknown> | null
}

export interface SheetProfile {
  sheet_name: string
  row_count: number
  columns: ColumnProfile[]
  preview_rows: Record<string, unknown>[]
}

export interface DatasetAnalysis {
  file_name: string
  sheets: SheetProfile[]
  suggested_relationships: Record<string, unknown>[]
}

export interface DetectedVisual {
  visual_id: string
  source: string
  raw_title: string | null
  candidate_type: string
  layout: Record<string, unknown>
  js_data_refs: string[]
}

export interface DashboardAnalysis {
  file_name: string
  detected_visuals: DetectedVisual[]
  theme: { palette?: string[]; font_family?: string | null }
  layout_grid: string[][]
}

export interface DaxMeasure {
  name: string
  expression: string
  validated: boolean
  notes: string
}

export interface FieldMapping {
  visual_id: string
  title: string
  power_bi_type: string
  x_axis?: string | null
  y_axis?: string | null
  field?: string | null
  category?: string | null
  values?: string[] | null
  aggregation?: string | null
  confidence: number
  level: 'automatic' | 'ai_suggested' | 'unsupported'
  warning?: string | null
  suggested_alternative?: string | null
  dax_measure?: DaxMeasure | null
}

export interface PreviewSummary {
  session_id: string
  counts: Record<string, number>
  warnings: string[]
  unsupported: { title: string; reason: string; suggested_alternative: string }[]
  ready: boolean
}

export interface ConversionReport {
  conversion_id: string
  session_id: string
  status: string
  visuals_converted: number
  data_mappings_created: number
  dax_measures_generated: number
  slicers_created: number
  warnings: string[]
  errors: string[]
  output_path?: string | null
}
