export type Asset = Record<string, any>;
export type Model = {nodes: Asset[]; links: Asset[]; curves: Asset[]; patterns: Asset[]; controls: Asset[]; sources: Asset[]; options: Record<string, any>; [key: string]: any};
export type Document = {model: Model; crs: string|null; layers: Asset[]; provenance: Asset[]; criteria: Record<string,number>; scenarios?:Asset[]; catalog?:Asset[]};
export type Project = {id:string; name:string; revision:number; hash:string; document:Document};
export type Issue = {rule:string; asset:string|null; severity:string; message:string};
export const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';
export async function request(path:string, init?:RequestInit) {
  const response = await fetch(API+path, init);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body));
  return body;
}
export function json(method:string, value:unknown):RequestInit {return {method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(value)}}
