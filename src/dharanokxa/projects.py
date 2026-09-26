"""Persistent, revisioned engineering projects. WNTR dictionaries use SI units.

Drafts deliberately retain incomplete inputs. Only validation/analysis constructs
an executable WNTR model, so missing field data never becomes synthetic data.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import wntr


def encode(value):
    return json.dumps(value, allow_nan=False, ensure_ascii=False)


def empty_document():
    model = wntr.network.WaterNetworkModel().to_dict()
    model['options']['hydraulic'].update(inpfile_units='LPS', required_pressure=8.0)
    return {
        'model': model, 'crs': None, 'layers': [], 'provenance': [], 'scenarios': [], 'catalog': [],
        'criteria': {'minimum_pressure_m': 7.0, 'maximum_pressure_m': 60.0,
                     'maximum_velocity_mps': 2.0, 'maximum_headloss_m_per_km': 15.0},
    }


class ProjectStore:
    def __init__(self, root: Path):
        self.root = root

    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.root / 'projects.sqlite3', timeout=30)
        db.row_factory = sqlite3.Row
        db.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT, revision INTEGER);
        CREATE TABLE IF NOT EXISTS revisions(project_id TEXT, revision INTEGER, created TEXT,
            document TEXT, hash TEXT, PRIMARY KEY(project_id, revision));
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, project_id TEXT, revision INTEGER,
            created TEXT, result TEXT);
        ''')
        return db

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY rowid DESC')]

    def create(self, name):
        pid = uuid4().hex
        document = encode(empty_document())
        with self.connect() as db:
            db.execute('INSERT INTO projects VALUES(?,?,?)', (pid, name, 1))
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)',
                       (pid, 1, datetime.now(timezone.utc).isoformat(), document, hashlib.sha256(document.encode()).hexdigest()))
        return self.get(pid)

    def get(self, pid, revision=None):
        with self.connect() as db:
            project = db.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
            if project is None:
                raise KeyError('Project not found')
            row = db.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?',
                             (pid, revision or project['revision'])).fetchone()
            if row is None:
                raise KeyError('Revision not found')
            return {'id': pid, 'name': project['name'], 'revision': row['revision'],
                    'created': row['created'], 'hash': row['hash'], 'document': json.loads(row['document'])}

    def save(self, pid, expected_revision, document):
        payload = encode(document)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute('UPDATE projects SET revision=revision+1 WHERE id=? AND revision=?',
                                 (pid, expected_revision)).rowcount
            if not changed:
                raise ValueError('This project changed. Reload before saving to avoid overwriting another revision.')
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?)', (pid, expected_revision + 1,
                       datetime.now(timezone.utc).isoformat(), payload, hashlib.sha256(payload.encode()).hexdigest()))
        return self.get(pid)

    def record_run(self, project, result):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)', (result['id'], project['id'], project['revision'],
                       datetime.now(timezone.utc).isoformat(), encode(result)))

    def runs(self, pid):
        self.get(pid)
        with self.connect() as db:
            return [json.loads(row['result']) for row in db.execute(
                'SELECT result FROM runs WHERE project_id=? ORDER BY rowid DESC', (pid,))]

    def run(self, pid, rid):
        with self.connect() as db:
            row = db.execute('SELECT result FROM runs WHERE project_id=? AND id=?', (pid, rid)).fetchone()
            if not row:
                raise KeyError('Run not found')
            return json.loads(row['result'])

    def recover(self):
        with self.connect() as db:
            for row in db.execute('SELECT id,result FROM runs').fetchall():
                result = json.loads(row['result'])
                if result.get('state') in {'QUEUED', 'RUNNING'}:
                    result.update(state='FAILED', error='Server restarted during analysis. Run this revision again.')
                    db.execute('UPDATE runs SET result=? WHERE id=?', (encode(result), row['id']))


def executable_model(document):
    data = deepcopy(document['model'])
    # Uploaded models must not read/write user-selected paths or reuse external hydraulics.
    data['options']['hydraulic'].update(hydraulics=None, hydraulics_filename=None)
    data['options']['report']['report_filename'] = None
    data['options']['graphics'].update(image_filename=None, map_filename=None)
    return wntr.network.from_dict(data)
