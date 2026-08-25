"""
Real dataset analysis using pandas — no mocked statistics.
Reads .xlsx / .xls / .csv, profiles every sheet/column, and proposes
relationships between sheets based on shared column names + key-like patterns.
"""
import pandas as pd
import numpy as np
from pathlib import Path


def _infer_dtype(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    # try to coerce object columns to datetime — real check, not a guess
    if series.dtype == object:
        non_null = series.dropna()
        if len(non_null) > 0:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                parsed = pd.to_datetime(non_null, errors="coerce")
            if parsed.notna().mean() > 0.85:
                return "date"
        # categorical vs free text: low cardinality relative to row count => categorical
        nunique = series.nunique(dropna=True)
        n = max(len(series), 1)
        if nunique <= max(20, int(n * 0.2)):
            return "categorical"
        return "text"
    return "text"


def _json_safe(v):
    if isinstance(v, (pd.Timestamp,)) or hasattr(v, "isoformat"):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    if hasattr(v, "item"):
        return v.item()
    return v


def _profile_column(series: pd.Series) -> dict:
    dtype = _infer_dtype(series)
    profile = {
        "name": series.name,
        "dtype": dtype,
        "missing_count": int(series.isna().sum()),
        "unique_count": int(series.nunique(dropna=True)),
        "sample_values": [_json_safe(v) for v in series.dropna().unique()[:5].tolist()],
        "stats": None,
    }
    if dtype == "numeric":
        numeric = pd.to_numeric(series, errors="coerce")
        profile["stats"] = {
            "min": float(np.nanmin(numeric)) if numeric.notna().any() else None,
            "max": float(np.nanmax(numeric)) if numeric.notna().any() else None,
            "mean": float(np.nanmean(numeric)) if numeric.notna().any() else None,
            "sum": float(np.nansum(numeric)) if numeric.notna().any() else None,
        }
    elif dtype == "date":
        parsed = pd.to_datetime(series, errors="coerce")
        profile["stats"] = {
            "min": str(parsed.min()) if parsed.notna().any() else None,
            "max": str(parsed.max()) if parsed.notna().any() else None,
        }
    return profile


def analyze_dataset(file_path: str) -> dict:
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".csv":
        sheets = {"Sheet1": pd.read_csv(file_path)}
    elif ext in (".xlsx", ".xls"):
        raw = pd.read_excel(file_path, sheet_name=None, engine="openpyxl" if ext == ".xlsx" else None)
        sheets = raw
    else:
        raise ValueError(f"Unsupported dataset file type: {ext}")

    sheet_profiles = []
    all_columns_by_sheet = {}

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all")  # drop fully-empty rows
        columns = [_profile_column(df[col]) for col in df.columns]
        all_columns_by_sheet[sheet_name] = [c["name"] for c in columns]

        preview = df.head(10).replace({np.nan: None}).to_dict(orient="records")
        # make preview JSON-safe (numpy scalars -> python)
        clean_preview = []
        for row in preview:
            clean_row = {k: _json_safe(v) for k, v in row.items()}
            clean_preview.append(clean_row)

        sheet_profiles.append({
            "sheet_name": sheet_name,
            "row_count": int(len(df)),
            "columns": columns,
            "preview_rows": clean_preview,
        })

    # Suggest relationships between sheets: shared column name, likely a *ID pattern
    relationships = []
    sheet_names = list(all_columns_by_sheet.keys())
    for i in range(len(sheet_names)):
        for j in range(i + 1, len(sheet_names)):
            s1, s2 = sheet_names[i], sheet_names[j]
            shared = set(all_columns_by_sheet[s1]) & set(all_columns_by_sheet[s2])
            for col in shared:
                confidence = 0.6
                if col.lower().endswith("id") or col.lower().endswith("key"):
                    confidence = 0.9
                relationships.append({
                    "from_table": s1,
                    "to_table": s2,
                    "on_column": col,
                    "confidence": confidence,
                })

    return {
        "file_name": path.name,
        "sheets": sheet_profiles,
        "suggested_relationships": relationships,
    }
