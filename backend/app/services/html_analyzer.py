"""
Real static analysis of an uploaded HTML dashboard (or a .zip containing
HTML/CSS/JS). We do NOT execute any uploaded JavaScript. Instead we:

  1. Parse the DOM with BeautifulSoup to find KPI cards, tables, dropdowns,
     and chart-container elements.
  2. Parse inline/linked <script> contents to statically find chart-library
     configuration calls for several common charting libraries (Chart.js,
     ECharts, ApexCharts, Highcharts, Google Charts, Plotly) and pull out
     type/title/data-field references — via AST parsing for Chart.js
     (highest fidelity) and via bounded, balanced-brace text extraction +
     regex for the others (these libraries don't have one simple
     `new X(config)` shape esprima's AST alone makes easy to key off of
     generically, so a lighter-weight textual scan is used; still purely
     static, never executed).
  3. Parse <style> blocks + inline styles for a rough layout grid & theme
     colors.

This keeps analysis safe (no eval, no server-side JS execution) while still
inspecting the underlying markup/script rather than only "looking" at it.

Adding support for another charting library later means adding one more
`_detect_<library>` function plus an entry in LIBRARY_TYPE_MAP — the rest of
the pipeline (mapping engine, DAX generation, PBIP writer) is unaffected.
"""
import re
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

try:
    import esprima
except ImportError:  # pragma: no cover
    esprima = None

CHARTJS_TYPE_MAP = {
    "line": "lineChart",
    "bar": "barChart",
    "pie": "pieChart",
    "doughnut": "donutChart",
    "radar": "unsupported",
    "polarArea": "unsupported",
    "scatter": "scatterChart",
    "bubble": "unsupported",
}

# Maps each library's own type vocabulary onto our internal candidate_type.
# A value of "unsupported" is a deliberate, informed choice (e.g. gauges,
# radial bars) rather than a gap — it's surfaced to the user as Level 3
# with a specific reason, never silently dropped.
LIBRARY_TYPE_MAP = {
    "echarts": {
        "line": "lineChart", "bar": "barChart", "pie": "pieChart",
        "scatter": "scatterChart", "gauge": "unsupported", "radar": "unsupported",
        "funnel": "unsupported", "heatmap": "unsupported", "treemap": "unsupported",
    },
    "apexcharts": {
        "line": "lineChart", "bar": "barChart", "area": "areaChart",
        "pie": "pieChart", "donut": "donutChart", "scatter": "scatterChart",
        "radialBar": "unsupported", "heatmap": "unsupported", "treemap": "unsupported",
        "candlestick": "unsupported", "radar": "unsupported",
    },
    "highcharts": {
        "line": "lineChart", "bar": "barChart", "column": "columnChart",
        "area": "areaChart", "pie": "pieChart", "scatter": "scatterChart",
        "gauge": "unsupported", "heatmap": "unsupported", "treemap": "unsupported",
    },
    "google-charts": {
        "line": "lineChart", "column": "columnChart", "bar": "barChart",
        "pie": "pieChart", "area": "areaChart", "scatter": "scatterChart",
        "combo": "unsupported", "gauge": "unsupported", "geo": "unsupported",
    },
    "plotly": {
        "scatter": "scatterChart", "bar": "barChart", "pie": "pieChart",
        "line": "lineChart", "box": "unsupported", "heatmap": "unsupported",
        "histogram": "unsupported",
    },
}

UNSUPPORTED_REASONS = {
    "gauge": "Gauge visuals have no direct static-analysis equivalent here; "
             "Power BI's Gauge visual requires a target/min/max value set, which "
             "this analyzer does not yet infer automatically.",
    "radar": "Radar/spider charts have no equivalent built-in Power BI visual type.",
    "heatmap": "Heatmaps are not yet supported by the mapping engine.",
    "treemap": "Treemaps are not yet supported by the mapping engine.",
    "radialBar": "Radial bar visuals are not yet supported by the mapping engine.",
    "funnel": "Funnel charts are not yet supported by the mapping engine.",
    "combo": "Combo charts (mixed visual types in one chart) are not yet decomposed into separate Power BI visuals.",
    "geo": "Geo/map charts require geographic role assignment this analyzer does not yet infer.",
    "candlestick": "Candlestick charts have no direct Power BI equivalent visual.",
    "box": "Box-and-whisker plots are not yet supported by the mapping engine.",
    "histogram": "Histograms are not yet supported by the mapping engine (would require binning logic).",
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
    """Statically walk the AST for `new Chart(ctx, {...})` calls (Chart.js pattern)."""
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


def _extract_balanced_braces(text: str, start: int, max_len: int = 20_000) -> str | None:
    """Given the index of an opening '{', return the balanced {...} substring.
    Bounded so a malformed/huge script can't cause a runaway scan."""
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    end = min(len(text), start + max_len)
    for i in range(start, end):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None  # unbalanced within max_len — treat as not found rather than guess


def _resolve_config_object(js_text: str, second_arg_token: str, arg_end_pos: int) -> str | None:
    """The second argument to a chart constructor/method is either an inline
    object literal (second_arg_token == '{') or a bare identifier referring
    to a variable declared earlier (second_arg_token == that identifier's
    name) — e.g. `var options = {...}; new ApexCharts(el, options);` is the
    officially-documented ApexCharts pattern, not an edge case. Both forms
    need to resolve to the same balanced-brace object text."""
    if second_arg_token == "{":
        return _extract_balanced_braces(js_text, arg_end_pos)

    # Bare identifier: find its most recent `name = {` assignment before the
    # call site (search the whole preceding text; real dashboards usually
    # declare the config object shortly before using it).
    var_pattern = re.compile(rf"\b{re.escape(second_arg_token)}\s*=\s*\{{")
    best_obj = None
    for vm in var_pattern.finditer(js_text, 0, arg_end_pos + 1):
        brace_idx = js_text.find("{", vm.end() - 1)
        obj = _extract_balanced_braces(js_text, brace_idx)
        if obj:
            best_obj = obj  # keep the closest (last) match before the call
    return best_obj


def _detect_echarts(js_text: str) -> list[dict]:
    """`someVar.setOption({ ... })` or `someVar.setOption(configVar)`"""
    results = []
    for m in re.finditer(r"\.setOption\s*\(\s*(\{|\w+)", js_text):
        obj = _resolve_config_object(js_text, m.group(1), m.end() - 1)
        if not obj:
            continue
        title_m = re.search(r"title\s*:\s*\{[^{}]*?text\s*:\s*['\"]([^'\"]+)['\"]", obj, re.DOTALL)
        type_m = re.search(r"series\s*:\s*\[?\s*\{[^{}]*?type\s*:\s*['\"](\w+)['\"]", obj, re.DOTALL)
        if not (title_m or type_m):
            continue
        results.append({
            "library": "echarts",
            "title": title_m.group(1) if title_m else None,
            "type": type_m.group(1) if type_m else None,
        })
    return results


def _detect_apexcharts(js_text: str) -> list[dict]:
    """`new ApexCharts(el, { ... })` or `new ApexCharts(el, configVar)`"""
    results = []
    for m in re.finditer(r"new\s+ApexCharts\s*\([^,]+,\s*(\{|\w+)", js_text):
        obj = _resolve_config_object(js_text, m.group(1), m.end() - 1)
        if not obj:
            continue
        type_m = re.search(r"chart\s*:\s*\{[^{}]*?type\s*:\s*['\"](\w+)['\"]", obj, re.DOTALL)
        title_m = re.search(r"title\s*:\s*\{[^{}]*?text\s*:\s*['\"]([^'\"]+)['\"]", obj, re.DOTALL)
        if not (title_m or type_m):
            continue
        results.append({
            "library": "apexcharts",
            "title": title_m.group(1) if title_m else None,
            "type": type_m.group(1) if type_m else None,
        })
    return results


def _detect_highcharts(js_text: str) -> list[dict]:
    """`Highcharts.chart('container', { ... })` or `Highcharts.chart('container', configVar)`"""
    results = []
    for m in re.finditer(r"Highcharts\.chart\s*\([^,]+,\s*(\{|\w+)", js_text):
        obj = _resolve_config_object(js_text, m.group(1), m.end() - 1)
        if not obj:
            continue
        type_m = re.search(r"chart\s*:\s*\{[^{}]*?type\s*:\s*['\"](\w+)['\"]", obj, re.DOTALL)
        title_m = re.search(r"title\s*:\s*\{[^{}]*?text\s*:\s*['\"]([^'\"]+)['\"]", obj, re.DOTALL)
        if not (title_m or type_m):
            continue
        results.append({
            "library": "highcharts",
            "title": title_m.group(1) if title_m else None,
            "type": type_m.group(1) if type_m else None,
        })
    return results


def _detect_google_charts(js_text: str) -> list[dict]:
    """`new google.visualization.LineChart(el)` + nearby `.draw(data, {title: '...'})`"""
    results = []
    for m in re.finditer(r"new\s+google\.visualization\.(\w+?)Chart\s*\(", js_text):
        chart_class = m.group(1)
        window = js_text[m.end():m.end() + 2000]
        draw_m = re.search(r"\.draw\s*\([^,]+,\s*", window)
        title = None
        if draw_m:
            brace_idx = window.find("{", draw_m.end() - 1)
            obj = _extract_balanced_braces(window, brace_idx) if brace_idx != -1 else None
            if obj:
                title_m = re.search(r"title\s*:\s*['\"]([^'\"]+)['\"]", obj)
                if title_m:
                    title = title_m.group(1)
        results.append({"library": "google-charts", "title": title, "type": chart_class.lower()})
    return results


def _detect_plotly(js_text: str) -> list[dict]:
    """`Plotly.newPlot(el, [{ type: '...' }], { title: '...' })`"""
    results = []
    for m in re.finditer(r"Plotly\.newPlot\s*\([^,]+,\s*\[\s*", js_text):
        brace_idx = js_text.find("{", m.end() - 1)
        obj = _extract_balanced_braces(js_text, brace_idx) if brace_idx != -1 else None
        type_m = re.search(r"type\s*:\s*['\"](\w+)['\"]", obj) if obj else None
        # layout object (title) is a separate argument after the data array closes
        title = None
        tail = js_text[m.end():m.end() + 3000]
        title_m = re.search(r"title\s*:\s*['\"]([^'\"]+)['\"]", tail)
        if title_m:
            title = title_m.group(1)
        if not (title or type_m):
            continue
        results.append({"library": "plotly", "title": title, "type": type_m.group(1) if type_m else None})
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


def _dedupe_leaf_elements(elements: list) -> list:
    """Given a list of matched BeautifulSoup elements, drop any element that
    has ANOTHER matched element nested inside it. Without this, a wrapper
    div (e.g. class="kpi-row") that also happens to match the same CSS
    selector as its child KPI cards produces one bogus "visual" whose text
    is every child's label mashed together (the bug where multiple KPI
    titles show up concatenated with no numbers, since the container's own
    text has no single number to anchor on)."""
    element_set = set(id(e) for e in elements)
    leaves = []
    for el in elements:
        has_matched_descendant = any(
            id(desc) in element_set for desc in el.find_all(True) if id(desc) != id(el)
        )
        if not has_matched_descendant:
            leaves.append(el)
    return leaves


def analyze_dashboard(file_path: str) -> dict:
    files = _extract_files_from_upload(file_path)
    main_name, html_text = _find_main_html(files)
    soup = BeautifulSoup(html_text, "html.parser")

    css_text = "\n".join(tag.get_text() for tag in soup.find_all("style"))
    for name, content in files.items():
        if name.lower().endswith(".css"):
            css_text += "\n" + content

    js_text = "\n".join(tag.get_text() for tag in soup.find_all("script") if not tag.get("src"))
    for name, content in files.items():
        if name.lower().endswith(".js"):
            js_text += "\n" + content

    detected_visuals = []
    visual_counter = 0
    matched_chart_titles = set()  # avoid re-flagging the same chart as "unknown" in the fallback pass

    # 1. Chart.js — highest fidelity (full AST parse, real data-field refs)
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

        entry = {
            "visual_id": f"chart_{visual_counter}",
            "source": "chartjs",
            "raw_title": title,
            "candidate_type": pbi_type,
            "layout": {},
            "js_data_refs": data_refs,
        }
        if pbi_type == "unsupported" and chart_type in UNSUPPORTED_REASONS:
            entry["unsupported_reason"] = UNSUPPORTED_REASONS[chart_type]
        elif pbi_type == "unsupported":
            entry["unsupported_reason"] = f"Chart.js type '{chart_type}' has no supported Power BI visual mapping."
        detected_visuals.append(entry)
        if title:
            matched_chart_titles.add(title)

    # 2. Other common charting libraries — lighter-weight text/regex extraction
    for detector in (_detect_echarts, _detect_apexcharts, _detect_highcharts, _detect_google_charts, _detect_plotly):
        for cfg in detector(js_text):
            visual_counter += 1
            library = cfg["library"]
            raw_type = cfg.get("type")
            pbi_type = LIBRARY_TYPE_MAP.get(library, {}).get(raw_type, "unsupported") if raw_type else "unsupported"
            entry = {
                "visual_id": f"{library.replace('-', '')}_{visual_counter}",
                "source": library,
                "raw_title": cfg.get("title"),
                "candidate_type": pbi_type,
                "layout": {},
                "js_data_refs": [],
            }
            if pbi_type == "unsupported":
                if raw_type in UNSUPPORTED_REASONS:
                    entry["unsupported_reason"] = UNSUPPORTED_REASONS[raw_type]
                elif raw_type is None:
                    entry["unsupported_reason"] = (
                        f"Detected a {library} chart but could not statically determine its chart type."
                    )
                else:
                    entry["unsupported_reason"] = f"{library} chart type '{raw_type}' has no supported Power BI visual mapping."
            detected_visuals.append(entry)
            if cfg.get("title"):
                matched_chart_titles.add(cfg["title"])

    any_library_matched = visual_counter > 0

    # 3. Fallback: raw canvas/chart-class containers not already claimed by a
    #    library detector above — still surfaced (never silently dropped),
    #    but honestly labeled as unidentified rather than guessed at.
    if not any_library_matched:
        seen_els = set()
        for hint in ["canvas", "[id*=chart]", "[class*=chart]"]:
            for el in soup.select(hint):
                if id(el) in seen_els:
                    continue
                seen_els.add(id(el))
                title_el = el.find_previous(["h1", "h2", "h3", "h4"]) or el.find(["h1", "h2", "h3", "h4"])
                title_text = title_el.get_text(strip=True) if title_el else None
                if title_text and title_text in matched_chart_titles:
                    continue
                visual_counter += 1
                detected_visuals.append({
                    "visual_id": f"unknown_{visual_counter}",
                    "source": "unknown",
                    "raw_title": title_text,
                    "candidate_type": "unsupported",
                    "layout": {},
                    "js_data_refs": [],
                    "unsupported_reason": (
                        "No matching chart-library configuration (Chart.js, ECharts, ApexCharts, "
                        "Highcharts, Google Charts, or Plotly) was found for this chart container. "
                        "It may use a custom-drawn canvas, a library this analyzer doesn't yet parse, "
                        "or its setup code lives in an external .js file not included in the upload."
                    ),
                })

    # 4. KPI cards — leaf-only match to avoid a wrapper div's text swallowing
    #    every child KPI into one bogus, number-less "visual".
    kpi_candidates = soup.select("[class*=kpi], [class*=card], [class*=metric], [class*=stat]")
    for el in _dedupe_leaf_elements(kpi_candidates):
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

    # 5. Tables
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

    # 6. Dropdown filters -> slicers
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
