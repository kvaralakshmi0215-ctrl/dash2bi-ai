"""
Reusable, extensible HTML-visual -> Power BI-visual mapping engine.

To add a new supported visual type later: add an entry to VISUAL_TYPE_MAP
and (if it needs special field logic) a branch in `_map_fields_for`.
"""
from app.services import ai_service

# --- Static HTML -> Power BI visual type table (Level 1 when candidate_type already known) ---
VISUAL_TYPE_MAP = {
    "lineChart": "Power BI Line Chart",
    "barChart": "Power BI Bar Chart",
    "columnChart": "Power BI Column Chart",
    "pieChart": "Power BI Pie Chart",
    "donutChart": "Power BI Donut Chart",
    "card": "Power BI Card",
    "table": "Power BI Table",
    "slicer": "Power BI Slicer",
}

CONFIDENCE_AUTO_THRESHOLD = 0.85
CONFIDENCE_MIN_THRESHOLD = 0.35


def _flatten_columns(dataset_analysis: dict) -> list[dict]:
    cols = []
    for sheet in dataset_analysis["sheets"]:
        for c in sheet["columns"]:
            entry = dict(c)
            entry["table"] = sheet["sheet_name"]
            cols.append(entry)
    return cols


def build_mappings(dataset_analysis: dict, dashboard_analysis: dict) -> list[dict]:
    columns = _flatten_columns(dataset_analysis)
    primary_table = dataset_analysis["sheets"][0]["sheet_name"] if dataset_analysis["sheets"] else "Sheet1"
    mappings = []

    for visual in dashboard_analysis["detected_visuals"]:
        candidate_type = visual["candidate_type"]
        title = visual.get("raw_title") or visual["visual_id"]

        # Level 3: unsupported visual type
        if candidate_type == "unsupported" or candidate_type not in VISUAL_TYPE_MAP:
            mappings.append({
                "visual_id": visual["visual_id"],
                "title": title,
                "power_bi_type": "unsupported",
                "aggregation": None,
                "confidence": 0.0,
                "level": "unsupported",
                "warning": "This visual could not be statically identified as a supported chart type.",
                "suggested_alternative": "Line Chart" if "trend" in title.lower() else "Table",
            })
            continue

        if candidate_type == "table":
            mappings.append({
                "visual_id": visual["visual_id"],
                "title": title,
                "power_bi_type": "Power BI Table",
                "values": visual.get("js_data_refs", []) or None,
                "aggregation": None,
                "confidence": 1.0,
                "level": "automatic",
            })
            continue

        if candidate_type == "slicer":
            # try to match the filter's field name against a categorical column
            field, score = _best_match_categorical(title, visual.get("js_data_refs", []), columns)
            level = "automatic" if score >= CONFIDENCE_AUTO_THRESHOLD else "ai_suggested"
            mappings.append({
                "visual_id": visual["visual_id"],
                "title": title,
                "power_bi_type": "Power BI Slicer",
                "field": field,
                "aggregation": None,
                "confidence": round(score, 2),
                "level": level if field else "unsupported",
                "warning": None if field else "Could not match this filter to a dataset column.",
            })
            continue

        # Chart / Card types: use AI service (or fallback heuristic) for field matching
        match = ai_service.match_visual_to_columns(
            visual_title=title,
            visual_type=candidate_type,
            data_refs=visual.get("js_data_refs", []),
            available_columns=[{"name": c["name"], "dtype": c["dtype"]} for c in columns],
        )
        confidence = float(match.get("confidence", 0))

        entry = {
            "visual_id": visual["visual_id"],
            "title": title,
            "power_bi_type": VISUAL_TYPE_MAP[candidate_type],
            "x_axis": match.get("x_axis"),
            "y_axis": match.get("y_axis"),
            "field": match.get("field"),
            "category": match.get("category"),
            "aggregation": match.get("aggregation", "SUM"),
            "confidence": round(confidence, 2),
        }

        if confidence < CONFIDENCE_MIN_THRESHOLD or (candidate_type == "card" and not entry["field"]) \
                or (candidate_type == "lineChart" and not (entry["y_axis"] and entry["x_axis"])) \
                or (candidate_type in ("barChart", "columnChart", "pieChart", "donutChart")
                    and not (entry["field"] and entry["category"])):
            entry["level"] = "unsupported"
            entry["warning"] = "AI could not confidently match this visual to any dataset column."
            entry["suggested_alternative"] = "Manually select fields, or use a Table visual."
        elif confidence < CONFIDENCE_AUTO_THRESHOLD:
            entry["level"] = "ai_suggested"
            entry["warning"] = f"AI confidence {int(confidence * 100)}% — please confirm the suggested field(s)."
        else:
            entry["level"] = "automatic"

        # DAX generation for anything with a numeric field + aggregation, if mapping succeeded
        if entry.get("field") and entry.get("aggregation") and entry.get("level") != "unsupported":
            measure_name = _measure_name_from_title(title)
            dax = ai_service.generate_dax_measure(
                measure_name=measure_name,
                table=primary_table,
                field=entry["field"],
                aggregation=entry["aggregation"],
            )
            entry["dax_measure"] = dax

        mappings.append(entry)

    return mappings


def _measure_name_from_title(title: str) -> str:
    cleaned = title.strip()
    return cleaned if cleaned else "Measure"


def _best_match_categorical(title: str, options: list[str], columns: list[dict]) -> tuple[str | None, float]:
    import difflib
    categorical = [c["name"] for c in columns if c["dtype"] in ("categorical", "text")]
    if not categorical:
        return None, 0.0
    pool = " ".join([title] + options).lower()
    best, score = None, 0.0
    for col in categorical:
        r = difflib.SequenceMatcher(None, pool, col.lower()).ratio()
        if r > score:
            best, score = col, r
    return best, score
