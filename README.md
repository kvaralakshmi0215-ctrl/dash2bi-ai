# Dash2BI AI

Turn AI-generated HTML dashboards into real Power BI Projects — without manually
rebuilding every chart, KPI, table, and filter.

```
Excel Dataset + HTML Dashboard → AI Analysis → Dashboard Mapping → Power BI Project (PBIP)
```

This is a working MVP: real Excel/CSV profiling with pandas, real static HTML/JS
analysis (no code execution), a configurable AI layer for semantic column matching
and DAX generation, and a generator that writes an actual **Power BI Project
(PBIP)** — Microsoft's supported, text-based project format (TMDL semantic model +
JSON report definition) that opens directly in Power BI Desktop via
`File → Open → Power BI Project`.

**This tool never renames or repackages an HTML file as `.pbix`.** `.pbix` is a
proprietary binary format and is intentionally out of scope. Anything that can't
be confidently converted is reported to the user, not silently faked.

---

## 1. Architecture

```
dash2bi-ai/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── main.py          App entrypoint, CORS, startup
│   │   ├── api/routes.py    All REST endpoints
│   │   ├── services/
│   │   │   ├── excel_analyzer.py    pandas-based dataset profiling
│   │   │   ├── html_analyzer.py     BeautifulSoup + esprima (AST) HTML/JS analysis
│   │   │   ├── ai_service.py        Configurable AI layer (Anthropic or heuristic fallback)
│   │   │   ├── mapping_engine.py    HTML visual → Power BI visual + column mapping
│   │   │   ├── pbip_generator.py    Writes a real PBIP project (TMDL + report JSON)
│   │   │   └── conversion_service.py Orchestrates preview + full conversion + zip
│   │   ├── models/schemas.py        Pydantic request/response models
│   │   ├── db/{database,models}.py  SQLAlchemy (SQLite by default)
│   │   └── core/config.py           Settings via .env
│   ├── requirements.txt
│   └── .env.example
└── frontend/                 React + TypeScript + Tailwind SPA
    └── src/
        ├── pages/             Landing, Dashboard, Upload, Analyze, Preview, Conversion, History, Settings
        ├── components/        Sidebar, shared UI primitives
        ├── api/client.ts      Typed fetch client for the backend
        ├── state/             Workflow context (session/analysis/mapping state)
        └── types/             Shared TypeScript types mirroring backend schemas
```

**Data flow:** Upload → Analyze (pandas + BeautifulSoup/esprima) → Map (AI or
heuristic column matching + DAX generation) → Preview (Level 1/2/3 summary) →
Convert (writes PBIP to disk, zips it) → Download.

---

## 2. Installation

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY if you want AI-assisted matching/DAX,
# or leave AI_PROVIDER=none to run on the deterministic fallback only
```

### Frontend

```bash
cd frontend
npm install
```

---

## 3. Running

### Backend

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

API docs are auto-served at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api/*` to
`http://localhost:8000` (see `vite.config.ts`).

---

## 4. Environment variables (backend `.env`)

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | Informational |
| `DATABASE_URL` | `sqlite:///./dash2bi.db` | SQLAlchemy DSN. Swap for a Postgres URL to scale up — no code changes needed. |
| `MAX_UPLOAD_SIZE_MB` | `25` | Per-file upload limit |
| `UPLOAD_DIR` | `./uploads` | Where raw uploads are stored |
| `OUTPUT_DIR` | `./outputs` | Where generated PBIP projects + zips are written |
| `AI_PROVIDER` | `none` | `anthropic` or `none` |
| `ANTHROPIC_API_KEY` | — | Required if `AI_PROVIDER=anthropic` |
| `AI_MODEL` | `claude-sonnet-4-6` | Model string used for matching/DAX generation |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | CORS allow-list |

Secrets are never sent to the frontend; the API key stays server-side.

---

## 5. How the conversion pipeline works

1. **Upload** — Excel/CSV dataset and an HTML file or a `.zip` of HTML/CSS/JS
   are uploaded and stored server-side under `UPLOAD_DIR`.
2. **Analyze**
   - *Dataset:* pandas profiles every sheet — column dtypes (numeric / date /
     categorical / text / boolean), missing values, unique counts, and basic
     stats (min/max/mean/sum for numeric columns).
   - *Dashboard:* BeautifulSoup parses the DOM for KPI-like elements, `<table>`s,
     and `<select>` filters. Inline/linked JavaScript is parsed with `esprima`
     into an AST (never executed) to statically pull out Chart.js `new
     Chart(ctx, {...})` calls — chart type, title, and data-field references.
3. **Map** — for each detected visual, the mapping engine assigns a Power BI
   visual type from a static lookup table, then calls the AI service (or a
   deterministic string-similarity fallback if no AI provider is configured)
   to match chart titles/data-refs to actual dataset columns. Every mapping
   gets a confidence score and is classified:
   - **Level 1 — Automatic**: confidence ≥ 0.85, mapping applied directly.
   - **Level 2 — AI Suggested**: confidence between 0.35 and 0.85, shown to
     the user for confirmation (editable in the Preview screen).
   - **Level 3 — Unsupported**: confidence too low, or the visual type
     couldn't be identified at all — excluded from the report generation and
     listed with a suggested alternative instead.
   Where a numeric field + aggregation is resolved, a DAX measure is drafted
   and passed through a structural validator (balanced parens/brackets/quotes)
   before being shown to the user.
4. **Preview** — aggregated counts of convertible visuals by type, plus every
   warning and unsupported item, are returned to the frontend before anything
   is generated.
5. **Convert** — `pbip_generator.py` writes a real PBIP project to disk:
   - `<name>.pbip` — project pointer file
   - `<name>.SemanticModel/definition/` — TMDL table definitions (columns,
     data types, Power Query `Excel.CurrentWorkbook()` partitions) and any
     generated DAX measures
   - `<name>.Report/definition/` — `report.json`, `pages/pages.json`, and one
     `visual.json` per converted visual, with an approximate grid layout
     derived from the detected HTML structure
   The project folder is then zipped for a single-file download.
6. **Download** — the zip is served from `/api/download/{conversion_id}`.
   Unzip it and open the `.pbip` file directly in Power BI Desktop.

---

## 6. Supported visual types (MVP)

| HTML source | Power BI visual |
|---|---|
| Chart.js `type: 'line'` | Line Chart |
| Chart.js `type: 'bar'` | Bar / Column Chart |
| Chart.js `type: 'pie'` | Pie Chart |
| Chart.js `type: 'doughnut'` | Donut Chart |
| KPI/metric card elements | Card |
| `<table>` | Table |
| `<select>` dropdown | Slicer |

Anything else (custom canvas/D3/Plotly visuals, Chart.js `radar`/`scatter`/
`bubble`/`polarArea`, etc.) is reported as **unsupported** with a suggested
closest alternative — it is never silently dropped or faked.

---

## 7. Security

- File type allow-lists enforced server-side for both dataset and dashboard
  uploads (`.xlsx/.xls/.csv`, `.html/.htm/.zip`).
- Per-file size limit (`MAX_UPLOAD_SIZE_MB`), enforced while streaming to disk.
- Uploaded JavaScript is **only ever statically parsed** (`esprima` AST) —
  never executed on the server.
- API keys are read from `.env` and never exposed to the frontend bundle.
- Pydantic models validate all request/response payloads.

---

## 8. Known limitations (MVP scope)

- Layout reconstruction is an approximate grid packing, not pixel-exact.
- Chart-type detection currently targets Chart.js constructor patterns
  specifically; other libraries (ECharts, Highcharts, Plotly, D3) fall back to
  generic "chart-like container" detection and are marked unsupported pending
  dedicated parsers.
- DAX generation covers simple aggregation measures (SUM/AVERAGE/COUNT/MIN/MAX)
  and AI-drafted measures when a provider is configured; complex multi-step
  DAX (time intelligence, nested `CALCULATE`, etc.) is not yet generated.
- Relationship detection between sheets is name-based (shared/`*Id`/`*Key`
  columns), not a full schema inference engine.
- No authentication/multi-tenant support yet — the MVP is single-user/local.

## 9. Future improvements

- Additional chart-library parsers (ECharts, Highcharts, Plotly, D3).
- Direct Power BI REST API publish (push the generated semantic model/report
  straight into a workspace) once service-principal auth is configured.
- PostgreSQL-backed multi-user deployment with auth.
- Richer layout fidelity (absolute positioning from computed CSS box models).
- Manual visual-by-visual editing UI beyond the current field-correction inputs.
