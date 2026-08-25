import json
import shutil
from pathlib import Path
from app.services import pbip_generator
from app.core.config import settings


def build_preview_summary(mappings: list[dict]) -> dict:
    counts = {"kpi": 0, "lineChart": 0, "barChart": 0, "columnChart": 0,
              "pieChart": 0, "donutChart": 0, "table": 0, "slicer": 0}
    warnings = []
    unsupported = []

    type_key_map = {
        "Power BI Card": "kpi",
        "Power BI Line Chart": "lineChart",
        "Power BI Bar Chart": "barChart",
        "Power BI Column Chart": "columnChart",
        "Power BI Pie Chart": "pieChart",
        "Power BI Donut Chart": "donutChart",
        "Power BI Table": "table",
        "Power BI Slicer": "slicer",
    }

    for m in mappings:
        if m["level"] == "unsupported":
            unsupported.append({
                "title": m["title"],
                "reason": m.get("warning", "Could not be mapped."),
                "suggested_alternative": m.get("suggested_alternative", "Table"),
            })
            continue
        key = type_key_map.get(m["power_bi_type"])
        if key:
            counts[key] += 1
        if m["level"] == "ai_suggested":
            warnings.append(f"\"{m['title']}\": {m.get('warning', 'Needs confirmation.')}")

    ready = True  # MVP: always allow generating even with unsupported items (they're just excluded)
    return {
        "counts": {k: v for k, v in counts.items() if v > 0},
        "warnings": warnings,
        "unsupported": unsupported,
        "ready": ready,
    }


def run_conversion(session_id: str, project_name: str, dataset_analysis: dict, mappings: list[dict]) -> dict:
    """Real conversion: no fake progress, this actually builds the PBIP project on disk,
    then zips it for download. Returns a conversion report dict."""
    try:
        gen_result = pbip_generator.generate_pbip_project(
            project_name=project_name,
            dataset_analysis=dataset_analysis,
            mappings=mappings,
            output_dir=settings.OUTPUT_DIR,
        )
    except Exception as e:
        return {
            "status": "failed",
            "visuals_converted": 0,
            "data_mappings_created": 0,
            "dax_measures_generated": 0,
            "slicers_created": 0,
            "warnings": [],
            "errors": [f"Power BI project generation failed: {e}"],
            "output_path": None,
        }

    supported = [m for m in mappings if m.get("level") != "unsupported"]
    unsupported = [m for m in mappings if m.get("level") == "unsupported"]
    dax_count = sum(1 for m in supported if m.get("dax_measure") and m["dax_measure"].get("validated"))
    slicer_count = sum(1 for m in supported if m.get("power_bi_type") == "Power BI Slicer")

    warnings = [
        f"\"{m['title']}\" required manual adjustment: {m.get('warning', 'low confidence mapping')}"
        for m in supported if m.get("level") == "ai_suggested"
    ] + [
        f"\"{m['title']}\" was not converted: {m.get('warning', 'unsupported visual')}. "
        f"Suggested alternative: {m.get('suggested_alternative', 'Table')}"
        for m in unsupported
    ]

    # zip the project folder for a single downloadable artifact
    root_path = Path(gen_result["root"])
    zip_base = str(root_path)  # shutil appends .zip
    shutil.make_archive(zip_base, "zip", root_dir=root_path.parent, base_dir=root_path.name)
    zip_path = f"{zip_base}.zip"

    return {
        "status": "completed",
        "visuals_converted": len(supported),
        "data_mappings_created": len(supported),
        "dax_measures_generated": dax_count,
        "slicers_created": slicer_count,
        "warnings": warnings,
        "errors": [],
        "output_path": zip_path,
    }
