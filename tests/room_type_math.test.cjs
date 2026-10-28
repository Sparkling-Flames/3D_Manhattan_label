const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const page=path.resolve(__dirname,'../research/statistics/research_explorer_v1_r2_20261017');
const source=fs.readFileSync(path.join(page,'workbench.js'),'utf8');
const ctx={hintButton:k=>`<button data-hint="${k}">?</button>`};vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('function researchMathHTML('),source.indexOf('async function render(){'))+'this.math=researchMathHTML;this.room=roomTypeHTML;',ctx);

test('same-purpose entry exposes adopted evidence, actual files and three original-answer routes',()=>{
 const html=ctx.room();
 for(const value of ['161图','4.567','4.188','11.449','11.450','1,638','104份','data-hint="mae"'])assert(html.includes(value),value);
 assert.match(html,/不能代替同一个物理房间/);assert.doesNotMatch(html,/导师|用户|审计|\.md/);
 for(const m of html.matchAll(/(?:href|src)="([^"#]+)"/g))assert(fs.existsSync(path.resolve(page,m[1])),m[1]);
 assert.equal((html.match(/module=images&image=/g)||[]).length,3);
 assert.equal((html.match(/ download>/g)||[]).length,16);
});

test('math panels distinguish status, symmetric amplitude, signed differences and conditional variance',()=>{
 assert.match(ctx.math('fusion'),/延期、未执行、参考不可用/);
 assert.match(ctx.math('population'),/实际执行且非延期/);
 assert.match(ctx.math('mixture'),/总方差为0时占比无定义/);
 assert.match(ctx.math('abc'),/\|Q꜀−Qₐ\|\+\|Q꜀−Qᵦ\|/);
 assert.match(ctx.math('same_room'),/CA 73\.01%、CB 74\.05%/);
 assert.match(ctx.math('background'),/偶数加一人提高门槛/);
});
