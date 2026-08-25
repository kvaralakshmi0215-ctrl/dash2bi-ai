from pydantic import BaseModel
from typing import Optional, Any


class ColumnProfile(BaseModel):
    name: str
    dtype: str  # "numeric" | "date" | "categorical" | "text" | "boolean"
    missing_count: int
    unique_count: int
    sample_values: list[Any] = []
    stats: Optional[dict[str, Any]] = None  # min/max/mean for numeric, etc.


class SheetProfile(BaseModel):
    sheet_name: str
    row_count: int
    columns: list[ColumnProfile]
    preview_rows: list[dict[str, Any]]


class DatasetAnalysis(BaseModel):
    file_name: str
    sheets: list[SheetProfile]
    suggested_relationships: list[dict[str, Any]] = []


class DetectedVisual(BaseModel):
    visual_id: str
    source: str  # "chartjs" | "html-table" | "css-grid-kpi" | "select" | "unknown"
    raw_title: Optional[str] = None
    candidate_type: str  # lineChart, barChart, columnChart, pieChart, donutChart, card, table, slicer, unsupported
    layout: dict[str, Any] = {}
    js_data_refs: list[str] = []


class DashboardAnalysis(BaseModel):
    file_name: str
    detected_visuals: list[DetectedVisual]
    theme: dict[str, Any] = {}
    layout_grid: list[list[str]] = []


class FieldMapping(BaseModel):
    visual_id: str
    title: str
    power_bi_type: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    field: Optional[str] = None
    category: Optional[str] = None
    values: Optional[list[str]] = None
    aggregation: Optional[str] = "SUM"
    confidence: float = 1.0
    level: str = "automatic"  # automatic | ai_suggested | unsupported
    warning: Optional[str] = None
    suggested_alternative: Optional[str] = None
    dax_measure: Optional[dict[str, str]] = None  # {"name": ..., "expression": ...}


class MappingResponse(BaseModel):
    session_id: str
    mappings: list[FieldMapping]


class PreviewSummary(BaseModel):
    session_id: str
    counts: dict[str, int]
    warnings: list[str]
    unsupported: list[dict[str, str]]
    ready: bool


class ConversionStep(BaseModel):
    name: str
    status: str  # "pending" | "running" | "done" | "failed"


class ConversionReport(BaseModel):
    session_id: str
    status: str
    visuals_converted: int
    data_mappings_created: int
    dax_measures_generated: int
    slicers_created: int
    warnings: list[str]
    errors: list[str]
    output_path: Optional[str] = None
