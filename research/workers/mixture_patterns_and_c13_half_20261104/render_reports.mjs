import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const resolved=require.resolve('marked',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]});
const {marked}=await import(pathToFileURL(resolved).href);
const base=path.dirname(fileURLToPath(import.meta.url));
const reports=['REPORT_ZH.md','README.md','METHODS_AND_SCOPE.md','SOURCE_AND_REPRODUCTION.md','mixtures/REPORT_ZH.md','mixtures/README.md','curves/REPORT_ZH.md','curves/README.md','c13_half/REPORT_ZH.md','c13_half/README.md'];
const available=new Set(reports.map(x=>path.resolve(base,x)));
const style=`body{font:16px/1.85 system-ui,"Microsoft YaHei",sans-serif;margin:0;color:#1c3038;background:#f3f6f7}main{max-width:1150px;margin:25px auto 50px;background:#fff;border:1px solid #d9e3e8;border-radius:8px;padding:40px 48px}h1{font-size:32px;line-height:1.4}h2{font-size:25px;margin-top:45px;padding-bottom:10px;border-bottom:1px solid #d7e1e6}h3{font-size:19px;margin-top:28px}a{color:#116f63;text-underline-offset:3px}img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow:auto;width:100%;font-size:14px;margin:22px 0}th,td{border:1px solid #d9e1e6;padding:8px 11px;text-align:left;min-width:75px}th{background:#f0f5f4}td{vertical-align:top}code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;overflow-wrap:anywhere}pre{background:#eef3f5;padding:16px;overflow:auto;font-size:14px}blockquote{margin:24px 0;padding:7px 22px;border-left:4px solid #247b6b;background:#f3f8f6}.nav{font-size:14px;color:#60727c;border-bottom:1px solid #dde6eb;padding-bottom:15px;margin-bottom:28px}.nav a{margin-right:24px}li{margin-bottom:5px}@media(max-width:760px){main{padding:24px 18px;margin:0;border:0}h1{font-size:26px}h2{font-size:23px}}`;
for(const rel of reports){
 const input=path.join(base,rel),md=await fs.readFile(input,'utf8');
 let body=await marked.parse(md,{gfm:true,breaks:false});
 body=body.replace(/href="([^"#]+\.md)(#[^"]*)?"/g,(all,url,hash='')=>{
  if(url.startsWith('http'))return all;
  return available.has(path.resolve(path.dirname(input),url))?`href="${url.replace(/\.md$/,'.html')}${hash}"`:all;
 });
 const title=(md.match(/^# (.+)$/m)||[])[1]||'HOHONET v2.1';
 const home=path.relative(path.dirname(input),path.join(base,'workbench/index.html')).split(path.sep).join('/');
 const source=path.basename(input);
 const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title}</title><style>${style}</style></head><body><main><div class="nav"><a href="${home}">混合人群研究台</a><a href="${source}">Markdown 原文</a>HOHONET v2.1 · 2026-11-04</div>${body}</main></body></html>`;
 await fs.writeFile(input.replace(/\.md$/,'.html'),html,'utf8');
}
console.log(JSON.stringify({rendered:reports.length,outputs:reports.map(x=>x.replace(/\.md$/,'.html'))}));
