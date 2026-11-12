"""Shared relational storage. SQLite for local use; PostgreSQL for deployment."""
import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, String, Float, Integer, JSON, ForeignKey, UniqueConstraint, CheckConstraint, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import load_local_settings

PROJECT = Path(__file__).resolve().parents[2]
load_local_settings(PROJECT)
WORKSPACE = Path(os.environ.get('NASA_WORKSPACE', PROJECT.parent)).resolve()
RUNTIME = Path(os.environ.get('RUNTIME_DIR', '/tmp/appa-runtime' if os.environ.get('VERCEL') else PROJECT / 'runtime')).resolve()
RUNTIME.mkdir(parents=True, exist_ok=True)

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def make_engine(url=None):
    url = url or os.environ.get('DATABASE_URL')
    if os.environ.get('VERCEL') and (not url or url.startswith('sqlite')):
        raise RuntimeError('Vercel requires a persistent PostgreSQL DATABASE_URL')
    url = url or f'sqlite:///{RUNTIME / "dashboard.db"}'
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql+psycopg://', 1)
    elif url.startswith('postgresql://'):
        url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
    engine = create_engine(url, pool_pre_ping=True, hide_parameters=True,
        **({'connect_args': {'check_same_thread': False, 'timeout': 30}} if url.startswith('sqlite') else {
            'connect_args': {'prepare_threshold': None, 'connect_timeout': 10},
            'poolclass': NullPool, 'execution_options': {'schema_translate_map': {None: 'appa'}}}))
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    else:
        @event.listens_for(engine, 'begin')
        def preserve_float_precision(connection):
            # Pooler sessions may default to rounded, 15-digit float output.
            # Set this within every transaction so source values round-trip exactly.
            connection.exec_driver_sql('SET LOCAL extra_float_digits = 3')
    return engine

class Base(DeclarativeBase):
    pass

class Photo(Base):
    __tablename__ = 'photos'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    captured_at: Mapped[str | None] = mapped_column(String, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, index=True)
    longitude: Mapped[float | None] = mapped_column(Float)
    mission: Mapped[str] = mapped_column(String, index=True)
    thumbnail_url: Mapped[str] = mapped_column(String)
    image_url: Mapped[str] = mapped_column(String)
    original_url: Mapped[str] = mapped_column(String)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Private worker input, never serialized by the API.
    local_image: Mapped[str | None] = mapped_column(String)
    image_sha256: Mapped[str | None] = mapped_column(String)

class ModelVersion(Base):
    __tablename__ = 'model_versions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    target: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    units: Mapped[str] = mapped_column(String)
    manifest: Mapped[dict] = mapped_column(JSON)

class Run(Base):
    __tablename__ = 'prediction_runs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    completed_at: Mapped[str | None] = mapped_column(String)
    provenance: Mapped[dict] = mapped_column(JSON)

class Matchup(Base):
    __tablename__ = 'satellite_matchups'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    dataset_sha256: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)

class Estimate(Base):
    __tablename__ = 'estimates'
    __table_args__ = (UniqueConstraint('run_id', 'photo_id', 'model_id'), CheckConstraint('value > 0', name='positive_estimate'))
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('prediction_runs.id'), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey('model_versions.id'), index=True)
    matchup_id: Mapped[str | None] = mapped_column(ForeignKey('satellite_matchups.id'), index=True)
    target: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    role: Mapped[str] = mapped_column(String, index=True)
    split: Mapped[str | None] = mapped_column(String, index=True)
    scene_group: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('prediction_runs.id'), index=True)
    model_ids: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    updated_at: Mapped[str] = mapped_column(String, default=utcnow)
    lease_until: Mapped[float | None] = mapped_column(Float)
    lease_token: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(String)

engine = make_engine()
Session = sessionmaker(engine, expire_on_commit=False)

def initialize(engine_to_use=engine):
    if engine_to_use.dialect.name == 'postgresql' and os.environ.get('DB_AUTO_CREATE') == '0':
        return  # Production schema is applied with the migration account, never the runtime role.
    if engine_to_use.dialect.name == 'postgresql':
        with engine_to_use.begin() as connection:
            connection.execute(text('CREATE SCHEMA IF NOT EXISTS appa'))
    Base.metadata.create_all(engine_to_use)

class Overlay(Base):
    __tablename__ = 'overlays'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    target: Mapped[str] = mapped_column(String)
    image_sha256: Mapped[str] = mapped_column(String)
    model_version: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    manifest: Mapped[dict] = mapped_column(JSON)
    # Portable to PostgreSQL; no dependency on the API host's filesystem.
    payload: Mapped[dict] = mapped_column(JSON)

class AnnotationRevision(Base):
    __tablename__ = 'annotation_revisions'
    __table_args__ = (UniqueConstraint('photo_id', 'revision'),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    image_sha256: Mapped[str] = mapped_column(String)
    reviewer: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    regions: Mapped[list] = mapped_column(JSON)

class Calibration(Base):
    __tablename__ = 'calibrations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey('model_versions.id'), index=True)
    created_at: Mapped[str] = mapped_column(String, default=utcnow)
    coverage: Mapped[float] = mapped_column(Float)
    log_radius: Mapped[float] = mapped_column(Float)
    manifest: Mapped[dict] = mapped_column(JSON)

class CatalogSnapshot(Base):
    """Append-only source rows; refreshed metadata cannot rewrite old evidence."""
    __tablename__ = 'catalog_snapshots'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    source: Mapped[str] = mapped_column(String)
    imported_at: Mapped[str] = mapped_column(String, default=utcnow)
    data: Mapped[dict] = mapped_column(JSON)

class InputAsset(Base):
    """Versioned model input, separate from the canonical NASA photo identity."""
    __tablename__ = 'input_assets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    photo_id: Mapped[str] = mapped_column(ForeignKey('photos.id'), index=True)
    image_sha256: Mapped[str] = mapped_column(String, index=True)
    local_path: Mapped[str | None] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    provenance: Mapped[dict] = mapped_column(JSON)
