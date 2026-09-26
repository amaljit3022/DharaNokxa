from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from dharanokxa.projects import ProjectStore, encode
from dharanokxa.project_imports import MAX_UPLOAD, TEMPLATES, inspect_upload
from dharanokxa.project_validation import validate_document
from dharanokxa.project_analysis import analyze
from dharanokxa.project_geometry import roadside_candidate, join_junctions, allocate_households
from dharanokxa.project_optimization import optimize_project

router = APIRouter(prefix='/projects', tags=['Engineering projects'])
pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='project-analysis')
ROOT = Path(__file__).resolve().parents[1]


def store():
    return ProjectStore(Path(os.environ.get('DHARANOKXA_PROJECTS_DIR', str(ROOT / 'results' / 'projects'))))


def get_project(pid, revision=None):
    try:
        return store().get(pid, revision)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SaveProject(BaseModel):
    revision: int = Field(ge=1)
    document: dict[str, Any]


class CommitImport(BaseModel):
    revision: int = Field(ge=1)


class GeometryAction(BaseModel):
    revision: int = Field(ge=1)
    action: str
    layer_index: int = Field(default=0, ge=0)
    sides: int = Field(default=2, ge=1, le=2)
    offset_m: float = Field(default=4, gt=0, le=100)
    diameter_mm: float = Field(default=100, gt=0)
    roughness: float = Field(default=130, gt=0)
    keep: str = ''
    remove: str = ''
    reason: str = ''
    mode: str = 'replace'


@router.post('/{pid}/geometry-preview')
def geometry_preview(pid: str, payload: GeometryAction):
    project = get_project(pid)
    if payload.revision != project['revision']:
        raise HTTPException(409, 'Save/reload the current revision before creating a geometry preview.')
    try:
        if payload.action == 'roadside':
            doc = roadside_candidate(project['document'], payload.layer_index, payload.sides,
                                     payload.offset_m, payload.diameter_mm, payload.roughness)
        elif payload.action == 'join':
            doc = join_junctions(project['document'], payload.keep, payload.remove, payload.reason)
        elif payload.action == 'households':
            doc = allocate_households(project['document'], payload.layer_index, payload.mode)
        else:
            raise ValueError('Unknown geometry action')
        return {'document': doc, 'issues': validate_document(doc)}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


def check_shape(document):
    if not isinstance(document.get('model'), dict):
        raise HTTPException(422, 'Document requires model data.')
    model = document['model']
    for key in ['nodes', 'links', 'curves', 'patterns', 'controls', 'sources']:
        if not isinstance(model.get(key), list) or not all(isinstance(o, dict) for o in model[key]):
            raise HTTPException(422, f'model.{key} must be a list of objects.')
    for key in ['options']:
        if not isinstance(model.get(key), dict):
            raise HTTPException(422, f'model.{key} must be an object.')
    for key in ['criteria']:
        if not isinstance(document.get(key), dict):
            raise HTTPException(422, f'{key} must be an object.')
    for key in ['layers', 'provenance']:
        if not isinstance(document.get(key), list):
            raise HTTPException(422, f'{key} must be a list.')
    try:
        encode(document)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get('')
def list_projects():
    return store().list()


@router.post('', status_code=201)
def create_project(payload: CreateProject):
    return store().create(payload.name.strip())


@router.get('/templates/{role}')
def template(role: str):
    if role not in TEMPLATES:
        raise HTTPException(404, 'Unknown template')
    return Response(TEMPLATES[role], media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{role}.csv"'})


@router.get('/{pid}')
def project(pid: str, revision: int | None = None):
    return get_project(pid, revision)


@router.put('/{pid}')
def save_project(pid: str, payload: SaveProject):
    get_project(pid)
    check_shape(payload.document)
    try:
        return store().save(pid, payload.revision, payload.document)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/{pid}/validate')
def validate_project(pid: str):
    try:
        issues = validate_document(get_project(pid)['document'])
        return {'issues': issues, 'valid': not any(i['severity'] == 'error' for i in issues)}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, f'Invalid draft: {exc}') from exc


@router.post('/{pid}/imports', status_code=201)
async def preview_import(pid: str, file: UploadFile = File(...), role: str = Form('network'),
                         mapping: str = Form('{}'), crs: str = Form(''), layer: str = Form(''), corrections: str = Form('{}')):
    project = get_project(pid)
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, 'Upload exceeds 20 MB.')
    try:
        columns = json.loads(mapping)
        if not isinstance(columns, dict):
            raise ValueError('Column mapping must be a JSON object.')
        preview = inspect_upload(content, file.filename or 'upload', role, project['document'], columns, crs or None, layer or None,
                                 json.loads(corrections))
    except Exception as exc:
        raise HTTPException(422, f'Import could not be read: {exc}') from exc
    iid = uuid4().hex
    root = store().root / pid / 'imports' / iid
    root.mkdir(parents=True)
    (root / 'original').write_bytes(content)
    preview.update(id=iid, revision=project['revision'], filename=Path(file.filename or 'upload').name)
    (root / 'preview.json').write_text(encode(preview), encoding='utf-8')
    return preview


@router.post('/{pid}/imports/{iid}/commit')
def commit_import(pid: str, iid: str, payload: CommitImport):
    get_project(pid)
    if len(iid) != 32 or any(c not in '0123456789abcdef' for c in iid):
        raise HTTPException(404, 'Import not found')
    path = store().root / pid / 'imports' / iid / 'preview.json'
    if not path.exists():
        raise HTTPException(404, 'Import not found')
    preview = json.loads(path.read_text(encoding='utf-8'))
    if preview['revision'] != payload.revision:
        raise HTTPException(409, 'Preview belongs to another revision. Preview the upload again.')
    if any(i['rule'] == 'IMPORT_ROW' for i in preview['issues']):
        raise HTTPException(422, 'Correct invalid input rows before committing; no rows will be silently dropped.')
    return save_project(pid, SaveProject(revision=payload.revision, document=preview['document']))


@router.get('/{pid}/runs')
def project_runs(pid: str):
    get_project(pid)
    return store().runs(pid)


@router.post('/{pid}/runs', status_code=202)
def run_project(pid: str, payload: CommitImport):
    project = get_project(pid)
    if project['revision'] != payload.revision:
        raise HTTPException(409, 'Reload the latest project before running.')
    validity = validate_project(pid)
    if not validity['valid']:
        raise HTTPException(422, {'message': 'Resolve model errors before running.', 'issues': validity['issues']})
    rid = uuid4().hex
    result = dict(id=rid, project_id=pid, revision=project['revision'], state='QUEUED')
    current_store = store()
    current_store.record_run(project, result)
    pool.submit(execute, current_store, project, result)
    return result


def execute(current_store, project, result, optimize=False):
    try:
        result = {**result, 'state': 'RUNNING'}
        current_store.record_run(project, result)
        runner = optimize_project if optimize else analyze
        result = runner(project, current_store.root / project['id'] / 'runs' / result['id'], result['id'])
    except Exception as exc:
        result = {**result, 'state': 'FAILED', 'error': str(exc)}
    current_store.record_run(project, result)


@router.post('/{pid}/optimize', status_code=202)
def optimize(pid: str, payload: CommitImport):
    project = get_project(pid)
    if project['revision'] != payload.revision:
        raise HTTPException(409, 'Reload the current revision.')
    if not validate_project(pid)['valid']:
        raise HTTPException(422, 'Resolve model errors before optimization.')
    if not project['document'].get('catalog'):
        raise HTTPException(422, 'Enter an internal-diameter search catalog in Operations first.')
    result = dict(id=uuid4().hex, project_id=pid, revision=project['revision'], state='QUEUED', candidate=True)
    current_store = store()
    current_store.record_run(project, result)
    pool.submit(execute, current_store, project, result, True)
    return result


@router.post('/{pid}/runs/{rid}/accept')
def accept_candidate(pid: str, rid: str, payload: CommitImport):
    result = get_run(pid, rid)
    if not result.get('candidate') or result.get('state') != 'COMPLETE' or result.get('status') != 'PASS':
        raise HTTPException(422, 'Only a completed feasible candidate can be applied.')
    if result['revision'] != payload.revision:
        raise HTTPException(409, 'Proposal belongs to a different revision.')
    return save_project(pid, SaveProject(revision=payload.revision, document=result['proposal']))


@router.get('/{pid}/runs/{rid}')
def get_run(pid: str, rid: str):
    try:
        return store().run(pid, rid)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get('/{pid}/runs/{rid}/artifacts/{filename}')
def download(pid: str, rid: str, filename: str):
    result = get_run(pid, rid)
    if result['state'] != 'COMPLETE' or filename not in result['artifacts']:
        raise HTTPException(404, 'Artifact not found')
    return FileResponse(store().root / pid / 'runs' / rid / filename, filename=filename)
