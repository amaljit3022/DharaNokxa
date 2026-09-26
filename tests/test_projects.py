from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest
import wntr
from fastapi.testclient import TestClient

from api.main import app
from dharanokxa.projects import ProjectStore, empty_document, executable_model
from dharanokxa.project_imports import inspect_upload
from dharanokxa.project_analysis import analyze
from dharanokxa.project_exports import safe_table
from dharanokxa.project_scenarios import scenario_document
from dharanokxa.project_geometry import openstreetmap_reference
from dharanokxa.project_validation import validate_document


def network():
    doc = empty_document()
    wn = wntr.network.WaterNetworkModel()
    wn.options.hydraulic.inpfile_units = 'LPS'
    wn.options.hydraulic.required_pressure = 8
    wn.add_reservoir('R', base_head=35, coordinates=(0, 100))
    wn.add_junction('J', base_demand=.001, elevation=10, coordinates=(100, 0))
    wn.add_pipe('P', 'R', 'J', length=150, diameter=.1, roughness=130)
    wn.get_link('P').vertices = [(0, 0)]
    doc['model'] = wn.to_dict()
    return doc


def test_revisions_persist_and_reject_lost_updates(tmp_path):
    first = ProjectStore(tmp_path)
    project = first.create('Field scheme')
    first.save(project['id'], 1, network())
    second = ProjectStore(tmp_path)
    assert second.get(project['id'])['revision'] == 2
    assert second.get(project['id'], 1)['document']['model']['nodes'] == []
    with pytest.raises(ValueError, match='changed'):
        first.save(project['id'], 1, network())


def test_vertex_roundtrip_does_not_add_junctions(tmp_path):
    doc = network()
    path = tmp_path / 'source.inp'
    wntr.network.write_inpfile(executable_model(doc), str(path), units='LPS', version=2.2)
    preview = inspect_upload(path.read_bytes(), 'source.inp', 'network', empty_document())
    wn = executable_model(preview['document'])
    assert wn.num_nodes == 2
    assert wn.num_links == 1
    assert wn.get_link('P').vertices == [(0.0, 0.0)]
    assert wn.get_node('J').base_demand == pytest.approx(.001)


def test_table_mapping_and_bad_rows_are_not_silently_dropped():
    content = b'code,x,y,z,q\nJ,0,0,10,2\n'
    result = inspect_upload(content, 'survey.csv', 'junctions', empty_document(),
                            {'name': 'code', 'elevation_m': 'z', 'demand_lps': 'q'})
    assert result['document']['model']['nodes'][0]['demand_timeseries_list'][0]['base_val'] == .002
    invalid = inspect_upload(content.replace(b',10,', b',bad,'), 'survey.csv', 'junctions', empty_document(),
                             {'name': 'code', 'elevation_m': 'z', 'demand_lps': 'q'})
    assert invalid['issues'][0]['rule'] == 'IMPORT_ROW'


def test_archive_traversal_rejected():
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        archive.writestr('../escaped.txt', 'not allowed')
    with pytest.raises(ValueError, match='Unsafe'):
        inspect_upload(data.getvalue(), 'roads.zip', 'roads', empty_document())


def test_two_run_limit_does_not_limit_junction_degree():
    doc = network()
    for i in range(3):
        node = deepcopy(doc['model']['nodes'][1]); node['name'] = f'J{i}'
        doc['model']['nodes'].append(node)
        link = deepcopy(doc['model']['links'][0]); link.update(name=f'P{i}', start_node_name='J', end_node_name=f'J{i}')
        doc['model']['links'].append(link)
    assert not [i for i in validate_document(doc) if i['severity'] == 'error']
    for i, link in enumerate(doc['model']['links']):
        link.update(road_id='ROAD', run_id=f'RUN{i}')
    assert any(i['rule'] == 'ROAD_RUN_LIMIT' for i in validate_document(doc))


def test_analysis_exports_signed_flows_and_all_times(tmp_path):
    repository = ProjectStore(tmp_path / 'projects')
    project = repository.create('Test')
    doc = network()
    doc['model']['options']['time'].update(duration=7200, report_timestep=3600)
    project = repository.save(project['id'], 1, doc)
    result = analyze(project, tmp_path / 'run', 'run1')
    assert result['state'] == 'COMPLETE'
    assert result['status'] == 'PASS'
    assert result['scenarios'][0]['times'] == [0, 3600, 7200]
    assert result['scenarios'][0]['links'][0]['flow_lps'] == pytest.approx(1, rel=.001)
    assert (tmp_path / 'run' / 'network.inp').exists()
    for artifact in ['hydraulic_results.xlsx', 'design_report.pdf', 'network.png', 'schematic_geometry.json']:
        assert (tmp_path / 'run' / artifact).exists()
    doc['model']['nodes'][0]['base_head'] = 12
    project = repository.save(project['id'], 2, doc)
    shortage = analyze(project, tmp_path / 'shortage', 'run2')
    assert shortage['status'] == 'FAIL'
    assert any(v['rule'] == 'DEMAND_SHORTFALL' for v in shortage['scenarios'][1]['violations'])


def test_scenarios_are_explicit_and_cannot_override_check_valves():
    doc = network()
    doc['model']['links'][0]['check_valve'] = True
    with pytest.raises(ValueError, match='check-valve'):
        scenario_document(doc, {'link_statuses': {'P': 'Closed'}})
    changed = scenario_document(network(), {'demand_multiplier': 1.25})
    assert changed['model']['options']['hydraulic']['demand_multiplier'] == 1.25
    assert network()['model']['options']['hydraulic']['demand_multiplier'] == 1


def test_export_tables_escape_spreadsheet_formulas():
    value = safe_table([{'asset': '=unsafe', 'note': '+unsafe', 'number': 2}]).iloc[0]
    assert value['asset'] == "'=unsafe"
    assert value['note'] == "'+unsafe"
    assert value['number'] == 2


def test_openstreetmap_reference_requires_declared_crs_and_uses_project_extent():
    with pytest.raises(ValueError, match='CRS'):
        openstreetmap_reference(network())
    doc = network()
    doc['crs'] = 'EPSG:4326'
    reference = openstreetmap_reference(doc)
    assert reference['provider'] == 'OpenStreetMap contributors'
    assert 'openstreetmap.org' in reference['url']
    assert reference['bounds']['east'] == 100


def test_api_staging_and_conflicts(tmp_path, monkeypatch):
    monkeypatch.setenv('DHARANOKXA_PROJECTS_DIR', str(tmp_path))
    client = TestClient(app)
    p = client.post('/projects', json={'name': 'Site'}).json()
    base = '/projects/' + p['id']
    saved = client.put(base, json={'revision': 1, 'document': network()})
    assert saved.status_code == 200
    assert client.put(base, json={'revision': 1, 'document': network()}).status_code == 409
    assert client.post(base + '/validate').json()['valid']
    preview = client.post(base + '/imports', data={'role': 'junctions'},
        files={'file': ('nodes.csv', b'name,x,y,elevation_m,demand_lps,pattern\nNEW,2,2,15,0,\n', 'text/csv')})
    assert preview.status_code == 201, preview.text
    assert len(client.get(base).json()['document']['model']['nodes']) == 2
    response = client.post(base + '/imports/' + preview.json()['id'] + '/commit', json={'revision': 2})
    assert response.status_code == 200, response.text
    assert len(response.json()['document']['model']['nodes']) == 3
