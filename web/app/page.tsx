"use client";

import {useEffect, useState} from 'react';
import AssetEditor from '../components/AssetEditor';
import GeometryTools from '../components/GeometryTools';
import InputPanel from '../components/InputPanel';
import NetworkView from '../components/NetworkView';
import Operations from '../components/Operations';
import Results from '../components/Results';
import {IssueList, ResultTable} from '../components/Tables';
import {API, Asset, Document, Issue, Project, json, request} from '../components/project-types';

const tabs = ['Inputs', 'Network', 'Operations', 'Checks', 'Results', 'Optimization', 'Exports'];
export default function Home() {
  const [projects, setProjects] = useState<Asset[]>([]);
  const [project, setProject] = useState<Project|null>(null);
  const [doc, setDoc] = useState<Document|null>(null);
  const [name, setName] = useState('');
  const [tab, setTab] = useState('Inputs');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Asset|null>(null);
  const [editType, setEditType] = useState('');
  const [issues, setIssues] = useState<Issue[]>([]);
  const [runs, setRuns] = useState<Asset[]>([]);
  const [run, setRun] = useState<Asset|null>(null);
  const [undo, setUndo] = useState<Document[]>([]);

  useEffect(() => { request('/projects').then(setProjects).catch(e => setError(e.message)); }, []);
  useEffect(() => {
    if (!project || !run || !['QUEUED', 'RUNNING'].includes(run.state)) return;
    let active = true;
    const timer = setInterval(() => request(`/projects/${project.id}/runs/${run.id}`).then(r => {
      if (!active) return;
      setRun(r);
      if (r.state === 'COMPLETE') {
        setRuns(old => [r, ...old.filter(x => x.id !== r.id)]);
        setMessage(`Analysis complete for revision ${r.revision}.`);
      }
      if (r.state === 'FAILED') setError(r.error);
    }).catch(e => { if (active) setError(e.message); }), 1200);
    return () => { active = false; clearInterval(timer); };
  }, [project?.id, run?.id, run?.state]);
  useEffect(() => {
    if (!project || !doc || !dirty) return;
    try { localStorage.setItem(`dn-draft-${project.id}`, JSON.stringify({revision: project.revision, document: doc})); }
    catch { setMessage('Local draft storage is full. Save a revision to retain changes.'); }
  }, [doc, dirty, project]);

  function change(next: Document) {
    if (doc) setUndo(history => [...history.slice(-19), doc]);
    setDoc(next); setDirty(true); setIssues([]);
  }
  async function task(fn: () => Promise<void>) {
    setBusy(true); setError('');
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  async function open(id: string) {
    await task(async () => {
      const p = await request(`/projects/${id}`);
      setProject(p); setDoc(p.document); setDirty(false); setSelected(null); setEditType('');
      setIssues([]); setUndo([]); setTab('Inputs'); setMessage('');
      const all = await request(`/projects/${id}/runs`); setRuns(all); setRun(all[0] ?? null);
      const draft = localStorage.getItem(`dn-draft-${id}`);
      if (draft) {
        try {
          const d = JSON.parse(draft);
          if (d.revision === p.revision) { setDoc(d.document); setDirty(true); setMessage('Recovered your unsaved draft. Review and save a revision.'); }
        } catch { setMessage('Saved project loaded; local draft could not be recovered.'); }
      }
    });
  }
  async function create() {
    if (!name.trim()) { setError('Enter a project name.'); return; }
    await task(async () => {
      const p = await request('/projects', json('POST', {name}));
      setProjects(old => [p, ...old]); setProject(p); setDoc(p.document);
      setTab('Inputs'); setRun(null); setRuns([]); setDirty(false); setUndo([]);
      setSelected(null); setEditType(''); setIssues([]);
      setMessage('Project created. Upload field data or add network assets.');
    });
  }
  async function save() {
    if (!project || !doc) return null;
    const p = await request(`/projects/${project.id}`, json('PUT', {revision: project.revision, document: doc}));
    setProject(p); setDoc(p.document); setDirty(false); localStorage.removeItem(`dn-draft-${p.id}`);
    setMessage(`Revision ${p.revision} saved.`); return p;
  }
  async function validate() {
    await task(async () => {
      const p = dirty ? await save() : project; if (!p) return;
      const r = await request(`/projects/${p.id}/validate`, {method:'POST'});
      setIssues(r.issues); setTab('Checks');
      setMessage(r.valid ? 'Model checks passed. Review warnings before analysis.' : 'Resolve the model errors below.');
    });
  }
  async function analyze(optimize = false) {
    await task(async () => {
      const p = dirty ? await save() : project; if (!p) return;
      const r = await request(`/projects/${p.id}/${optimize ? 'optimize' : 'runs'}`, json('POST', {revision: p.revision}));
      setRun(r); setTab(optimize ? 'Optimization' : 'Results'); setMessage('Analysis queued for the saved revision.');
    });
  }
  function applyAsset(asset: Asset) {
    if (!doc) return;
    const key = asset.node_type ? 'nodes' : 'links'; const existing = doc.model[key];
    if (!selected && existing.some(a => a.name === asset.name)) { setError('This ID already exists in the node/link namespace.'); return; }
    change({...doc, model: {...doc.model, [key]: selected ? existing.map(a => a.name === selected.name ? asset : a) : [...existing, asset]}});
    setSelected(asset); setEditType('');
  }
  function inspect(asset: Asset) { setSelected(asset); setEditType(asset.node_type ?? asset.link_type); setTab('Network'); }
  function removeSelected() {
    if (!selected || !doc) return;
    if (selected.locked) { setError('This asset is locked.'); return; }
    if (doc.model.controls.length || doc.model.sources.length) { setError('Review control/source references before removing an asset.'); return; }
    if (selected.node_type && doc.model.links.some(l => l.start_node_name === selected.name || l.end_node_name === selected.name)) {
      setError('Remove or reconnect incident links before removing a junction.'); return;
    }
    const key = selected.node_type ? 'nodes' : 'links';
    change({...doc, model: {...doc.model, [key]: doc.model[key].filter(a => a.name !== selected.name)}});
    setSelected(null); setEditType('');
  }
  const running = ['RUNNING', 'QUEUED'].includes(run?.state);
  const stale = !!run && !!project && (dirty || run.revision !== project.revision);
  return <main className="studio">
    <header><div><span className="mark">DN</span><strong>DharaNokxa</strong><span className="muted">Hydraulic engineering workspace</span></div><a href="/demo">Open synthetic demo</a></header>
    <div className="project-bar">
      <label>Saved project<select value={project?.id ?? ''} onChange={e => { if (e.target.value) open(e.target.value); }}><option value="">Select a project</option>{projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label>
      <label>New project name<input value={name} onChange={e => setName(e.target.value)} placeholder="Village water supply"/></label><button onClick={create} disabled={busy}>Create project</button>
    </div>
    <div className="feedback" aria-live="polite">{message && <span>{message}</span>}{error && <p className="error" role="alert">{error}</p>}</div>
    {!project || !doc ? <section className="welcome"><p className="eyebrow">BUILD FROM YOUR FIELD DATA</p><h1>A real network.<br/>A traceable design.</h1><p>Create a project above, then choose your starting point.</p><div className="start-cards"><article><h2>Import EPANET</h2><p>Bring an INP model with nodes, equipment, patterns, controls and pipe geometry.</p></article><article><h2>Upload field data</h2><p>Import CSV, Excel, GeoJSON, GeoPackage or zipped Shapefiles. Review mapping and units.</p></article><article><h2>Enter a network</h2><p>Add junctions, reservoirs, tanks, pipes, pumps and valves with editable forms.</p></article></div></section> : <>
      <div className="project-heading"><div><p className="eyebrow">{project.name}</p><h1>Revision {project.revision} <small>{dirty ? '· Unsaved draft' : '· Saved'}</small></h1></div><div className="actions">
        <button disabled={!undo.length} onClick={() => {const previous=undo[undo.length-1]; setUndo(undo.slice(0,-1)); setDoc(previous); setDirty(true);}}>Undo</button>
        <button disabled={busy || !dirty} onClick={() => task(async () => { await save(); })}>Save revision</button><button disabled={busy} onClick={validate}>Validate</button><button className="primary" disabled={busy || running} onClick={() => analyze()}>Run DDA + PDA</button>
      </div></div>
      <nav>{tabs.map(t => <button key={t} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</nav>
      {tab === 'Inputs' && <InputPanel project={project} doc={doc} dirty={dirty} onChange={change} task={task} onImported={p => {setProject(p); setDoc(p.document); setDirty(false); setUndo([]); setMessage('Import committed as a new revision.'); setIssues([]);}}/>}
      {tab === 'Network' && <>
        <div className="tool-row">{['Junction','Reservoir','Tank','Pipe','Pump','Valve'].map(t => <button key={t} onClick={() => {setSelected(null); setEditType(t);}}>+ {t}</button>)}<span>{doc.model.nodes.length} nodes · {doc.model.links.length} links</span></div>
        <div className="engineering-grid"><section><NetworkView document={doc} selected={selected?.name} onSelect={inspect}/><div className="table-scroll"><table><thead><tr><th>Asset ID</th><th>Type</th><th>From</th><th>To</th><th>Action</th></tr></thead><tbody>{[...doc.model.nodes,...doc.model.links].map((a,i) => <tr key={i}><td>{a.name}</td><td>{a.node_type ?? a.link_type}</td><td>{a.start_node_name ?? '—'}</td><td>{a.end_node_name ?? '—'}</td><td><button onClick={() => inspect(a)}>Edit</button></td></tr>)}</tbody></table></div></section>
        <aside>{editType ? <><AssetEditor asset={selected} type={editType} document={doc} onSave={applyAsset} onCancel={() => setEditType('')}/>{selected && <button onClick={removeSelected}>Remove selected asset from draft</button>}</> : <div className="empty-map">Select an asset or add one above.<p>One physical connection uses one node. Geometry vertices shape pipes without adding joints.</p></div>}</aside></div>
        <GeometryTools project={project} doc={doc} dirty={dirty} onChange={change} task={task}/>
      </>}
      {tab === 'Operations' && <Operations doc={doc} onChange={change}/>}
      {tab === 'Checks' && <section className="panel"><h2>Model and construction checks</h2><p>Model validity, hydraulic criteria and engineer approval are separate decisions.</p><IssueList issues={issues} onSelect={id => {const a=[...doc.model.nodes,...doc.model.links].find(a=>a.name===id); if(a)inspect(a);}}/>{!issues.length && <p>Use Validate to check the saved model.</p>}</section>}
      {tab === 'Results' && <Results run={run} runs={runs} onRun={setRun} stale={stale}/>}
      {tab === 'Optimization' && <section className="panel wide"><h2>Compare diameter candidates</h2><p>Uses your internal-diameter catalog and all configured scenarios. Locked pipes remain unchanged. Full network evaluation supports loops and multiple sources.</p><button disabled={busy || running} onClick={() => analyze(true)}>Optimize diameters</button><p>{run?.state}</p>{run?.candidate && run.state === 'COMPLETE' && <><p>{run.optimization_outcome} · Baseline {run.baseline_status} → Candidate {run.status}</p><p>{run.optimization_note}</p><ResultTable rows={run.optimization_history} fields={['iteration','pipe','from_mm','to_mm','status','selected','reason']}/><button disabled={dirty || run.revision !== project.revision || run.status !== 'PASS'} onClick={() => task(async () => {const p=await request(`/projects/${project.id}/runs/${run.id}/accept`,json('POST',{revision:project.revision})); setProject(p); setDoc(p.document); setDirty(false); setMessage('Candidate saved as a new revision. Run analysis for the adopted revision.');})}>Apply feasible candidate as new revision</button></>}</section>}
      {tab === 'Exports' && <section className="panel"><h2>Download the analyzed revision</h2>{run?.state === 'COMPLETE' ? <><p>{run.candidate ? 'Candidate based on revision' : 'Revision'} {run.revision} · {run.engine} · input hash {run.input_hash.slice(0,16)}{stale ? ' · Older than the current draft' : ''}</p><div className="downloads">{run.artifacts.map((f:string) => <a key={f} href={`${API}/projects/${project.id}/runs/${run.id}/artifacts/${f}`}>{f}</a>)}</div></> : <p>Complete an analysis to download its frozen INP, inputs, result tables and EPANET reports.</p>}</section>}
    </>}
    <footer><span>Field inputs stay editable · No automatic synthetic completion</span><span>EPANET 2.2 through WNTR</span></footer>
  </main>;
}
