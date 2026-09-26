from copy import deepcopy


def scenario_document(document, scenario):
    doc = deepcopy(document)
    hydraulic = doc['model']['options']['hydraulic']
    if 'demand_multiplier' in scenario:
        value = float(scenario['demand_multiplier'])
        if value < 0:
            raise ValueError('Scenario demand multiplier must be non-negative.')
        hydraulic['demand_multiplier'] = value
    nodes = {n['name']: n for n in doc['model']['nodes']}
    for name, level in scenario.get('tank_levels', {}).items():
        if name not in nodes or nodes[name]['node_type'] != 'Tank':
            raise ValueError(f'Scenario references unknown tank {name}.')
        if not nodes[name]['min_level'] <= float(level) <= nodes[name]['max_level']:
            raise ValueError(f'Scenario tank {name} level is outside its bounds.')
        nodes[name]['init_level'] = float(level)
    links = {p['name']: p for p in doc['model']['links']}
    for name, status in scenario.get('link_statuses', {}).items():
        if name not in links or status not in {'Open', 'Closed', 'Active'}:
            raise ValueError(f'Invalid scenario link/status: {name}.')
        if links[name].get('check_valve'):
            raise ValueError('Cannot override check-valve status.')
        links[name]['initial_status'] = status
    return doc
