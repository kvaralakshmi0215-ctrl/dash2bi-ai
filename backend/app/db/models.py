import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from app.db.database import Base


def gen_id():
    return str(uuid.uuid4())


class Session(Base):
    """A conversion session groups one dataset upload + one dashboard upload."""
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_id)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="created")  # created, dataset_uploaded, dashboard_uploaded,
    #                                              analyzed, mapped, previewed, converting,
    #                                              converted, failed


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    kind = Column(String)  # "dataset" | "dashboard"
    original_filename = Column(String)
    stored_path = Column(String)
    size_bytes = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    kind = Column(String)  # "dataset" | "dashboard"
    result_json = Column(Text)  # JSON blob
    created_at = Column(DateTime, default=datetime.utcnow)


class VisualMapping(Base):
    __tablename__ = "visual_mappings"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    mapping_json = Column(Text)  # JSON blob: list of mapped visuals
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversionRecord(Base):
    __tablename__ = "conversions"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("sessions.id"))
    status = Column(String, default="pending")  # pending, running, completed, failed
    report_json = Column(Text)  # conversion report: converted/warnings/errors
    output_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
