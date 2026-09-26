"""Staged file ingestion: never commit an upload directly into a project."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path, PurePosixPath

import geopandas as gpd
import pandas as pd
import wntr

from .project_validation import validate_document

MAX_UPLOAD = 20 * 1024 * 1024
MAX_EXPANDED = 100 * 1024 * 1024
TEMPLATES = {
    'junctions': 'name,x,y,elevation_m,demand_lps,pattern\n',
    'reservoirs': 'name,x,y,head_m,pattern\n',
    'tanks': 'name,x,y,elevation_m,initial_level_m,min_level_m,max_level_m,diameter_m\n',
    'pipes': 'name,from_node,to_node,length_m,diameter_mm,roughness,status\n',
    'households': 'household_id,longitude,latitude,population,node_id,demand_lps\n',
}


def inspect_upload(content: bytes, filename: str, role: str, document: dict, mapping=None, crs=None, layer=None, corrections=None):
    if len(content) > MAX_UPLOAD:
        raise ValueError('Upload exceeds 20 MB.')
    suffix = Path(filename).suffix.lower()
    mapping = mapping or {}
    candidate = deepcopy(document)
    notes, rows, columns = [], [], []
    if suffix == '.inp':
        text = content.decode('utf-8-sig', errors='strict')
        # EPANET input is data, but file/path options must not access local files.
        section = ''
        sanitized = []
        for line in text.splitlines():
            stripped = line.split(';', 1)[0].strip()
            if stripped.startswith('['):
                section = stripped.upper()
            tokens = stripped.upper().split()
            if (section == '[OPTIONS]' and tokens and tokens[0] in {'HYDRAULICS', 'MAP'}) or (
                section == '[REPORT]' and tokens and tokens[0] == 'FILE') or section == '[BACKDROP]':
                if stripped:
                    notes.append('External file/backdrop directive excluded; original upload retained.')
                continue
            sanitized.append(line)
        with tempfile.TemporaryDirectory(prefix='dn-import-') as tmp:
            path = Path(tmp) / 'network.inp'
            path.write_text('\n'.join(sanitized), encoding='utf-8')
            model = wntr.network.WaterNetworkModel(str(path))
            candidate['model'] = model.to_dict()
            candidate['model']['name'] = Path(filename).name
        candidate['crs'] = crs or None
        notes.append('Replaces the hydraulic model. INP coordinates are schematic unless a CRS is specified. Review supported settings before committing.')
        rows = candidate['model']['nodes'][:100]
        columns = ['name', 'node_type', 'elevation', 'base_head']
    elif suffix in {'.csv', '.xlsx'}:
        if role not in TEMPLATES:
            raise ValueError('Choose a supported table role: ' + ', '.join(TEMPLATES))
        if suffix == '.xlsx':
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > MAX_EXPANDED:
                    raise ValueError('Workbook expands beyond 100 MB.')
            frame = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
            rows = frame.to_dict('records')
        else:
            rows = list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
        if len(rows) > 50000:
            raise ValueError('Tables are limited to 50,000 rows per upload.')
        columns = list(rows[0]) if rows else []
        for index, corrected in (corrections or {}).items():
            index = int(index)
            if index < 0 or index >= len(rows) or not isinstance(corrected, dict) or set(corrected) - set(columns):
                raise ValueError('Invalid row correction.')
            rows[index].update(corrected)
        errors = []
        normalized = []
        for index, original in enumerate(rows):
            row = {key: original.get(mapping.get(key, key), '') for key in TEMPLATES[role].strip().split(',')}
            try:
                def number(key, optional=False):
                    val = row.get(key)
                    if optional and (val is None or str(val).strip() == ''):
                        return None
                    value = float(val)
                    if not math.isfinite(value):
                        raise ValueError(f'{key} must be finite')
                    return value
                coords = [number('x', True), number('y', True)]
                name = str(row.get('name', '')).strip()
                if role == 'junctions':
                    normalized.append(dict(name=name, node_type='Junction', coordinates=coords,
                        elevation=number('elevation_m'), demand_timeseries_list=[dict(base_val=number('demand_lps') / 1000,
                        pattern_name=row.get('pattern') or None, category=None)]))
                elif role == 'reservoirs':
                    normalized.append(dict(name=name, node_type='Reservoir', coordinates=coords,
                        base_head=number('head_m'), head_pattern_name=row.get('pattern') or None))
                elif role == 'tanks':
                    normalized.append(dict(name=name, node_type='Tank', coordinates=coords,
                        elevation=number('elevation_m'), init_level=number('initial_level_m'),
                        min_level=number('min_level_m'), max_level=number('max_level_m'), diameter=number('diameter_m')))
                elif role == 'pipes':
                    normalized.append(dict(name=name, link_type='Pipe', start_node_name=row['from_node'],
                        end_node_name=row['to_node'], length=number('length_m'), diameter=number('diameter_mm') / 1000,
                        roughness=number('roughness'), initial_status=row.get('status') or 'Open', minor_loss=0, vertices=[]))
                else:
                    normalized.append(dict(type='Feature', properties={**row, 'population': number('population', True),
                        'demand_lps': number('demand_lps', True)}, geometry=dict(type='Point',
                        coordinates=[number('longitude'), number('latitude')])))
            except (ValueError, TypeError) as exc:
                errors.append(dict(rule='IMPORT_ROW', asset=f'Row {index+2}', severity='error', message=f'Missing or invalid number: {exc}'))
        if role == 'households':
            candidate['layers'].append(dict(name=filename, role=role, crs='EPSG:4326',
                data=dict(type='FeatureCollection', features=normalized)))
            notes.append('Households retained as field evidence; demands are not automatically added to imported junction demands.')
        else:
            for asset in normalized:
                if asset.get('coordinates') and None in asset['coordinates']:
                    asset.pop('coordinates')
            candidate['model']['links' if role == 'pipes' else 'nodes'].extend(normalized)
            if crs:
                if candidate.get('crs') and candidate['crs'] != crs:
                    raise ValueError('Table CRS differs from project CRS. Transform coordinates before adding assets.')
                candidate['crs'] = crs
        if errors:
            return dict(document=candidate, rows=rows[:100], columns=columns, issues=errors, notes=notes, count=len(rows))
    elif suffix in {'.geojson', '.json', '.gpkg', '.zip'}:
        with tempfile.TemporaryDirectory(prefix='dn-gis-') as tmp:
            path = Path(tmp) / ('upload' + suffix)
            path.write_bytes(content)
            if suffix == '.zip':
                with zipfile.ZipFile(path) as archive:
                    members = archive.infolist()
                    if len(members) > 1000 or sum(i.file_size for i in members) > MAX_EXPANDED:
                        raise ValueError('Archive is too large after decompression.')
                    for item in members:
                        member = PurePosixPath(item.filename.replace('\\', '/'))
                        if member.is_absolute() or '..' in member.parts or ':' in item.filename:
                            raise ValueError('Unsafe archive path.')
                    archive.extractall(tmp)
                shapes = list(Path(tmp).rglob('*.shp'))
                if len(shapes) != 1:
                    raise ValueError('Upload a ZIP with exactly one Shapefile layer.')
                path = shapes[0]
                if not all(path.with_suffix(ext).exists() for ext in ['.shx', '.dbf']):
                    raise ValueError('Shapefile requires SHP, SHX and DBF files.')
            if suffix == '.gpkg':
                import fiona
                layers = fiona.listlayers(path)
                if not layer and len(layers) > 1:
                    raise ValueError('Specify a layer name: ' + ', '.join(layers))
            frame = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
            if len(frame) > 50000:
                raise ValueError('GIS layers are limited to 50,000 features.')
            if frame.crs is None:
                if not crs:
                    raise ValueError('CRS is missing. Enter the source CRS; it will not be guessed.')
                frame = frame.set_crs(crs)
            native = str(frame.crs)
            frame = frame.to_crs(4326)
            if frame.geometry.is_empty.any() or frame.geometry.isna().any() or not frame.geometry.is_valid.all():
                raise ValueError('Layer contains missing, empty or invalid geometry. Correct it before import.')
            geo = json.loads(frame.to_json())
            candidate['layers'].append(dict(name=filename, role=role, crs='EPSG:4326', source_crs=native, data=geo))
            rows = [f['properties'] for f in geo['features'][:100]]
            columns = list(rows[0]) if rows else []
            notes.append('GIS layer is reference geometry. It does not silently create hydraulic nodes or connections.')
    else:
        raise ValueError('Supported uploads: INP, CSV, XLSX, GeoJSON, GeoPackage, zipped Shapefile.')
    candidate['provenance'].append(dict(filename=Path(filename).name, sha256=hashlib.sha256(content).hexdigest(), role=role,
                                       column_mapping=mapping, row_corrections=corrections or {}))
    return dict(document=candidate, rows=rows[:100], columns=columns, issues=validate_document(candidate),
                notes=list(dict.fromkeys(notes)), count=len(rows))
