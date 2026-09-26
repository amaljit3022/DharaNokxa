from __future__ import annotations

import json
import warnings
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import wntr

from .projects import encode, executable_model
from .project_validation import validate_document
from .project_scenarios import scenario_document
from .project_exports import export_evidence, safe_table


def analyze(project, root: Path, run_id: str, include_report=True):
    document = project['document']
    issues = validate_document(document)
    if any(i['severity'] == 'error' for i in issues):
        raise ValueError('Resolve model errors before analysis.')
    root.mkdir(parents=True, exist_ok=True)
    (root / 'input.json').write_text(encode(project), encoding='utf-8')
    model = executable_model(document)
    wntr.network.write_inpfile(model, str(root / 'network.inp'), version=2.2)
    results = []
    criteria = document['criteria']
    scenarios = [{'name': 'Baseline'}, *document.get('scenarios', [])]
    if len(scenarios) > 8:
        raise ValueError('Interactive analysis supports at most eight scenarios including baseline.')
    extra_artifacts = []
    for scenario_index, scenario, mode in [(i, s, m) for i, s in enumerate(scenarios) for m in ['DDA', 'PDA']]:
        scenario_doc = scenario_document(document, scenario)
        wn = executable_model(scenario_doc)
        prefix = mode.lower() if scenario_index == 0 else f's{scenario_index}_{mode.lower()}'
        wn.options.hydraulic.demand_model = mode
        # Preserve every configured pressure threshold; invalid PDA settings are not repaired.
        if wn.options.hydraulic.required_pressure - wn.options.hydraulic.minimum_pressure < .1:
            raise ValueError('Set required pressure at least 0.1 m above minimum pressure before comparing DDA/PDA.')
        wn.options.report.status = 'YES'
        wn.options.time.statistic = 'NONE'
        if wn.options.time.duration > 31 * 86400:
            raise ValueError('Interactive runs are limited to 31 days.')
        step = wn.options.time.report_timestep
        if not isinstance(step, (int, float)) or step <= 0:
            raise ValueError('Use a positive numeric reporting time step.')
        if (wn.options.time.duration / step + 1) * (wn.num_nodes + wn.num_links) > 2000000:
            raise ValueError('Reduce duration or increase report step; interactive runs are limited to 2 million asset/time rows.')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            sim = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(root / prefix), version=2.2, convergence_error=True)
        pressure, head = sim.node['pressure'], sim.node['head']
        demand, flow, velocity = sim.node['demand'], sim.link['flowrate'], sim.link['velocity']
        for frame in [pressure, head, demand, flow, velocity]:
            if not np.isfinite(frame.to_numpy()).all():
                raise ValueError('EPANET returned non-finite values; results cannot be accepted.')
        expected = wntr.metrics.expected_demand(wn).reindex(demand.index)
        nodes, links, failures = [], [], []
        def violation(rule, asset, value, limit, at):
            failures.append(dict(rule=rule, asset=asset, value=float(value), limit=float(limit), time_s=int(at)))
        for name, node in wn.nodes():
            for time in pressure.index:
                row = dict(id=name, type=node.node_type, time_s=int(time), head_m=float(head.loc[time, name]),
                    pressure_m=float(pressure.loc[time, name]), delivered_lps=float(demand.loc[time, name]) * 1000)
                if node.node_type == 'Junction':
                    requested = float(expected.loc[time, name]) * 1000
                    row['requested_lps'] = requested
                    if requested > 0 and row['pressure_m'] <= criteria['minimum_pressure_m']:
                        violation('MIN_PRESSURE', name, row['pressure_m'], criteria['minimum_pressure_m'], time)
                    if row['pressure_m'] > criteria['maximum_pressure_m']:
                        violation('MAX_PRESSURE', name, row['pressure_m'], criteria['maximum_pressure_m'], time)
                    if mode == 'PDA' and requested > 0 and row['delivered_lps'] < requested * .999:
                        violation('DEMAND_SHORTFALL', name, row['delivered_lps'], requested, time)
                if node.node_type == 'Tank':
                    row['level_m'] = row['head_m'] - node.elevation
                if 'quality' in sim.node:
                    value = float(sim.node['quality'].loc[time, name])
                    parameter = wn.options.quality.parameter
                    if parameter == 'AGE':
                        value /= 3600
                    elif parameter == 'CHEMICAL':
                        value *= 1e6 if wn.options.quality.inpfile_units.lower() == 'ug/l' else 1000
                    row['quality'] = value
                nodes.append(row)
        for name, link in wn.links():
            for time in flow.index:
                delta = float(head.loc[time, link.start_node_name] - head.loc[time, link.end_node_name])
                row = dict(id=name, type=link.link_type, time_s=int(time), flow_lps=float(flow.loc[time, name]) * 1000,
                    velocity_mps=abs(float(velocity.loc[time, name])), head_difference_m=delta)
                if 'status' in sim.link:
                    row['status'] = int(sim.link['status'].loc[time, name])
                if link.link_type == 'Pipe':
                    row['headloss_m_per_km'] = abs(delta) * 1000 / link.length
                    if row['velocity_mps'] > criteria['maximum_velocity_mps']:
                        violation('MAX_VELOCITY', name, row['velocity_mps'], criteria['maximum_velocity_mps'], time)
                    if row['headloss_m_per_km'] > criteria['maximum_headloss_m_per_km']:
                        violation('MAX_HEADLOSS', name, row['headloss_m_per_km'], criteria['maximum_headloss_m_per_km'], time)
                links.append(row)
        report = (root / (prefix + '.rpt')).read_text(errors='replace')
        messages = list(dict.fromkeys([str(w.message) for w in caught] + [line.strip() for line in report.splitlines() if 'WARNING' in line.upper()]))
        safe_table(nodes).to_csv(root / f'{prefix}_nodes.csv', index=False)
        safe_table(links).to_csv(root / f'{prefix}_links.csv', index=False)
        if scenario_index:
            extra_artifacts.extend([f'{prefix}_nodes.csv', f'{prefix}_links.csv', f'{prefix}.rpt'])
        results.append(dict(mode=mode, scenario=scenario['name'], nodes=nodes, links=links, violations=failures, warnings=messages,
            status='FAIL' if failures else 'REVIEW' if messages else 'PASS', times=[int(t) for t in pressure.index]))
    result = dict(id=run_id, state='COMPLETE', project_id=project['id'], revision=project['revision'],
        input_hash=project['hash'], engine='EPANET 2.2', wntr_version=wntr.__version__, scenarios=results,
        issues=issues, construction_status='NOT_REVIEWED', approval_status='AWAITING_REVIEW',
        status='FAIL' if any(r['status'] == 'FAIL' for r in results) else 'REVIEW' if any(r['status'] == 'REVIEW' for r in results) else 'PASS',
        artifacts=['network.inp', 'input.json', 'dda_nodes.csv', 'dda_links.csv', 'pda_nodes.csv', 'pda_links.csv', 'dda.rpt', 'pda.rpt', 'results.json', *extra_artifacts])
    parameter = model.options.quality.parameter
    result['quality_units'] = ('hours' if parameter == 'AGE' else 'percent' if parameter == 'TRACE' else
                               model.options.quality.inpfile_units if parameter == 'CHEMICAL' else 'not analyzed')
    if include_report:
        result['artifacts'].extend(export_evidence(project, result, root))
    (root / 'results.json').write_text(encode(result), encoding='utf-8')
    return result
