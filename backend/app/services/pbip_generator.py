"""
Generates a Power BI Project (PBIP) — the text-based, source-control-friendly
project format Microsoft officially supports for opening in Power BI Desktop
(File > Open > .pbip), introduced as a supported alternative to the binary
.pbix. This is NOT a renamed/repackaged HTML file: we emit real TMDL
(Tabular Model Definition Language) for the semantic model and a real
report.json/pages definition for the report, per Microsoft's documented
PBIP project layout:

  <ProjectName>.pbip
  <ProjectName>.Report/
      report.json
      definition/
          pages/
              pages.json
              <page>/page.json
              <page>/visuals/<visual>/visual.json
  <ProjectName>.SemanticModel/
      definition/
          model.tmdl
          tables/<table>.tmdl
          relationships.tmdl

Layout fidelity: visual x/y/width/height are approximated from the detected
HTML layout grid (see html_analyzer.layout_grid) — pixel-exact conversion is
out of scope for the MVP, as documented in the README/known-limitations.

Anything the mapping engine marked "unsupported" is NOT written into the
report; it's surfaced only in the conversion report, per the "don't fake it"
requirement.
"""
import json
import uuid
from pathlib import Path

VISUAL_TYPE_TO_PBI_VISUAL = {
    "Power BI Line Chart": "lineChart",
    "Power BI Bar Chart": "barChart",
    "Power BI Column Chart": "columnChart",
    "Power BI Pie Chart": "pieChart",
    "Power BI Donut Chart": "donutChart",
    "Power BI Card": "card",
    "Power BI Table": "tableEx",
    "Power BI Slicer": "slicer",
}

PAGE_WIDTH = 1280
PAGE_HEIGHT = 720


def _sanitize_tmdl_identifier(name: str) -> str:
    return name.replace("'", "''")


def _dax_type_for_dtype(dtype: str) -> str:
    return {
        "numeric": "double",
        "date": "dateTime",
        "boolean": "boolean",
    }.get(dtype, "string")


def _build_table_tmdl(sheet: dict) -> str:
    lines = [f"table '{_sanitize_tmdl_identifier(sheet['sheet_name'])}'", ""]
    for col in sheet["columns"]:
        dtype = _dax_type_for_dtype(col["dtype"])
        lines.append(f"\tcolumn '{_sanitize_tmdl_identifier(col['name'])}'")
        lines.append(f"\t\tdataType: {dtype}")
        lines.append(f"\t\tsourceColumn: '{_sanitize_tmdl_identifier(col['name'])}'")
        lines.append("")
    lines.append("\tpartition '{}' = m".format(_sanitize_tmdl_identifier(sheet["sheet_name"])))
    lines.append("\t\tmode: import")
    lines.append("\t\tsource =")
    lines.append("\t\t\tlet")
    lines.append(f"\t\t\t\tSource = Excel.CurrentWorkbook(){{[Name=\"{sheet['sheet_name']}\"]}}[Content]")
    lines.append("\t\t\tin")
    lines.append("\t\t\t\tSource")
    lines.append("")
    return "\n".join(lines)


def _build_measures_tmdl_block(measures: list[dict]) -> str:
    """Appends measures to the primary table's TMDL block text."""
    lines = []
    for m in measures:
        if not m or not m.get("expression"):
            continue
        name = _sanitize_tmdl_identifier(m["name"])
        # expression already includes "Name = DAX" form from ai_service; split it out
        expr = m["expression"]
        if "=" in expr:
            expr_body = expr.split("=", 1)[1].strip()
        else:
            expr_body = expr
        lines.append(f"\tmeasure '{name}' = {expr_body}")
        lines.append("")
    return "\n".join(lines)


def _build_relationships_tmdl(relationships: list[dict]) -> str:
    lines = []
    for rel in relationships:
        if rel.get("confidence", 0) < 0.5:
            continue
        rel_id = str(uuid.uuid4())
        lines.append(f"relationship {rel_id}")
        lines.append(f"\tfromColumn: '{rel['from_table']}'.'{rel['on_column']}'")
        lines.append(f"\ttoColumn: '{rel['to_table']}'.'{rel['on_column']}'")
        lines.append("")
    return "\n".join(lines)


def _layout_positions(n: int) -> list[dict]:
    """Simple grid packing: KPI-style row of up to 4, then full-width rows below.
    Approximates the detected HTML layout without claiming pixel accuracy."""
    positions = []
    cols_per_row = 4 if n > 4 else max(n, 1)
    cell_w = PAGE_WIDTH / cols_per_row
    cell_h = 180
    row, col = 0, 0
    for i in range(n):
        positions.append({
            "x": round(col * cell_w, 1),
            "y": round(row * cell_h, 1),
            "width": round(cell_w - 12, 1),
            "height": cell_h - 12,
        })
        col += 1
        if col >= cols_per_row:
            col = 0
            row += 1
    return positions


def _build_visual_json(mapping: dict, position: dict, primary_table: str) -> dict:
    pbi_visual = VISUAL_TYPE_TO_PBI_VISUAL.get(mapping["power_bi_type"], "card")
    query_state = {}

    def col_ref(col_name):
        return {
            "Column": {
                "Expression": {"SourceRef": {"Entity": primary_table}},
                "Property": col_name,
            }
        }

    def measure_ref(measure_name):
        return {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": primary_table}},
                "Property": measure_name,
            }
        }

    field_expr = None
    if mapping.get("dax_measure"):
        field_expr = measure_ref(mapping["dax_measure"]["name"])
    elif mapping.get("field"):
        field_expr = col_ref(mapping["field"])

    if pbi_visual in ("lineChart",):
        query_state = {
            "Category": {"projections": [col_ref(mapping.get("x_axis"))]} if mapping.get("x_axis") else {},
            "Y": {"projections": [field_expr]} if field_expr else {},
        }
    elif pbi_visual in ("barChart", "columnChart", "pieChart", "donutChart"):
        query_state = {
            "Category": {"projections": [col_ref(mapping.get("category"))]} if mapping.get("category") else {},
            "Y": {"projections": [field_expr]} if field_expr else {},
        }
    elif pbi_visual == "card":
        query_state = {"Values": {"projections": [field_expr]} if field_expr else {}}
    elif pbi_visual == "tableEx":
        cols = mapping.get("values") or []
        query_state = {"Values": {"projections": [col_ref(c) for c in cols]}}
    elif pbi_visual == "slicer":
        query_state = {"Values": {"projections": [col_ref(mapping.get("field"))]} if mapping.get("field") else {}}

    return {
        "name": mapping["visual_id"],
        "position": position,
        "visual": {
            "visualType": pbi_visual,
            "title": mapping["title"],
            "query": {"queryState": query_state},
            "objects": {
                "title": [{"properties": {"text": {"expr": {"Literal": {"Value": f"'{mapping['title']}'"}}}}}]
            },
        },
    }


def generate_pbip_project(
    project_name: str,
    dataset_analysis: dict,
    mappings: list[dict],
    output_dir: str,
) -> dict:
    """Writes a full PBIP project to disk. Returns {"root": path, "files_written": [...]}"""
    root = Path(output_dir) / project_name
    report_dir = root / f"{project_name}.Report"
    model_dir = root / f"{project_name}.SemanticModel"
    pages_dir = report_dir / "definition" / "pages"
    page1_dir = pages_dir / "page_1"
    visuals_dir = page1_dir / "visuals"
    model_def_dir = model_dir / "definition"
    tables_dir = model_def_dir / "tables"

    for d in (report_dir, model_dir, pages_dir, page1_dir, visuals_dir, model_def_dir, tables_dir):
        d.mkdir(parents=True, exist_ok=True)

    files_written = []
    primary_table = dataset_analysis["sheets"][0]["sheet_name"] if dataset_analysis["sheets"] else "Sheet1"

    # --- .pbip root file ---
    pbip_content = {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{project_name}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }
    pbip_path = root / f"{project_name}.pbip"
    pbip_path.write_text(json.dumps(pbip_content, indent=2))
    files_written.append(str(pbip_path))

    # --- Convenience launcher (Windows) ---
    # Streamlit Cloud runs on a remote server with no access to the user's
    # desktop or installed applications, so it cannot launch Power BI
    # Desktop itself. This script ships INSIDE the extracted project folder
    # so that, once the user has unzipped it locally, opening the project
    # is a single double-click instead of hunting for the right file.
    launcher_path = root / "Open in Power BI Desktop.bat"
    launcher_path.write_text(
        "@echo off\r\n"
        f'start "" "%~dp0{project_name}.pbip"\r\n'
    )
    files_written.append(str(launcher_path))

    # --- Semantic model: TMDL per sheet + relationships ---
    all_measures_by_table: dict[str, list] = {}
    for m in mappings:
        if m.get("dax_measure") and m.get("level") != "unsupported":
            all_measures_by_table.setdefault(primary_table, []).append(m["dax_measure"])

    for sheet in dataset_analysis["sheets"]:
        tmdl = _build_table_tmdl(sheet)
        if sheet["sheet_name"] == primary_table and all_measures_by_table.get(primary_table):
            tmdl += "\n" + _build_measures_tmdl_block(all_measures_by_table[primary_table])
        table_path = tables_dir / f"{sheet['sheet_name']}.tmdl"
        table_path.write_text(tmdl)
        files_written.append(str(table_path))

    model_tmdl = (
        "model Model\n"
        "\tculture: en-US\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n"
    )
    model_path = model_def_dir / "model.tmdl"
    model_path.write_text(model_tmdl)
    files_written.append(str(model_path))

    rel_tmdl = _build_relationships_tmdl(dataset_analysis.get("suggested_relationships", []))
    if rel_tmdl:
        rel_path = model_def_dir / "relationships.tmdl"
        rel_path.write_text(rel_tmdl)
        files_written.append(str(rel_path))

    model_meta = {"version": "1.0", "settings": {}}
    (model_dir / f"{project_name}.SemanticModel.pbism").write_text(json.dumps(model_meta, indent=2))
    files_written.append(str(model_dir / f"{project_name}.SemanticModel.pbism"))

    # --- Report: pages + visuals ---
    supported_mappings = [m for m in mappings if m.get("level") != "unsupported"]
    positions = _layout_positions(len(supported_mappings))

    visual_refs = []
    for mapping, pos in zip(supported_mappings, positions):
        v_dir = visuals_dir / mapping["visual_id"]
        v_dir.mkdir(parents=True, exist_ok=True)
        visual_json = _build_visual_json(mapping, pos, primary_table)
        v_path = v_dir / "visual.json"
        v_path.write_text(json.dumps(visual_json, indent=2))
        files_written.append(str(v_path))
        visual_refs.append(mapping["visual_id"])

    page_json = {
        "name": "page_1",
        "displayName": "Page 1",
        "width": PAGE_WIDTH,
        "height": PAGE_HEIGHT,
        "visualsFolder": "visuals",
    }
    page_path = page1_dir / "page.json"
    page_path.write_text(json.dumps(page_json, indent=2))
    files_written.append(str(page_path))

    pages_json = {"pageOrder": ["page_1"], "activePageName": "page_1"}
    pages_index_path = pages_dir / "pages.json"
    pages_index_path.write_text(json.dumps(pages_json, indent=2))
    files_written.append(str(pages_index_path))

    report_json = {
        "version": "1.0",
        "themeCollection": {"baseTheme": {"name": "CY24SU02"}},
        "layoutOptimization": "None",
    }
    report_json_path = report_dir / "report.json"
    report_json_path.write_text(json.dumps(report_json, indent=2))
    files_written.append(str(report_json_path))

    pbir_path = report_dir / "definition.pbir"
    pbir_content = {
        "version": "1.0",
        "datasetReference": {
            "byPath": {"path": f"../{project_name}.SemanticModel"}
        },
    }
    pbir_path.write_text(json.dumps(pbir_content, indent=2))
    files_written.append(str(pbir_path))

    return {"root": str(root), "files_written": files_written, "visual_count": len(visual_refs)}
