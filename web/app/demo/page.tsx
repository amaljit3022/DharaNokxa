"use client";

import * as maplibregl from "maplibre-gl";
import { FormEvent, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
type Result = {status:string; scheme_name:string; summary:Record<string, string|number|boolean>; households:any[]; nodes:any[]; pipes:any[]; iterations:any[]; artifacts:Record<string,string>};

export default function Home() {
  const [result, setResult] = useState<Result|null>(null);
  const [state, setState] = useState("Ready");
  const [scheme, setScheme] = useState("Demo JJM 2.0 Rural Scheme");
  const [lat, setLat] = useState("26.182145"); const [lon, setLon] = useState("91.743281");
  const [tab, setTab] = useState("Overview");

  useEffect(() => { fetch(`${API}/demo`).then(r => r.ok ? r.json() : null).then(setResult).catch(() => null); }, []);
  async function run(event: FormEvent) {
    event.preventDefault(); setState("Queued");
    const response = await fetch(`${API}/runs`, {method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify({scheme_name:scheme,source_latitude:Number(lat),source_longitude:Number(lon)})});
    const job = await response.json();
    const timer = setInterval(async () => { const next = await fetch(`${API}/runs/${job.job_id}`).then(r=>r.json()); setState(next.stage); if(next.state === "COMPLETE" || next.state === "FAILED") { clearInterval(timer); if(next.result) setResult(next.result); } }, 1500);
  }
  return <main>
    <header><div><span className="mark">DN</span><strong>DharaNokxa</strong><span className="muted">Automated hydraulic design</span></div><span className="badge">{result ? `${result.summary.data_quality} · ${result.summary.review_status}` : "New design"}</span></header>
    {!result ? <section className="setup"><div><p className="eyebrow">NEW HYDRAULIC DESIGN</p><h1>Field facts in.<br/>Engineering evidence out.</h1><p>Provide a source location and household coordinates. DharaNokxa builds, simulates, corrects and documents a candidate network.</p></div><form onSubmit={run}><label>Scheme name<input value={scheme} onChange={e=>setScheme(e.target.value)} required/></label><div className="grid"><label>ESR latitude<input value={lat} onChange={e=>setLat(e.target.value)}/></label><label>ESR longitude<input value={lon} onChange={e=>setLon(e.target.value)}/></label></div><label>Household data<button type="button" className="drop">Generate deterministic 100-household demo</button></label><button className="primary">Generate hydraulic design</button><small>JJM 2.0 Assam demo profile · Synthetic assumptions are clearly labeled.</small><p aria-live="polite">{state}</p></form></section> : <Workspace result={result} tab={tab} setTab={setTab} state={state}/>}
  </main>
}

function Workspace({result,tab,setTab,state}:{result:Result;tab:string;setTab:(s:string)=>void;state:string}) {
  const s:any=result.summary;
  return <><div className="scheme"><div><p className="eyebrow">CANDIDATE DESIGN</p><h1>{result.scheme_name}</h1></div><div className={`status ${result.status.toLowerCase()}`}>{result.status}<small>Hydraulic status</small></div></div>
  <nav>{["Overview","Network","Optimization","Tables","Design basis","Exports"].map(x=><button className={tab===x?"active":""} onClick={()=>setTab(x)} key={x}>{x}</button>)}</nav>
  {tab==="Overview"||tab==="Network"?<div className="workspace"><aside><Metric label="Worst endpoint" value={`${Number(s.minimum_endpoint_pressure_m).toFixed(3)} m`} note={`Critical: ${s.critical_endpoint_id}`}/><div className="threshold"><span>Hard requirement <b>&gt; 7.00 m</b></span><span>Target <b>≥ 8.00 m</b></span></div><Metric label="Achieved margin" value={`${Number(s.achieved_pressure_margin_m).toFixed(3)} m`} note={`Configured margin: ${Number(s.configured_pressure_margin_m).toFixed(2)} m`}/><div className="facts"><span><b>{s.households}</b> households</span><span><b>{s.population}</b> people</span><span><b>{Number(s.design_demand_lps).toFixed(3)}</b> L/s</span><span><b>{Number(s.total_pipe_length_m).toFixed(0)}</b> m pipe</span></div><p className="corridor-note"><b>Road corridor alignment</b><br/>Paired left/right roadside pipes. Straight segments between named intersections. Road boring only at approved crossings.</p><p className="notice">Preliminary automated design. Synthetic terrain, roads, population and pipe catalog. Awaiting engineer review.</p></aside><NetworkMap result={result}/></div>:null}
  {tab==="Optimization"?<Optimization rows={result.iterations}/>:null}
  {tab==="Tables"?<Tables result={result}/>:null}
  {tab==="Design basis"?<Basis/>:null}
  {tab==="Exports"?<Exports result={result}/>:null}
  <footer><span>{state}</span><span>EPANET 2.2 through WNTR · Run {String(s.simulator)}</span></footer></>
}

function Metric({label,value,note}:{label:string;value:string;note:string}) {return <div className="metric"><span>{label}</span><strong>{value}</strong><small>{note}</small></div>}
function NetworkMap({result}:{result:Result}) { const ref=useRef<HTMLDivElement>(null); useEffect(()=>{if(!ref.current)return; maplibregl.setWorkerUrl("/maplibre-worker.js"); const map=new maplibregl.Map({container:ref.current,style:{version:8,sources:{},layers:[{id:"background",type:"background",paint:{"background-color":"#eef0eb"}}]},center:[91.744,26.192],zoom:12.5}); map.on("load",()=>{const features=result.pipes.map(p=>{const a=p.from_node==="ESR"?[91.743281,26.182145]:point(result,p.from_node);const b=point(result,p.to_node);return {type:"Feature",properties:p,geometry:{type:"LineString",coordinates:[a,b]}}});map.addSource("pipes",{type:"geojson",data:{type:"FeatureCollection",features} as any});map.addLayer({id:"pipes",type:"line",source:"pipes",paint:{"line-color":"#087d83","line-width":["interpolate",["linear"],["get","internal_diameter_mm"],20,2,105,8]}});map.addSource("nodes",{type:"geojson",data:{type:"FeatureCollection",features:result.nodes.map(n=>({type:"Feature",properties:n,geometry:{type:"Point",coordinates:[n.longitude,n.latitude]}}))} as any});map.addLayer({id:"nodes",type:"circle",source:"nodes",paint:{"circle-radius":["case",["get","critical"],8,4],"circle-color":["case",["get","critical"],"#c84040","#17324d"],"circle-stroke-color":"#fff","circle-stroke-width":1.5}});const bounds=new maplibregl.LngLatBounds(); result.nodes.forEach(n=>bounds.extend([n.longitude,n.latitude]));map.fitBounds(bounds,{padding:55});}); return()=>map.remove()},[result]); return <section className="map"><div className="mapbar"><b>Network map</b><span>Diameter mode · Critical endpoint highlighted</span></div><div ref={ref} className="mapcanvas"/></section>}
function point(r:Result,id:string){const n=r.nodes.find(x=>x.node_id===id);return [n.longitude,n.latitude]}
function Optimization({rows}:{rows:any[]}){return <section className="panel"><h2>Optimization evidence</h2><p>The initial network failed. Each accepted change targeted the highest-loss pipe on the path to the critical endpoint; safe downsizing trials followed compliance.</p><div className="chart">{rows.filter((_,i)=>i%Math.ceil(rows.length/24)===0).map((r,i)=><i key={i} style={{height:`${Math.max(4,Math.min(100,Number(r.minimum_endpoint_pressure_m)+15))}%`}} title={`${r.minimum_endpoint_pressure_m} m`}/>)}</div><table><thead><tr><th>Iteration</th><th>Action</th><th>Critical endpoint</th><th>Minimum pressure</th></tr></thead><tbody>{rows.slice(-16).map(r=><tr key={`${r.iteration}-${r.action}`}><td>{r.iteration}</td><td>{r.action}</td><td>{r.critical_endpoint_id}</td><td>{Number(r.minimum_endpoint_pressure_m).toFixed(3)} m</td></tr>)}</tbody></table></section>}
function Tables({result}:{result:Result}){return <section className="panel"><h2>Hydraulic nodes</h2><table><thead><tr><th>ID</th><th>Elevation</th><th>Demand</th><th>Pressure</th><th>Status</th></tr></thead><tbody>{result.nodes.map(n=><tr key={n.node_id}><td>{n.node_id}</td><td>{n.elevation_m.toFixed(2)} m</td><td>{n.design_demand_lps.toFixed(3)} L/s</td><td>{n.pressure_m.toFixed(3)} m</td><td>{n.compliance}</td></tr>)}</tbody></table></section>}
function Basis(){return <section className="panel"><h2>Design basis</h2><p>55 LPCD × 1.15 demand uplift = 63.25 LPCD/person. Synthetic peak factor 3.0. Endpoint pressure must be strictly greater than 7.00 m; optimization targets at least 8.00 m. HDPE hydraulic calculations use internal diameter.</p><div className="notice">These values come from the project brief and remain pending verification against authoritative departmental standards.</div></section>}
function Exports({result}:{result:Result}){return <section className="panel"><h2>Design package</h2><p>All files were generated from the same frozen result.</p><div className="downloads">{Object.entries(result.artifacts).map(([name,path])=><a key={name} href={`file:///${String(path).replaceAll("\\","/")}`}>{name.replaceAll("_"," ")}<small>{String(path).split(/[\\/]/).pop()}</small></a>)}</div></section>}
