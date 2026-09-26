"""Bounded diameter search using full EPANET evaluations, including loops.

No graph-path assumption: each permitted change is assessed against every
scenario and demand model. A proposal never mutates the saved project.
"""
from copy import deepcopy
import hashlib
from pathlib import Path

from .project_analysis import analyze
from .projects import encode


def optimize_project(project, root: Path, run_id: str, max_iterations=8):
    doc = deepcopy(project['document'])
    catalog = doc.get('catalog', [])
    diameters = sorted(set(float(row['internal_diameter_mm']) / 1000 for row in catalog))
    if not diameters or any(d <= 0 for d in diameters):
        raise ValueError('Enter a catalog of positive internal_diameter_mm values in Operations first.')
    pipes = [p for p in doc['model']['links'] if p['link_type'] == 'Pipe' and not p.get('locked')]
    if len(pipes) > 80:
        raise ValueError('Lock reviewed assets to leave at most 80 pipes for interactive diameter search.')
    for p in pipes:
        if not any(abs(p['diameter'] - d) < 1e-8 for d in diameters):
            raise ValueError(f'{p["name"]}: current internal diameter must appear in the approved search catalog.')
    history = []
    def evaluate(document, folder, report=False):
        snapshot = {**project, 'document': deepcopy(document), 'hash': hashlib.sha256(encode(document).encode()).hexdigest()}
        return analyze(snapshot, folder, run_id, include_report=report)

    def score(result, document):
        violations = [v for s in result['scenarios'] for v in s['violations']]
        penalty = sum(abs(v['value'] - v['limit']) / max(abs(v['limit']), .001) + 1 for v in violations)
        warning_count = sum(len(s['warnings']) for s in result['scenarios'])
        volume = sum(p['length'] * p['diameter'] ** 2 for p in document['model']['links'] if p['link_type'] == 'Pipe')
        return (len(violations), penalty, warning_count, volume)

    current = evaluate(doc, root / 'baseline')
    baseline_status = current['status']
    current_score = score(current, doc)
    for iteration in range(max_iterations):
        best = None
        for pipe in pipes:
            original = pipe['diameter']
            index = min(range(len(diameters)), key=lambda i: abs(diameters[i] - original))
            for alternative in [index-1, index+1]:
                if alternative < 0 or alternative >= len(diameters):
                    continue
                pipe['diameter'] = diameters[alternative]
                candidate_id = len(history) + 1
                try:
                    trial = evaluate(doc, root / 'trials' / str(candidate_id))
                    candidate_score = score(trial, doc)
                    improves = candidate_score < (best[0] if best else current_score)
                    # A compliant incumbent cannot be replaced by a failing one.
                    improves = improves and (current['status'] != 'PASS' or trial['status'] == 'PASS')
                    history.append(dict(iteration=iteration+1, pipe=pipe['name'], from_mm=original*1000,
                        to_mm=pipe['diameter']*1000, status=trial['status'], score=candidate_score, selected=False))
                    if improves:
                        best = (candidate_score, pipe, pipe['diameter'], trial, len(history)-1)
                except Exception as exc:
                    history.append(dict(iteration=iteration+1, pipe=pipe['name'], from_mm=original*1000,
                        to_mm=pipe['diameter']*1000, status='ERROR', reason=str(exc), selected=False))
                finally:
                    pipe['diameter'] = original
        if not best:
            break
        current_score, pipe, diameter, current, record = best
        pipe['diameter'] = diameter
        history[record]['selected'] = True
    final = evaluate(doc, root, report=True)
    final.update(candidate=True, proposal=doc, baseline_status=baseline_status, optimization_history=history,
        optimization_outcome='FEASIBLE_CANDIDATE' if final['status'] == 'PASS' else 'NO_FEASIBLE_CANDIDATE_FOUND',
        optimization_note='Bounded local search; no global optimum or infeasibility proof. Tie-break uses pipe volume proxy, not cost.')
    (root / 'optimization.json').write_text(encode(history), encoding='utf-8')
    final['artifacts'].append('optimization.json')
    (root / 'results.json').write_text(encode(final), encoding='utf-8')
    return final
