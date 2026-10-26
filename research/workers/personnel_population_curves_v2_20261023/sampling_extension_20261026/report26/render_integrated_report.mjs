/** Render the final Markdown report as one portable HTML file.
 * Numerical analysis remains in the saved Python code and CSV tables.
 * Usage: node report26/render_integrated_report.mjs STUDY
 * Dependency: marked 17.0.5 (or use the supplied already rendered HTML).
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const study = path.resolve(process.argv[2] || '.');
const moduleRoots = process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES
  ? [process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES] : [study];
const markedPath = require.resolve('marked', { paths: moduleRoots });
const { marked } = await import(pathToFileURL(markedPath));
const input = path.join(study, 'REPORT_ZH.md');
const markdown = fs.readFileSync(input, 'utf8');
if (/\{\{[A-Z_]+\}\}/.test(markdown)) throw new Error('Unfilled final report field');
let body = marked.parse(markdown, { gfm: true, breaks: false });
const images = [];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
body = body.replace(/<img\b([^>]*?)src="([^"]+)"([^>]*?)>/g, (tag, before, source, after) => {
  if (/^(https?:|data:)/i.test(source)) return tag;
  const local = path.resolve(study, decodeURIComponent(source));
  if (!local.startsWith(study + path.sep)) throw new Error('Image outside study: ' + source);
  const bytes = fs.readFileSync(local);
  const suffix = path.extname(local).toLowerCase();
  const mime = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml' }[suffix];
  if (!mime) throw new Error('Unsupported inline image: ' + source);
  images.push({ relative_path: path.relative(study, local), bytes: bytes.length, sha256: hash(bytes) });
  return `<img${before}src="data:${mime};base64,${bytes.toString('base64')}"${after}>`;
});
const contents = [];
let heading = 0;
body = body.replace(/<h2>([\s\S]*?)<\/h2>/g, (_tag, label) => {
  const id = 'section-' + (++heading);
  contents.push(`<a href="#${id}">${label}</a>`);
  return `<h2 id="${id}">${label}</h2>`;
});
// Data/code links are repository-relative in REPORT_ZH.md; HTML lives in report26.
body = body.replace(/href="(?!https?:|mailto:|#|data:)([^"]+)"/g, 'href="../$1"');
const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HOHONET 人数曲线抽样精度与稳定性 · 2026-10-26</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#1d2835;font-family:system-ui,"Noto Sans CJK SC",sans-serif;line-height:1.7;font-size:16px}
main{max-width:1250px;margin:30px auto;padding:36px 44px;background:white;border:1px solid #e0e5ea;border-radius:10px}h1{font-size:30px;line-height:1.4;color:#123b52}h2{margin-top:2.2em;padding-top:.4em;border-top:2px solid #e5ecf0;font-size:24px}h3{font-size:20px;margin-top:1.7em}a{color:#17688c;text-decoration:none}a:hover{text-decoration:underline}p{margin:1em 0}li{margin:.35em 0}
nav{display:flex;flex-wrap:wrap;gap:7px 20px;background:#eef4f7;padding:16px 20px;border-radius:6px;margin:20px 0}nav a{font-size:14px}img{max-width:100%;height:auto;display:block;margin:20px auto}table{display:block;width:100%;overflow:auto;border-collapse:collapse;font-size:14px;margin:20px 0}th,td{padding:9px 11px;text-align:left;border:1px solid #dce3e9;vertical-align:top}th{background:#edf3f6;font-weight:650}tr:nth-child(even) td{background:#fafbfc}blockquote{margin:18px 0;padding:10px 18px;border-left:4px solid #6695a8;background:#f3f7f8}pre{overflow:auto;padding:16px;background:#f2f4f6;border-radius:5px;font-size:13px;line-height:1.5}code{font-family:ui-monospace,monospace;font-size:.9em;overflow-wrap:anywhere}.download{padding:12px 18px;background:#e9f3ed;border-radius:6px;font-size:14px}.footer{font-size:13px;color:#5a6570;border-top:1px solid #dde3e8;margin-top:30px;padding-top:16px}
@media(max-width:800px){main{margin:0;padding:22px 18px;border:0;border-radius:0}h1{font-size:25px}h2{font-size:21px}table{font-size:13px}}@media print{body{background:white}main{max-width:none;border:0;margin:0;padding:0}nav,.download{display:none}img,pre{break-inside:avoid}h2,h3{break-after:avoid}a{color:inherit}}
</style></head><body><main>
<div class="download">报告中的主要图表已嵌入本文件，可独立阅读。精确数据、代码与所有分包：<a href="https://chatgpt.com/library?file_id=libfile_381dc032fac08191b4b8d1b28c16ac84&account_id=personal">当前统一入口</a>。相对路径的数据链接在完整解压后可用。</div>
<nav aria-label="目录">${contents.join('')}</nav>
${body}
<div class="footer">固定源提交 b9bcec809fbaec8ab055931a1abb7baa5db44dac；真人 v2。HTML仅呈现已保存报告和图表，不执行抽样或融合。</div>
</main></body></html>`;
const output = path.join(study, 'report26/REPORT.html');
fs.writeFileSync(output + '.writing', html);
fs.renameSync(output + '.writing', output);
const receipt = { markdown: 'REPORT_ZH.md', markdown_sha256: hash(Buffer.from(markdown)), html: 'report26/REPORT.html', html_bytes: fs.statSync(output).size,
  html_sha256: hash(fs.readFileSync(output)), embedded_images: images, sections: contents.length, node: process.version, marked_entry: markedPath,
  standalone_figures: true, new_fusions: 0, new_orders: 0 };
fs.writeFileSync(path.join(study, 'report26/HTML_RENDER_RECEIPT.json'), JSON.stringify(receipt, null, 2) + '\n');
console.log(JSON.stringify({ html_bytes: receipt.html_bytes, embedded_images: images.length, sections: contents.length }));
