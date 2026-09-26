"""Explicit geometry actions. Intersecting map lines never imply connectivity."""
from __future__ import annotations

from copy import deepcopy

import geopandas as gpd
from pyproj import CRS, Transformer
from shapely.geometry import LineString, shape


def roadside_candidate(document, layer_index, sides, offset_m, diameter_mm, roughness):
    if sides not in {1, 2} or offset_m <= 0 or diameter_mm <= 0 or roughness <= 0:
        raise ValueError('Choose one/two sides and positive offset, diameter and roughness.')
    doc = deepcopy(document)
    if doc['model']['options']['hydraulic']['headloss'] != 'H-W':
        raise ValueError('Roadside candidate roughness is entered as Hazen-Williams C. Use H-W for candidate generation.')
    layer = doc['layers'][layer_index]
    if layer.get('role') != 'roads':
        raise ValueError('Select a roads layer.')
    frame = gpd.GeoDataFrame.from_features(layer['data']['features'], crs=layer['crs'])
    if frame.empty:
        raise ValueError('Road layer is empty.')
    if any(g.geom_type != 'LineString' for g in frame.geometry):
        raise ValueError('Road generation requires LineString features; split multipart roads first.')
    metric = frame.estimate_utm_crs()
    if metric is None:
        raise ValueError('Cannot determine a metric working CRS for these roads.')
    if doc['model']['nodes'] and not doc.get('crs'):
        raise ValueError('Georeference the existing model before adding GIS roads.')
    target = CRS.from_user_input(doc['crs']) if doc.get('crs') else metric
    doc['crs'] = target.to_string()
    project = Transformer.from_crs(metric, target, always_xy=True)
    frame = frame.to_crs(metric)
    names = {n['name'] for n in doc['model']['nodes']} | {p['name'] for p in doc['model']['links']}
    for index, row in frame.iterrows():
        road = str(row.get('road_id', f'ROAD{index+1}'))
        if not road or len(road) > 18 or any(c.isspace() for c in road):
            raise ValueError('road_id must be nonempty, <=18 characters, without whitespace.')
        coords = list(row.geometry.coords)
        # Stable orientation makes LEFT/RIGHT independent of digitization direction.
        reverse = coords[-1] < coords[0]
        if reverse:
            coords.reverse()
        source = LineString(coords)
        for side, direction in [('L', 1), ('R', -1)][:sides]:
            route = source.offset_curve(offset_m * direction, join_style='mitre', mitre_limit=3)
            if route.geom_type != 'LineString' or route.is_empty or not route.is_simple:
                raise ValueError(f'{road}: offset creates invalid/disconnected geometry; revise road alignment or offset.')
            run = f'{road}_{side}'
            start, end = f'{run}_A', f'{run}_B'
            if any(n in names for n in [run, start, end]):
                raise ValueError(f'{run}: generated IDs already exist. Use distinct road IDs or another draft.')
            names.update([run, start, end])
            points = [list(project.transform(*point[:2])) for point in route.coords]
            elevations = [row.get('start_elevation_m'), row.get('end_elevation_m')]
            if reverse:
                elevations.reverse()
            for name, coord, elevation in [(start, points[0], elevations[0]), (end, points[-1], elevations[1])]:
                import math
                try:
                    elevation = float(elevation) if elevation is not None else None
                except (ValueError, TypeError):
                    elevation = None
                if elevation is not None and not math.isfinite(elevation):
                    elevation = None
                doc['model']['nodes'].append(dict(name=name, node_type='Junction', coordinates=coord,
                    elevation=elevation, demand_timeseries_list=[dict(base_val=0, pattern_name=None, category='Unallocated')],
                    road_id=road, run_id=run, provenance='Road-offset candidate; survey elevation and demand require review'))
            doc['model']['links'].append(dict(name=run, link_type='Pipe', start_node_name=start, end_node_name=end,
                vertices=points[1:-1], length=float(route.length), diameter=diameter_mm / 1000, roughness=roughness,
                minor_loss=0, initial_status='Open', road_id=road, run_id=run, road_side=side,
                locked=False, construction_type='ROADSIDE', length_source='Derived from projected road offset'))
    doc['provenance'].append(dict(action='Roadside candidate', layer=layer['name'], offset_m=offset_m, sides=sides,
        working_crs=metric.to_string(), note='No intersections were automatically joined; elevations/demands require review.'))
    return doc


def join_junctions(document, keep, remove, reason):
    if keep == remove or not reason.strip():
        raise ValueError('Choose two different junctions and document the physical connection.')
    doc = deepcopy(document)
    nodes = {n['name']: n for n in doc['model']['nodes']}
    a, b = nodes[keep], nodes[remove]
    if a.get('node_type') != 'Junction' or b.get('node_type') != 'Junction':
        raise ValueError('Only junctions can be joined; source/storage assets retain their identity.')
    if a.get('locked') or b.get('locked'):
        raise ValueError('A selected junction is locked.')
    if a.get('elevation') != b.get('elevation'):
        raise ValueError('Reconcile junction elevations before joining the same physical connection.')
    if a.get('emitter_coefficient') or b.get('emitter_coefficient'):
        raise ValueError('Junctions with emitters require an explicit hydraulic review before merging.')
    if doc['model'].get('controls') or doc['model'].get('sources'):
        raise ValueError('This model has controls/quality sources. Resolve their node references before merging.')
    for link in doc['model']['links']:
        if {link['start_node_name'], link['end_node_name']} == {keep, remove}:
            raise ValueError('Joining would collapse an existing link. Remove the unnecessary link explicitly first.')
        if remove in {link['start_node_name'], link['end_node_name']} and link.get('locked'):
            raise ValueError('A connected link is locked.')
    a['demand_timeseries_list'] = a.get('demand_timeseries_list', []) + b.get('demand_timeseries_list', [])
    for link in doc['model']['links']:
        for key in ['start_node_name', 'end_node_name']:
            if link[key] == remove:
                link[key] = keep
    doc['model']['nodes'] = [n for n in doc['model']['nodes'] if n['name'] != remove]
    doc['provenance'].append(dict(action='Join physical connection', kept_node=keep, removed_node=remove, reason=reason,
        note='Surviving node coordinates retained; review route and hydraulic lengths.'))
    return doc


def allocate_households(document, layer_index, mode):
    if mode not in {'add', 'replace'}:
        raise ValueError('Choose add or replace demand explicitly.')
    doc = deepcopy(document)
    layer = doc['layers'][layer_index]
    if layer.get('role') != 'households':
        raise ValueError('Select a households layer.')
    allocations = {}
    for index, feature in enumerate(layer['data']['features']):
        props = feature['properties']
        name, demand = props.get('node_id'), props.get('demand_lps')
        if not name or demand is None or float(demand) < 0:
            raise ValueError(f'Household row {index+1} requires node_id and non-negative demand_lps; no population assumptions are applied.')
        allocations[name] = allocations.get(name, 0) + float(demand) / 1000
    junctions = {n['name']: n for n in doc['model']['nodes'] if n['node_type'] == 'Junction'}
    if set(allocations) - set(junctions):
        raise ValueError('Households reference unknown/non-junction nodes: ' + ', '.join(set(allocations) - set(junctions)))
    if layer.get('allocated'):
        raise ValueError('This layer has already been allocated. Import a new revision rather than double counting.')
    for name, value in allocations.items():
        demand = dict(base_val=value, pattern_name=None, category='Field households')
        node = junctions[name]
        node['demand_timeseries_list'] = ([*node.get('demand_timeseries_list', []), demand] if mode == 'add' else [demand])
    layer['allocated'] = True
    doc['provenance'].append(dict(action='Allocate household demands', layer=layer['name'], mode=mode,
        total_lps=sum(allocations.values())*1000))
    return doc
