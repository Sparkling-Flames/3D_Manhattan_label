/** Optional report renderer. Numerical reproduction uses Python only.
 * Install marked or set MARKED_MODULE_PATH to its ESM entry. */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(here);
const modulePath = process.env.MARKED_MODULE_PATH;
const {marked} = await import(modulePath ? pathToFileURL(modulePath).href : 'marked');
const markdown = fs.readFileSync(path.join(root,'REPORT_ZH.md'),'utf8');
let body = marked.parse(markdown,{gfm:true});
let items=[], serial=0;
body=body.replace(/<h([23])>(.*?)<\/h\1>/gs,(_,level,text)=>{
  const id='section-'+(++serial);items.push({id,level,text:text.replace(/<[^>]*>/g,'')});
  return `<h${level} id="${id}">${text}</h${level}>`;
});
const esc=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const toc=items.filter(x=>x.level==='2').map(x=>`<a href="#${x.id}">${esc(x.text)}</a>`).join('');
const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>人员类型发现 Part A · v2 研究报告</title><style>
:root{color-scheme:light;--ink:#183144;--muted:#506371;--line:#d9e3e9;--accent:#166d79}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2f5f7;color:var(--ink);font:16px/1.85 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif}header{background:#132f43;color:white;padding:28px 4vw}header p{margin:.25rem 0;color:#d5e3eb}header a{color:#bceff1}.wrap{max-width:1550px;margin:auto;display:grid;grid-template-columns:250px minmax(0,1fr);gap:24px;padding:25px}nav{position:sticky;top:16px;align-self:start;max-height:92vh;overflow:auto;font-size:13px}nav a{display:block;padding:7px 10px;border-left:2px solid #c5d6e1;text-decoration:none;color:#31556d}nav a:hover{background:#e2edf1;border-color:var(--accent)}main{background:white;padding:36px 44px;border:1px solid var(--line);border-radius:12px;min-width:0}h1{font-size:31px;line-height:1.4;letter-spacing:-.6px}h2{font-size:25px;margin-top:2.2em;padding-top:1em;border-top:1px solid var(--line);scroll-margin:18px}h3{font-size:20px;margin-top:1.7em;scroll-margin:18px}a{color:var(--accent);text-underline-offset:3px}p{margin:1.05em 0}strong{font-weight:650}table{display:block;width:100%;overflow:auto;border-collapse:collapse;font-size:14px;line-height:1.65;margin:20px 0}thead{background:#e9f1f4}td,th{text-align:left;vertical-align:top;padding:11px 12px;border:1px solid var(--line);min-width:80px}tr:nth-child(even){background:#f8fafb}code{background:#eef3f5;border-radius:4px;padding:2px 5px;font-size:.88em;overflow-wrap:anywhere}pre{overflow:auto;background:#f3f6f8;padding:18px;border-radius:7px}pre code{padding:0}li{margin:8px 0}footer{color:var(--muted);padding:20px 0;font-size:13px}.tag{display:inline-block;padding:3px 10px;border:1px solid #567584;border-radius:20px;margin-right:8px;font-size:12px}@media(max-width:900px){.wrap{display:block;padding:12px}nav{position:static;max-height:230px;margin-bottom:18px}main{padding:24px 20px}h1{font-size:26px}h2{font-size:22px}}@media print{body{background:white}.wrap{display:block;padding:0}header,nav{display:none}main{border:0;padding:0}h2{break-after:avoid}table{font-size:10px;display:table}td,th{padding:5px}a{color:inherit}}
</style></head><body><header><span class="tag">v2 · 冻结输入</span><span class="tag">Part A · 回顾性留建筑</span><p>60 人画像 · 92 个候选分型 · 58,679 唯一团队 · 175 图 / 22 楼</p><p><a href="presentation/personnel_types_part_a.html">打开整簇与团队联动展示</a>　<a href="assessment/WORKER_PORTRAITS_60.csv">下载60人联合画像</a>　<a href="RUN_EVIDENCE_ZH.md">可读运行证据</a></p></header><div class="wrap"><nav aria-label="报告目录">${toc}</nav><main>${body}<footer>报告正文自包含可离线阅读。相对链接的完整明细随三份ZIP合并目录提供；单独下载此HTML不自动带入其它明细文件。本文没有远程脚本、追踪或网络依赖。</footer></main></div></body></html>`;
fs.writeFileSync(path.join(root,'REPORT_ZH.html'),html);
fs.writeFileSync(path.join(root,'reproducibility/REPORT_RENDER_RECEIPT.json'),JSON.stringify({renderer:'marked',renderer_version:JSON.parse(fs.readFileSync(new URL('../package.json',import.meta.resolve(modulePath ? pathToFileURL(modulePath).href:'marked')),'utf8')).version,headings:items.length,html_bytes:Buffer.byteLength(html),has_remote_script:/<script[^>]+src=["']https?:/.test(html),source:'REPORT_ZH.md'},null,2)+'\n');
process.stdout.write(JSON.stringify({html_bytes:Buffer.byteLength(html),sections:items.filter(x=>x.level==='2').length})+'\n');
