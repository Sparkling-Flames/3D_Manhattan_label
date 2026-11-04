import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const resolved=require.resolve('marked',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]});
const {marked}=await import(pathToFileURL(resolved).href);
const base=path.dirname(fileURLToPath(import.meta.url));
async function gather(dir){let items=[];for(const ent of await fs.readdir(dir,{withFileTypes:true})){if(ent.isDirectory()&&!['source','inputs'].includes(ent.name))items.push(...await gather(path.join(dir,ent.name)));else if(ent.isFile()&&ent.name.endsWith('.md'))items.push(path.join(dir,ent.name));}return items;}
const reports=await gather(base);const available=new Set(reports);
let math={files:{}};try{math=JSON.parse(await fs.readFile(path.join(base,'math_assets/MANIFEST.json'),'utf8'));}catch{}
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const style=`*{box-sizing:border-box}body{font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif;margin:0;color:#20333e;background:#f1f5f6}main{max-width:1200px;margin:24px auto 50px;background:#fff;border:1px solid #d9e3e8;border-radius:8px;padding:36px 48px}h1{font-size:32px;line-height:1.4}h2{font-size:25px;margin-top:42px;padding-bottom:9px;border-bottom:1px solid #d7e1e6}h3{font-size:19px;margin-top:26px}a{color:#0b7369;text-underline-offset:3px}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow:auto;width:100%;font-size:14px;margin:22px 0}th,td{border:1px solid #d9e1e6;padding:8px 11px;text-align:left;min-width:70px}th{background:#edf4f4}td{vertical-align:top}code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}pre{background:#eef3f5;padding:16px;overflow:auto;font-size:14px}blockquote{margin:24px 0;padding:7px 22px;border-left:4px solid #247b6b;background:#f3f8f6}.nav{font-size:14px;color:#60727c;border-bottom:1px solid #dde6eb;padding-bottom:14px;margin-bottom:26px}.nav a{margin-right:22px}li{margin-bottom:4px}.equation{overflow:auto;text-align:center;margin:22px 0;padding:5px}.inline-equation{display:inline;vertical-align:middle}details{padding:12px 18px;border:1px solid #d7e1e6;margin:20px 0;background:#f8fbfb}summary{cursor:pointer;font-weight:600}@media(max-width:760px){main{padding:22px 17px;margin:0;border:0}h1{font-size:26px}h2{font-size:22px}}@media print{body{background:#fff}main{border:0;padding:0;max-width:none}.nav{display:none}h2{break-after:avoid}table{font-size:11px}img{max-height:90vh;object-fit:contain}}`;
for(const input of reports){
 const rel=path.relative(base,input).split(path.sep).join('/');let md=await fs.readFile(input,'utf8');
 for(const entry of math.files[rel]||[]){
  const href=path.relative(path.dirname(input),path.join(base,entry.file)).split(path.sep).join('/');
  const im=`<img src="${href}" alt="${esc(entry.alt)}" style="width:${entry.width.toFixed(2)}px;height:${entry.height.toFixed(2)}px" class="${entry.display?'block-equation':'inline-equation'}">`;
  md=md.replaceAll(entry.raw,entry.display?`\n<div class="equation">${im}</div>\n`:im);
 }
 let body=await marked.parse(md,{gfm:true,breaks:false});
 body=body.replace(/href="([^"#]+\.md)(#[^"]*)?"/g,(all,url,hash='')=>url.startsWith('http')?all:(available.has(path.resolve(path.dirname(input),url))?`href="${url.replace(/\.md$/,'.html')}${hash}"`:all));
 const title=(md.match(/^# (.+)$/m)||[])[1]||'HOHONET 当前 DSTRUCT 直接 AC';
 const home=path.relative(path.dirname(input),path.join(base,'workbench/index.html')).split(path.sep).join('/');
 const report=path.relative(path.dirname(input),path.join(base,'REPORT_ZH.html')).split(path.sep).join('/');
 const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)}</title><style>${style}</style></head><body><main><div class="nav"><a href="${home}">直接 AC 研究台</a><a href="${report}">完整报告</a><a href="${path.basename(input)}">Markdown 原文</a>HOHONET v2.1 · 2026-11-04</div>${body}</main></body></html>`;
 await fs.writeFile(input.replace(/\.md$/,'.html'),html,'utf8');
}
console.log(JSON.stringify({rendered:reports.length,files:reports.map(x=>path.relative(base,x).replace(/\.md$/,'.html'))}));
