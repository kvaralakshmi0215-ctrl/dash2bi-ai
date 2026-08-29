"""
AI layer, kept behind a provider-agnostic interface so the underlying model
can be swapped via the AI_PROVIDER env var without touching call sites.

- AI_PROVIDER=anthropic -> calls the Anthropic Messages API for semantic
  column matching + DAX generation, and returns structured JSON.
- AI_PROVIDER=none -> deterministic fallback using string-similarity
  heuristics only. The app still functions, just with lower match quality
  and simpler DAX; this keeps the MVP usable without any API key.

Nothing here fabricates a "correct" mapping when it isn't confident — low
confidence is surfaced to the caller so the API layer can flag it for user
confirmation (Level 2) rather than silently guessing.
"""
import json
import difflib
from app.core.config import settings

_client = None
if settings.AI_PROVIDER == "anthropic" and settings.ANTHROPIC_API_KEY:
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:
        _client = None


def _call_anthropic_json(system: str, user: str) -> dict | None:
    if _client is None:
        return None
    try:
        resp = _client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.lower().startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return None


def _best_string_match(target: str, candidates: list[str]) -> tuple[str | None, float]:
    if not candidates:
        return None, 0.0
    matches = difflib.get_close_matches(target.lower(), [c.lower() for c in candidates], n=1, cutoff=0.0)
    if not matches:
        return None, 0.0
    ratio = difflib.SequenceMatcher(None, target.lower(), matches[0]).ratio()
    # map back to original casing
    for c in candidates:
        if c.lower() == matches[0]:
            return c, ratio
    return None, 0.0


def match_visual_to_columns(visual_title: str, visual_type: str, data_refs: list[str],
                             available_columns: list[dict]) -> dict:
    """
    Returns:
      {
        "x_axis": str|None, "y_axis": str|None, "field": str|None,
        "aggregation": "SUM"|"AVERAGE"|"COUNT", "confidence": float,
        "reasoning": str
      }
    """
    col_names = [c["name"] for c in available_columns]
    numeric_cols = [c["name"] for c in available_columns if c["dtype"] == "numeric"]
    date_cols = [c["name"] for c in available_columns if c["dtype"] == "date"]
    categorical_cols = [c["name"] for c in available_columns if c["dtype"] == "categorical"]

    if _client is not None:
        system = (
            "You map a dashboard visual (title, type, referenced data labels) to columns "
            "of a tabular dataset. Respond with ONLY compact JSON, no prose, no markdown fences. "
            'Schema: {"x_axis": string|null, "y_axis": string|null, "field": string|null, '
            '"category": string|null, "aggregation": "SUM"|"AVERAGE"|"COUNT"|"MIN"|"MAX"|null, '
            '"confidence": number between 0 and 1, "reasoning": short string}. '
            "For visual_type 'scatterChart', set x_axis and y_axis to two DIFFERENT numeric "
            "columns (no category/field/aggregation needed). For 'lineChart'/'areaChart', set "
            "x_axis (usually a date column) and y_axis (a numeric column) plus aggregation. For "
            "'barChart'/'columnChart'/'pieChart'/'donutChart', set category (a categorical column) "
            "and field (a numeric column) plus aggregation. For 'card', set field and aggregation only. "
            "Only reference column names that literally appear in the provided column list. "
            "If nothing plausible fits, set confidence low (< 0.5) rather than guessing confidently."
        )
        user = json.dumps({
            "visual_title": visual_title,
            "visual_type": visual_type,
            "js_data_refs": data_refs,
            "columns": available_columns,
        })
        result = _call_anthropic_json(system, user)
        if result and isinstance(result, dict):
            # sanitize: only accept column names that actually exist
            for key in ("x_axis", "y_axis", "field", "category"):
                if result.get(key) and result[key] not in col_names:
                    result[key] = None
            result.setdefault("aggregation", "SUM")
            result.setdefault("confidence", 0.5)
            return result

    # --- Deterministic fallback heuristic ---
    text_pool = " ".join([visual_title or ""] + data_refs).lower()

    if visual_type == "scatterChart":
        # Scatter needs two DIFFERENT numeric columns (X and Y), not a
        # category/value pair — pick the two closest matches by name.
        if len(numeric_cols) >= 2:
            ranked = sorted(numeric_cols, key=lambda c: -difflib.SequenceMatcher(None, text_pool, c.lower()).ratio())
            x_axis, y_axis = ranked[0], ranked[1]
            confidence = 0.6
        elif len(numeric_cols) == 1:
            x_axis, y_axis, confidence = numeric_cols[0], None, 0.2
        else:
            x_axis, y_axis, confidence = None, None, 0.0
        return {
            "x_axis": x_axis, "y_axis": y_axis, "field": None, "category": None,
            "aggregation": None, "confidence": confidence,
            "reasoning": "heuristic: picked two numeric columns by name similarity (no AI provider configured)",
        }

    field, field_score = _best_string_match(text_pool, numeric_cols) if numeric_cols else (None, 0)
    x_axis = None
    x_score = 0
    if visual_type in ("lineChart", "areaChart") and date_cols:
        x_axis, x_score = date_cols[0], 0.8
    elif visual_type in ("barChart", "columnChart", "pieChart", "donutChart") and categorical_cols:
        x_axis, x_score = _best_string_match(text_pool, categorical_cols)

    confidence = round(min(0.95, (field_score + x_score) / 2 + 0.2), 2) if field else 0.2
    return {
        "x_axis": x_axis,
        "y_axis": field if visual_type in ("lineChart", "areaChart") else None,
        "field": field,
        "category": x_axis if visual_type in ("barChart", "columnChart", "pieChart", "donutChart") else None,
        "aggregation": "SUM",
        "confidence": confidence,
        "reasoning": "heuristic string-similarity match (no AI provider configured)",
    }


def generate_dax_measure(measure_name: str, table: str, field: str, aggregation: str,
                          extra_context: str | None = None) -> dict:
    """Returns {"name": str, "expression": str, "validated": bool, "notes": str}"""
    agg_fn = {"SUM": "SUM", "AVERAGE": "AVERAGE", "COUNT": "COUNTA", "MIN": "MIN", "MAX": "MAX"}.get(
        aggregation.upper(), "SUM"
    )

    if _client is not None:
        system = (
            "You write a single Power BI DAX measure. Respond with ONLY compact JSON, no prose. "
            'Schema: {"name": string, "expression": string (valid DAX), "notes": string}. '
            "Use exactly the table/column names given. Keep the expression syntactically valid DAX."
        )
        user = json.dumps({
            "measure_name": measure_name, "table": table, "field": field,
            "aggregation": aggregation, "extra_context": extra_context,
        })
        result = _call_anthropic_json(system, user)
        if result and result.get("expression"):
            expr = result["expression"]
            validated = _validate_dax_syntax(expr)
            return {
                "name": result.get("name", measure_name),
                "expression": expr,
                "validated": validated,
                "notes": result.get("notes", ""),
            }

    # Deterministic fallback: simple aggregation measure
    expr = f"{agg_fn}('{table}'[{field}])"
    return {
        "name": measure_name,
        "expression": f"{measure_name} = {expr}",
        "validated": _validate_dax_syntax(expr),
        "notes": "rule-based aggregation (no AI provider configured)",
    }


def _validate_dax_syntax(expr: str) -> bool:
    """Lightweight structural validation: balanced parens/brackets/quotes.
    This is NOT a full DAX parser — it catches obviously malformed output
    before it's shown to the user, per the 'never silently create incorrect
    calculations' requirement."""
    if not expr or not expr.strip():
        return False
    pairs = {"(": ")", "[": "]"}
    stack = []
    for ch in expr:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in (")", "]"):
            if not stack or stack.pop() != ch:
                return False
    if stack:
        return False
    if expr.count("'") % 2 != 0:
        return False
    return True
