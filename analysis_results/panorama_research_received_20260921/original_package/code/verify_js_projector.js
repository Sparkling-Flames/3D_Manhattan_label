const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(process.argv[2],'utf8');
const begin=source.indexOf('function projectCornersForViewer(corners)');
let depth=0,end=0,op=source.indexOf('{',begin);
for(let i=op;i<source.length;i++){ if(source[i]==='{')depth++;if(source[i]==='}')depth--;if(depth===0){end=i+1;break;} }
const f=source.slice(begin,end);
class Vector3 { constructor(x,y,z){this.x=x;this.y=y;this.z=z;} }
const ctx={THREE:{Vector3},W:1024,H:512,Math};vm.createContext(ctx);
vm.runInContext(f,ctx,{timeout:1000});
const input=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
process.stdout.write(JSON.stringify(ctx.projectCornersForViewer(input)));
