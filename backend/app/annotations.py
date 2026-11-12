"""Append-only reviewed polygons in normalized decoded-image coordinates."""
import math
from typing import Annotated, Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from sqlalchemy import select
from .db import AnnotationRevision

Coordinate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
class Region(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: Literal['water', 'land', 'cloud', 'coast', 'plume', 'glint', 'possible_bloom', 'unknown']
    points: list[tuple[Coordinate, Coordinate]] = Field(min_length=3, max_length=500)
    @model_validator(mode='after')
    def valid_polygon(self):
        p = self.points
        if len(set(p)) != len(p): raise ValueError('Polygon has repeated vertices')
        area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(p, p[1:]+p[:1]))) / 2
        if area < 1e-7: raise ValueError('Polygon has no area')
        def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        def intersects(a,b,c,d):
            if max(a[0],b[0]) < min(c[0],d[0]) or max(c[0],d[0]) < min(a[0],b[0]): return False
            if max(a[1],b[1]) < min(c[1],d[1]) or max(c[1],d[1]) < min(a[1],b[1]): return False
            return cross(a,b,c)*cross(a,b,d) <= 0 and cross(c,d,a)*cross(c,d,b) <= 0
        edges = list(zip(p, p[1:]+p[:1]))
        for i, (a,b) in enumerate(edges):
            for j in range(i+1, len(edges)):
                if j == i+1 or (i == 0 and j == len(edges)-1): continue
                if intersects(a,b,*edges[j]): raise ValueError('Polygon edges cross')
        return self

class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=8, max_length=128)
    base_revision: int = Field(ge=0)
    image_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewer: str = Field(min_length=1, max_length=100)
    regions: list[Region] = Field(max_length=100)

def latest(s, photo_id):
    return s.scalar(select(AnnotationRevision).where(AnnotationRevision.photo_id == photo_id).order_by(AnnotationRevision.revision.desc()).limit(1))

def serialize(row):
    if not row: return {'revision': 0, 'regions': [], 'status': 'unreviewed'}
    return {k: getattr(row,k) for k in ['id', 'photo_id', 'revision', 'image_sha256', 'reviewer', 'created_at', 'regions']} | {
        'status': 'human_reviewed', 'confidence': None,
        'coordinate_system': 'Normalized decoded image x/y; origin top left',
        'limitations': 'Reviewer annotations, not automatic detections or confirmed chemical composition.'}
