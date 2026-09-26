from __future__ import annotations

import math
from collections import Counter, defaultdict

import networkx as nx

from .projects import executable_model


def validate_document(document):
    issues = []

    def issue(rule, asset, message, severity='error'):
        issues.append(dict(rule=rule, asset=asset, message=message, severity=severity))

    data = document.get('model', {})
    nodes, links = data.get('nodes', []), data.get('links', [])
    ids = {n.get('name') for n in nodes if isinstance(n.get('name'), str)}
    for kind, objects in [('node', nodes), ('link', links)]:
        for name, count in Counter(o.get('name') for o in objects).items():
            if not isinstance(name, str) or not name or any(c.isspace() for c in name) or len(name) > 31:
                issue('ID', name, f'{kind.title()} IDs must be nonempty, without whitespace and at most 31 characters.')
            if count > 1:
                issue('DUPLICATE_ID', name, f'Duplicate {kind} ID; IDs are unique across all {kind} types.')

    def numeric(obj, field, minimum=None, positive=False):
        value = obj.get(field)
        try:
            number = float(value)
            valid = math.isfinite(number) and (minimum is None or number >= minimum) and (not positive or number > 0)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            issue('VALUE', obj.get('name'), f'{field} must be a finite number' + (' greater than zero.' if positive else f' >= {minimum}.' if minimum is not None else '.'))
        return valid

    graph = nx.Graph()
    graph.add_nodes_from(ids)
    physical = nx.Graph()
    physical.add_nodes_from(ids)
    boundaries = []
    if not any(n.get('node_type') == 'Junction' for n in nodes):
        issue('JUNCTION_REQUIRED', None, 'Add at least one junction.')
    for n in nodes:
        kind = n.get('node_type')
        if kind not in {'Junction', 'Reservoir', 'Tank'}:
            issue('NODE_TYPE', n.get('name'), 'Choose Junction, Reservoir or Tank.')
        if kind == 'Reservoir':
            numeric(n, 'base_head')
            boundaries.append(n['name'])
        else:
            numeric(n, 'elevation')
        if kind == 'Tank':
            boundaries.append(n['name'])
            valid = [numeric(n, f, minimum=0) for f in ['min_level', 'init_level', 'max_level']]
            numeric(n, 'diameter', positive=True)
            if all(valid) and not n['min_level'] <= n['init_level'] <= n['max_level']:
                issue('TANK_LEVELS', n['name'], 'Tank levels must satisfy minimum <= initial <= maximum.')
            if all(valid) and n['max_level'] <= n['min_level']:
                issue('TANK_RANGE', n['name'], 'Maximum tank level must exceed minimum level.')
        if kind == 'Junction':
            if 'demand_timeseries_list' not in n and 'base_demand' not in n:
                issue('DEMAND_MISSING', n.get('name'), 'Enter demand explicitly; use zero for a transit junction.')
            for demand in n.get('demand_timeseries_list', []):
                numeric({'name': n['name'], 'base_val': demand.get('base_val')}, 'base_val')
        coords = n.get('coordinates')
        if coords and (len(coords) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in coords)):
            issue('COORDINATES_INVALID', n.get('name'), 'Coordinates must be two finite numbers or omitted.')
        if not coords:
            issue('COORDINATES', n.get('name'), 'No map coordinates; hydraulics can still run.', 'warning')
    if not boundaries:
        issue('SOURCE_REQUIRED', None, 'Add a reservoir or storage tank.')
    for p in links:
        a, b = p.get('start_node_name'), p.get('end_node_name')
        if a not in ids or b not in ids:
            issue('ENDPOINT', p.get('name'), 'Both endpoint IDs must refer to existing nodes.')
        elif a == b:
            issue('SELF_LINK', p['name'], 'A link cannot connect a node to itself.')
        else:
            physical.add_edge(a, b)
            if str(p.get('initial_status', 'Open')).lower() != 'closed':
                graph.add_edge(a, b)
        kind = p.get('link_type')
        if kind not in {'Pipe', 'Pump', 'Valve'}:
            issue('LINK_TYPE', p.get('name'), 'Choose Pipe, Pump or Valve.')
        if kind in {'Pipe', 'Valve'}:
            numeric(p, 'diameter', positive=True)
            numeric({**p, 'minor_loss': p.get('minor_loss', 0)}, 'minor_loss', minimum=0)
        if kind == 'Pipe':
            numeric(p, 'length', positive=True)
            numeric(p, 'roughness', minimum=0 if data.get('options', {}).get('hydraulic', {}).get('headloss') == 'D-W' else None,
                    positive=data.get('options', {}).get('hydraulic', {}).get('headloss') != 'D-W')
        if kind == 'Pump' and not (p.get('pump_curve_name') or p.get('power')):
            issue('PUMP_DATA', p.get('name'), 'Supply a pump curve or power rating.')
        if kind == 'Valve' and p.get('valve_type') in {'PRV', 'PSV', 'FCV'} and (a in boundaries or b in boundaries):
            issue('VALVE_BOUNDARY', p['name'], 'PRV, PSV and FCV require a pipe between the valve and a tank/reservoir.')
        for vertex in p.get('vertices', []):
            if not isinstance(vertex, (list, tuple)) or len(vertex) != 2 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in vertex):
                issue('VERTEX', p.get('name'), 'Each vertex must contain two finite coordinates.')
        if str(p.get('initial_status', 'Open')).upper() not in {'OPEN', 'CLOSED', 'ACTIVE'}:
            issue('STATUS', p.get('name'), 'Choose Open, Closed or (for a valve) Active; check valve is a separate pipe property.')
    valves = [p for p in links if p.get('link_type') == 'Valve']
    for index, a in enumerate(valves):
        for b in valves[index+1:]:
            at, bt = a.get('valve_type'), b.get('valve_type')
            u, v, x, y = a.get('start_node_name'), a.get('end_node_name'), b.get('start_node_name'), b.get('end_node_name')
            illegal = (at == bt == 'PRV' and (v == y or v == x or y == u)) or (at == bt == 'PSV' and (u == x or v == x or y == u))
            illegal |= (at == 'PRV' and bt == 'PSV' and v in {x, y}) or (bt == 'PRV' and at == 'PSV' and y in {u, v})
            if illegal:
                issue('VALVE_CONNECTION', a['name'], f'Unsupported valve arrangement with {b["name"]}.')
    reachable = set()
    for source in boundaries:
        reachable.update(nx.node_connected_component(graph, source))
    for n in nodes:
        if n.get('name') not in ids:
            continue
        if not any(nx.has_path(physical, n['name'], source) for source in boundaries):
            issue('NO_SOURCE_PATH', n['name'], 'No physical path to a tank/reservoir.')
        if n['name'] not in reachable:
            issue('DISCONNECTED', n['name'], 'No initially open path to a tank/reservoir.', 'warning')
        if not any(p.get('start_node_name') == n['name'] or p.get('end_node_name') == n['name'] for p in links):
            issue('ISOLATED', n['name'], 'Node has no incident link.')
    runs = defaultdict(set)
    for p in links:
        if p.get('road_id') and p.get('run_id'):
            runs[p['road_id']].add(p['run_id'])
        if p.get('construction_type') == 'ROAD_BORE' and not p.get('approved_crossing'):
            issue('UNAPPROVED_CROSSING', p['name'], 'Road crossing awaits approval.', 'warning')
    for road, physical_runs in runs.items():
        if len(physical_runs) > 2:
            issue('ROAD_RUN_LIMIT', road, 'Road has more than two longitudinal run IDs.')
    if not document.get('crs'):
        issue('SCHEMATIC', None, 'Coordinates are schematic until a CRS is assigned. Lengths will not be inferred.', 'warning')
    else:
        try:
            from pyproj import CRS
            CRS.from_user_input(document['crs'])
        except Exception:
            issue('CRS', None, 'Spatial reference is not a recognized CRS.')
    for name, value in document.get('criteria', {}).items():
        numeric({'name': 'Design criteria', name: value}, name, minimum=0)
    options = data.get('options', {})
    hydraulic = options.get('hydraulic', {})
    if hydraulic.get('required_pressure', 0) - hydraulic.get('minimum_pressure', 0) < 0.1:
        issue('PDA_LIMITS', None, 'Comparative DDA/PDA runs require required pressure at least 0.1 m above minimum pressure.')
    times = options.get('time', {})
    for key in ['hydraulic_timestep', 'report_timestep', 'pattern_timestep', 'quality_timestep', 'rule_timestep']:
        numeric({'name': 'Time options', key: times.get(key)}, key, positive=True)
    numeric({'name': 'Time options', 'duration': times.get('duration')}, 'duration', minimum=0)
    if options.get('quality', {}).get('parameter', 'NONE') != 'NONE' and not times.get('duration'):
        issue('QUALITY_DURATION', None, 'Water-quality analysis requires a non-zero duration.')
    for curve in data.get('curves', []):
        points = curve.get('points', [])
        if not points or any(len(p) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in points):
            issue('CURVE_DATA', curve.get('name'), 'Curve requires finite X/Y pairs.')
            continue
        if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
            issue('CURVE_X', curve.get('name'), 'Curve X values must increase strictly.')
        if curve.get('curve_type') == 'HEAD' and any(b[1] >= a[1] for a, b in zip(points, points[1:])):
            issue('PUMP_CURVE', curve.get('name'), 'Pump head must decrease with increasing flow.')
    if not any(i['severity'] == 'error' for i in issues):
        try:
            executable_model(document)
        except Exception as exc:
            issue('MODEL_BUILD', None, str(exc))
    return issues
