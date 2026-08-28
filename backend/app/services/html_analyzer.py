"""
Real static analysis of an uploaded HTML dashboard (or a .zip containing
HTML/CSS/JS). We do NOT execute any uploaded JavaScript. Instead we:

  1. Parse the DOM with BeautifulSoup to find KPI cards, tables, dropdowns,
     and chart-container elements.
  2. Parse inline/linked <script> contents with esprima (a JS *parser*, not
     an interpreter) to statically find chart-library constructor calls
     (e.g. `new Chart(ctx, {type: 'bar', ...})`) and pull out type/title/
     data-field references from the object literal AST.
  3. Parse <style> blocks + inline styles for a rough layout grid & theme
     colors.

This keeps analysis safe (no eval, no server-side JS execution) while still
inspecting the underlying markup/script rather than only "looking" at it.
"""
import re
import json
import zipfile
import tempfile
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import esprima
except ImportError:  # pragma: no cover
    esprima = None

CHART_LIB_HINTS = ["chart.js", "chartjs", "echarts", "highcharts", "plotly", "d3", "apexcharts"]

CHARTJS_TYPE_MAP = {
    "line": "lineChart",
    "bar": "barChart",
    "pie": "pieChart",
    "doughnut": "donutChart",
    "radar": "unsupported",
    "polarArea": "unsupported",
    "scatter": "unsupported",
    "bubble": "unsupported",
}


def _extract_files_from_upload(file_path: str) -> dict:
    """Returns {filename: text_content} for the html/css/js involved."""
    path = Path(file_path)
    files = {}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(file_path) as zf:
            for name in zf.namelist():
                if name.endswith(("/",)):
                    continue
                if name.lower().endswith((".html", ".htm", ".css", ".js")):
                    try:
                        files[name] = zf.read(name).decode("utf-8", errors="ignore")
                    except Exception:
                        continue
    else:
        files[path.name] = path.read_text(encoding="utf-8", errors="ignore")
    return files


def _find_main_html(files: dict) -> tuple[str, str]:
    html_files = {k: v for k, v in files.items() if k.lower().endswith((".html", ".htm"))}
    if not html_files:
        raise ValueError("No .html file found in upload.")
    # Prefer index.html, else first
    for name in html_files:
        if Path(name).name.lower() == "index.html":
            return name, html_files[name]
    name = next(iter(html_files))
    return name, html_files[name]


def _js_literal_to_py(node):
    """Convert a small subset of esprima AST literal/object/array nodes to Python values."""
    if node is None:
        return None
    t = node.type
    if t == "Literal":
        return node.value
    if t == "ArrayExpression":
        return [_js_literal_to_py(el) for el in node.elements]
    if t == "ObjectExpression":
        out = {}
        for prop in node.properties:
            key = prop.key.name if hasattr(prop.key, "name") else getattr(prop.key, "value", None)
            out[key] = _js_literal_to_py(prop.value)
        return out
    if t == "Identifier":
        return f"${node.name}"  # reference to a JS variable we can't statically resolve
    if t in ("CallExpression",):
        return None
    return None


def _find_chart_constructors(js_source: str, max_js_bytes: int = 400_000, max_nodes: int = 40_000) -> list[dict]:
    """Statically walk the AST for `new Chart(ctx, {...})` calls (Chart.js pattern).

    Bounded for safety: large inline scripts (e.g. an accidentally-inlined
    charting library, rather than just dashboard config code) are skipped
    past `max_js_bytes`, and the walk itself stops after `max_nodes` visited
    nodes so a pathological/huge script can never hang the analysis step.
    """
    results = []
    if esprima is None or not js_source.strip():
        return results
    if len(js_source) > max_js_bytes:
        js_source = js_source[:max_js_bytes]

    try:
        tree = esprima.parseScript(js_source, tolerant=True)
    except Exception:
        try:
            tree = esprima.parseModule(js_source, tolerant=True)
        except Exception:
            return results

    # Iterative traversal (avoids Python recursion-depth issues on deeply
    # nested code) using vars(node) — the node's own instance attributes —
    # instead of dir(node), which pulls in every inherited method/attribute
    # and made each node visit far more expensive than it needed to be.
    stack = [tree]
    visited = 0
    while stack and visited < max_nodes:
        node = stack.pop()
        visited += 1
        if node is None or not hasattr(node, "type"):
            continue

        if node.type == "NewExpression" and getattr(node.callee, "name", None) == "Chart":
            config = None
            for a in getattr(node, "arguments", []) or []:
                if getattr(a, "type", None) == "ObjectExpression":
                    config = _js_literal_to_py(a)
            if config:
                results.append(config)

        try:
            attrs = vars(node)
        except TypeError:
            continue
        for val in attrs.values():
            if hasattr(val, "type"):
                stack.append(val)
            elif isinstance(val, list):
                for item in val:
                    if hasattr(item, "type"):
                        stack.append(item)
    return results


def _detect_theme(css_text: str) -> dict:
    colors = re.findall(r"#(?:[0-9a-fA-F]{3}){1,2}\b", css_text)
    freq = {}
    for c in colors:
        freq[c.lower()] = freq.get(c.lower(), 0) + 1
    top_colors = sorted(freq.items(), key=lambda kv: -kv[1])[:6]
    font_match = re.search(r"font-family:\s*([^;]+);", css_text)
    return {
        "palette": [c for c, _ in top_colors],
        "font_family": font_match.group(1).strip() if font_match else None,
    }


def analyze_dashboard(file_path: str) -> dict:
    files = _extract_files_from_upload(file_path)
    main_name, html_text = _find_main_html(files)
    # html.parser is part of the Python standard library, so it needs no
    # compiled extension (unlike lxml) — this keeps the app deployable on
    # hosts that don't have libxml2/libxslt build tools available.
    soup = BeautifulSoup(html_text, "html.parser")

    # gather CSS: inline <style> + any .css files in the zip
    css_text = "\n".join(tag.get_text() for tag in soup.find_all("style"))
    for name, content in files.items():
        if name.lower().endswith(".css"):
            css_text += "\n" + content

    # gather JS: inline <script> (no src) + any .js files in the zip
    js_text = "\n".join(tag.get_text() for tag in soup.find_all("script") if not tag.get("src"))
    for name, content in files.items():
        if name.lower().endswith(".js"):
            js_text += "\n" + content

    detected_visuals = []
    visual_counter = 0

    # 1. Chart.js-style chart detection via AST
    chart_configs = _find_chart_constructors(js_text)
    for cfg in chart_configs:
        visual_counter += 1
        chart_type = cfg.get("type", "unknown")
        pbi_type = CHARTJS_TYPE_MAP.get(chart_type, "unsupported")
        data = cfg.get("data", {}) or {}
        labels = data.get("labels")
        datasets = data.get("datasets") or []
        title = None
        options = cfg.get("options", {}) or {}
        plugins = options.get("plugins", {}) if isinstance(options, dict) else {}
        if isinstance(plugins, dict):
            title_cfg = plugins.get("title", {})
            if isinstance(title_cfg, dict):
                title = title_cfg.get("text")

        data_refs = []
        if isinstance(labels, str) and labels.startswith("$"):
            data_refs.append(labels)
        for ds in datasets:
            if isinstance(ds, dict):
                label = ds.get("label")
                if isinstance(label, str):
                    data_refs.append(label)
                d = ds.get("data")
                if isinstance(d, str) and d.startswith("$"):
                    data_refs.append(d)

        detected_visuals.append({
            "visual_id": f"chart_{visual_counter}",
            "source": "chartjs",
            "raw_title": title,
            "candidate_type": pbi_type,
            "layout": {},
            "js_data_refs": data_refs,
        })

    # 2. Fallback: detect other known chart-lib containers if no Chart.js configs found
    if not chart_configs:
        for hint in ["canvas", "[id*=chart]", "[class*=chart]"]:
            for el in soup.select(hint):
                visual_counter += 1
                title_el = el.find_previous(["h1", "h2", "h3", "h4"]) or el.find(["h1", "h2", "h3", "h4"])
                detected_visuals.append({
                    "visual_id": f"unknown_{visual_counter}",
                    "source": "unknown",
                    "raw_title": title_el.get_text(strip=True) if title_el else None,
                    "candidate_type": "unsupported",
                    "layout": {},
                    "js_data_refs": [],
                })
            if detected_visuals:
                break

    # 3. KPI cards: elements with class containing "kpi" or "card" holding a number + label
    for el in soup.select("[class*=kpi], [class*=card], [class*=metric], [class*=stat]"):
        text = el.get_text(" ", strip=True)
        if not text or len(text) > 80:
            continue
        number_match = re.search(r"[-+]?[\d,]+(\.\d+)?%?", text)
        if not number_match:
            continue
        label = text.replace(number_match.group(0), "").strip(" :-")
        if not label:
            continue
        visual_counter += 1
        detected_visuals.append({
            "visual_id": f"kpi_{visual_counter}",
            "source": "css-grid-kpi",
            "raw_title": label,
            "candidate_type": "card",
            "layout": {},
            "js_data_refs": [label],
        })

    # 4. Tables
    for idx, table in enumerate(soup.find_all("table"), start=1):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        caption = table.find("caption")
        title_el = table.find_previous(["h1", "h2", "h3", "h4"])
        detected_visuals.append({
            "visual_id": f"table_{idx}",
            "source": "html-table",
            "raw_title": (caption.get_text(strip=True) if caption else None)
            or (title_el.get_text(strip=True) if title_el else "Data Table"),
            "candidate_type": "table",
            "layout": {},
            "js_data_refs": headers,
        })

    # 5. Dropdown filters -> slicers
    for idx, select in enumerate(soup.find_all("select"), start=1):
        label_el = select.find_previous("label")
        options = [opt.get_text(strip=True) for opt in select.find_all("option")]
        detected_visuals.append({
            "visual_id": f"filter_{idx}",
            "source": "select",
            "raw_title": (label_el.get_text(strip=True) if label_el else select.get("name") or select.get("id") or "Filter"),
            "candidate_type": "slicer",
            "layout": {},
            "js_data_refs": options,
        })

    theme = _detect_theme(css_text)

    # rough layout grid: group top-level "section"/"div.row" children by DOM order
    layout_grid = []
    rows = soup.select("[class*=row], section, [class*=grid]")
    for row in rows[:10]:
        cells = [c.get("class", [""])[0] if c.get("class") else c.name for c in row.find_all(recursive=False)]
        if cells:
            layout_grid.append(cells)

    return {
        "file_name": main_name,
        "detected_visuals": detected_visuals,
        "theme": theme,
        "layout_grid": layout_grid,
    }
