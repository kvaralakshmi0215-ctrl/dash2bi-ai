import json
import shutil
import uuid
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session as DBSession

from app.core.config import settings
from app.db.database import get_db
from app.db import models
from app.services import excel_analyzer, html_analyzer, mapping_engine, conversion_service

router = APIRouter(prefix="/api")

ALLOWED_DATASET_EXT = {".xlsx", ".xls", ".csv"}
ALLOWED_DASHBOARD_EXT = {".html", ".htm", ".zip"}
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _get_or_create_session(db: DBSession, session_id: str | None) -> models.Session:
    if session_id:
        sess = db.get(models.Session, session_id)
        if sess:
            return sess
    sess = models.Session(status="created")
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def _save_upload(file: UploadFile, allowed_ext: set[str]) -> Path:
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(allowed_ext)}")

    dest = Path(settings.UPLOAD_DIR) / f"{uuid.uuid4()}{ext}"
    with dest.open("wb") as out:
        total = 0
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_BYTES:
                dest.unlink(missing_ok=True)
                raise HTTPException(400, f"File exceeds max size of {settings.MAX_UPLOAD_SIZE_MB}MB")
            out.write(chunk)
    return dest


@router.post("/upload/dataset")
async def upload_dataset(session_id: str | None = Form(None), file: UploadFile = File(...),
                          db: DBSession = Depends(get_db)):
    sess = _get_or_create_session(db, session_id)
    path = _save_upload(file, ALLOWED_DATASET_EXT)

    record = models.UploadedFile(
        session_id=sess.id, kind="dataset", original_filename=file.filename,
        stored_path=str(path), size_bytes=str(path.stat().st_size),
    )
    db.add(record)
    sess.status = "dataset_uploaded"
    db.commit()

    return {"session_id": sess.id, "file_id": record.id, "filename": file.filename}


@router.post("/upload/dashboard")
async def upload_dashboard(session_id: str = Form(...), file: UploadFile = File(...),
                            db: DBSession = Depends(get_db)):
    sess = db.get(models.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found. Upload a dataset first.")
    path = _save_upload(file, ALLOWED_DASHBOARD_EXT)

    record = models.UploadedFile(
        session_id=sess.id, kind="dashboard", original_filename=file.filename,
        stored_path=str(path), size_bytes=str(path.stat().st_size),
    )
    db.add(record)
    sess.status = "dashboard_uploaded"
    db.commit()

    return {"session_id": sess.id, "file_id": record.id, "filename": file.filename}


def _latest_file(db: DBSession, session_id: str, kind: str) -> models.UploadedFile:
    rows = (
        db.query(models.UploadedFile)
        .filter_by(session_id=session_id, kind=kind)
        .order_by(models.UploadedFile.created_at.desc())
        .all()
    )
    if not rows:
        raise HTTPException(400, f"No {kind} file uploaded for this session yet.")
    return rows[0]


@router.post("/analyze")
async def analyze(session_id: str = Form(...), db: DBSession = Depends(get_db)):
    sess = db.get(models.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")

    dataset_file = _latest_file(db, session_id, "dataset")
    dashboard_file = _latest_file(db, session_id, "dashboard")

    try:
        dataset_analysis = excel_analyzer.analyze_dataset(dataset_file.stored_path)
    except Exception as e:
        raise HTTPException(422, f"Failed to analyze dataset: {e}")

    try:
        dashboard_analysis = html_analyzer.analyze_dashboard(dashboard_file.stored_path)
    except Exception as e:
        raise HTTPException(422, f"Failed to analyze dashboard: {e}")

    db.add(models.AnalysisResult(session_id=session_id, kind="dataset",
                                  result_json=json.dumps(dataset_analysis)))
    db.add(models.AnalysisResult(session_id=session_id, kind="dashboard",
                                  result_json=json.dumps(dashboard_analysis)))
    sess.status = "analyzed"
    db.commit()

    return {"session_id": session_id, "dataset_analysis": dataset_analysis, "dashboard_analysis": dashboard_analysis}


def _latest_analysis(db: DBSession, session_id: str, kind: str) -> dict:
    row = (
        db.query(models.AnalysisResult)
        .filter_by(session_id=session_id, kind=kind)
        .order_by(models.AnalysisResult.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(400, f"No {kind} analysis found. Run /api/analyze first.")
    return json.loads(row.result_json)


@router.post("/map")
async def map_visuals(session_id: str = Form(...), db: DBSession = Depends(get_db)):
    dataset_analysis = _latest_analysis(db, session_id, "dataset")
    dashboard_analysis = _latest_analysis(db, session_id, "dashboard")

    mappings = mapping_engine.build_mappings(dataset_analysis, dashboard_analysis)

    db.add(models.VisualMapping(session_id=session_id, mapping_json=json.dumps(mappings)))
    sess = db.get(models.Session, session_id)
    if sess:
        sess.status = "mapped"
    db.commit()

    return {"session_id": session_id, "mappings": mappings}


@router.post("/map/update")
async def update_mapping(session_id: str = Form(...), visual_id: str = Form(...),
                          field_updates: str = Form(...), db: DBSession = Depends(get_db)):
    """Lets the user manually correct a Level-2 (ai_suggested) or Level-3 mapping."""
    row = (
        db.query(models.VisualMapping)
        .filter_by(session_id=session_id)
        .order_by(models.VisualMapping.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(400, "No mappings found for this session.")
    mappings = json.loads(row.mapping_json)
    updates = json.loads(field_updates)

    found = False
    for m in mappings:
        if m["visual_id"] == visual_id:
            m.update(updates)
            if updates.get("field") or updates.get("x_axis") or updates.get("category"):
                m["level"] = "automatic"
                m["confidence"] = 1.0
                m["warning"] = None
            found = True
            break
    if not found:
        raise HTTPException(404, f"Visual '{visual_id}' not found in current mapping set.")

    row.mapping_json = json.dumps(mappings)
    db.commit()
    return {"session_id": session_id, "mappings": mappings}


def _latest_mappings(db: DBSession, session_id: str) -> list[dict]:
    row = (
        db.query(models.VisualMapping)
        .filter_by(session_id=session_id)
        .order_by(models.VisualMapping.created_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(400, "No mappings found. Run /api/map first.")
    return json.loads(row.mapping_json)


@router.post("/preview")
async def preview(session_id: str = Form(...), db: DBSession = Depends(get_db)):
    mappings = _latest_mappings(db, session_id)
    summary = conversion_service.build_preview_summary(mappings)
    sess = db.get(models.Session, session_id)
    if sess:
        sess.status = "previewed"
    db.commit()
    return {"session_id": session_id, **summary}


@router.post("/convert")
async def convert(session_id: str = Form(...), project_name: str = Form("Dash2BI_Project"),
                   db: DBSession = Depends(get_db)):
    sess = db.get(models.Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found.")

    dataset_analysis = _latest_analysis(db, session_id, "dataset")
    mappings = _latest_mappings(db, session_id)

    conv = models.ConversionRecord(session_id=session_id, status="running")
    db.add(conv)
    sess.status = "converting"
    db.commit()
    db.refresh(conv)

    safe_project_name = "".join(c for c in project_name if c.isalnum() or c in ("_", "-")) or "Dash2BI_Project"
    report = conversion_service.run_conversion(session_id, safe_project_name, dataset_analysis, mappings)

    conv.status = report["status"]
    conv.report_json = json.dumps(report)
    conv.output_path = report.get("output_path")
    conv.error_message = "; ".join(report.get("errors", [])) or None
    conv.completed_at = datetime.utcnow()
    sess.status = "converted" if report["status"] == "completed" else "failed"
    db.commit()

    return {"conversion_id": conv.id, "session_id": session_id, **report}


@router.get("/conversion/{conversion_id}")
async def get_conversion(conversion_id: str, db: DBSession = Depends(get_db)):
    conv = db.get(models.ConversionRecord, conversion_id)
    if not conv:
        raise HTTPException(404, "Conversion not found.")
    report = json.loads(conv.report_json) if conv.report_json else {}
    return {"conversion_id": conv.id, "session_id": conv.session_id, "status": conv.status, **report}


@router.get("/download/{conversion_id}")
async def download(conversion_id: str, db: DBSession = Depends(get_db)):
    conv = db.get(models.ConversionRecord, conversion_id)
    if not conv or not conv.output_path or not Path(conv.output_path).exists():
        raise HTTPException(404, "No downloadable output for this conversion.")
    return FileResponse(conv.output_path, filename=Path(conv.output_path).name,
                         media_type="application/zip")


@router.get("/history")
async def history(db: DBSession = Depends(get_db)):
    conversions = db.query(models.ConversionRecord).order_by(models.ConversionRecord.created_at.desc()).limit(50).all()
    return [
        {
            "conversion_id": c.id, "session_id": c.session_id, "status": c.status,
            "created_at": c.created_at.isoformat(), "output_path": c.output_path,
        }
        for c in conversions
    ]
