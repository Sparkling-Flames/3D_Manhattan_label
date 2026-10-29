const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const select={value:'v2',dataset:{v2Module:'personnel_main'},addEventListener(name,fn){this.change=fn;}};
const location={href:''},context={location,document:{querySelectorAll:()=>[select]}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'v21-version-switch.js'),'utf8'),context);
select.change();assert.equal(location.href,'index.html#release=v2&module=personnel_main');
const main=fs.readFileSync(path.join(__dirname,'workbench.js'),'utf8');assert.match(main,/value="v2\.1"/);assert.match(main,/v21-reselection\.html/);
for(const page of ['v21-results.html','v21-reselection.html','v21-exchange-case.html'])assert.match(fs.readFileSync(path.join(__dirname,page),'utf8'),/data-version-switch/);
console.log('v2/v2.1 navigation present, historical view identity retained');
