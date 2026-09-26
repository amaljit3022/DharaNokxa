from __future__ import annotations

import json
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
from pyproj import Transformer


def safe_table(rows):
    frame = pd.DataFrame(rows)
    return frame.map(lambda value: "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@')) else value)


def export_evidence(project, result, root):
    doc = project['document']
    nodes = {n['name']: n for n in doc['model']['nodes']}
    features = []
    transform = Transformer.from_crs(doc['crs'], 4326, always_xy=True).transform if doc.get('crs') else None
    def point(value):
        return list(transform(*value)) if transform else value
    for n in nodes.values():
        coords = n.get('coordinates')
        if coords:
            features.append(dict(type='Feature', properties=dict(id=n['name'], type=n['node_type']),
                                 geometry=dict(type='Point', coordinates=point(coords))))
    for link in doc['model']['links']:
        a, b = nodes[link['start_node_name']].get('coordinates'), nodes[link['end_node_name']].get('coordinates')
        if a and b:
            features.append(dict(type='Feature', properties=dict(id=link['name'], type=link['link_type'],
                start_node=link['start_node_name'], end_node=link['end_node_name']),
                geometry=dict(type='LineString', coordinates=[point(p) for p in [a, *link.get('vertices', []), b]])))
    geometry_file = 'network.geojson' if transform else 'schematic_geometry.json'
    geometry = dict(type='FeatureCollection', features=features)
    if not transform:
        geometry['coordinate_system'] = 'SCHEMATIC_NOT_GEOGRAPHIC'
    (root / geometry_file).write_text(json.dumps(geometry), encoding='utf-8')
    with pd.ExcelWriter(root / 'hydraulic_results.xlsx', engine='openpyxl') as writer:
        for i, scenario in enumerate(result['scenarios']):
            safe_table(scenario['nodes']).to_excel(writer, sheet_name=f'{i+1}_nodes', index=False)
            safe_table(scenario['links']).to_excel(writer, sheet_name=f'{i+1}_links', index=False)
            safe_table(scenario['violations']).to_excel(writer, sheet_name=f'{i+1}_issues', index=False)
    with PdfPages(root / 'design_report.pdf') as pdf:
        fig = plt.figure(figsize=(8.27, 11.69))
        lines = [project['name'], f"Revision {project['revision']} | Hydraulic status: {result['status']}",
            f"Engine: {result['engine']} | WNTR: {result['wntr_version']}",
            f"Input SHA-256: {project['hash']}", '',
            'Model criteria and construction/approval are separate decisions.',
            'Construction: NOT_REVIEWED | Engineer approval: AWAITING_REVIEW', '', 'Design criteria (project assumptions):']
        lines.extend(f'{key}: {value}' for key, value in doc['criteria'].items())
        lines += ['', 'Scenario results (all reported times):']
        for s in result['scenarios']:
            lines.append(f"{s['scenario']} / {s['mode']}: {s['status']}; {len(s['violations'])} violations, {len(s['warnings'])} warnings")
        lines += ['', 'See Excel/CSV tables and EPANET reports for all assets and times.',
            'Coordinates are schematic unless the project declares a CRS.',
            'Flow signs follow each link start/end orientation. Bends are vertices.',
            'Quality: ' + result.get('quality_units', 'not analyzed')]
        wrapped = '\n'.join(textwrap.fill(str(line), 88) if line else '' for line in lines)
        fig.text(.08, .94, wrapped, va='top', fontsize=10, linespacing=1.6)
        pdf.savefig(fig); plt.close(fig)
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        for link in doc['model']['links']:
            a, b = nodes[link['start_node_name']].get('coordinates'), nodes[link['end_node_name']].get('coordinates')
            if a and b:
                coordinates = [a, *link.get('vertices', []), b]
                ax.plot([p[0] for p in coordinates], [p[1] for p in coordinates], color='#087d83', linewidth=1.5)
        for n in nodes.values():
            if n.get('coordinates'):
                x, y = n['coordinates']
                ax.scatter(x, y, marker='o' if n['node_type'] == 'Junction' else 's', color='#17324d', s=18)
                if len(nodes) < 100:
                    ax.annotate(n['name'], (x, y), xytext=(5, 5), textcoords='offset points', fontsize=7)
        ax.set_aspect('equal', adjustable='datalim')
        ax.set_title(f"{project['name']} | {doc.get('crs') or 'Schematic coordinates'}")
        fig.tight_layout(); pdf.savefig(fig); fig.savefig(root / 'network.png', dpi=140); plt.close(fig)
    return [geometry_file, 'hydraulic_results.xlsx', 'design_report.pdf', 'network.png']
