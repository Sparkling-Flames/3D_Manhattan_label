"""Current standalone dashboard contract; all writes use temporary fixtures."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tools.thesis_main.analysis import difficulty_wild_dashboard as dw

RUN = dw.base.ROOT.parent / 'output/difficulty_wild_35_20261017/full'


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    output = tmp_path_factory.mktemp('dashboard')
    sources = dw.load_inputs()
    rows = dw.base.read_jsonl(RUN/'simulations.jsonl')
    selected = {}
    for row in rows:
        selected.setdefault(row['difficulty'], row['image_id'])
    ids = set(selected.values())
    dw.base.write_jsonl(output/'simulations.jsonl', [r for r in rows if r['image_id'] in ids])
    for name in ('summary.json','VALIDATION.json','REPRODUCIBILITY.json','TEST_RESULTS.json'):
        shutil.copyfile(RUN/name, output/name)
    original = dw.load_inputs
    try:
        dw.load_inputs = lambda: sources
        path = dw.build(output)
    finally:
        dw.load_inputs = original
    html = path.read_text()
    data = json.loads(re.search(r'<script id="dataset" type="application/json">(.*?)</script>',html,re.S).group(1))
    return path, data, html


def test_build_outputs(built):
    path, data, _ = built
    assert path.name == 'dashboard.html' and path.is_file()
    assert data['summary']['target_images'] == 259
    assert data['summary']['generated'] == 6678
    assert data['summary']['wild'] + data['summary']['normal'] == 6678


def test_page_js_dom_mock(built):
    path, _, _ = built
    js = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[1],'utf8');
const scripts=[...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(x=>x[1]);
assert.equal(scripts.length,2);
const E={};let strokes=0;
const ctx=new Proxy({},{get:(_,k)=>k==='stroke'?()=>strokes++:()=>{},set:()=>true});
class Element {
 constructor(){this.children=[];this.dataset={};this.style={};this.value='';this.checked=false;
 this.textContent='';this.className='';this.clientWidth=640;this.hidden=false;this.handlers={};}
 append(...cs){this.children.push(...cs);if(this.tag==='select'&&!this.value&&cs[0])this.value=cs[0].value;}
 replaceChildren(...cs){this.children=cs;this.value='';}
 setAttribute(){} insertAdjacentHTML(){} scrollIntoView(){} getContext(){return ctx;}
 addEventListener(k,v){this.handlers[k]=v;} querySelector(){return this.children[0]||null;}
}
const selectIds=['difficulty','scope','modelSelect','humanSelect','sampleSelect','sampleType','metric'];
const document={getElementById(id){if(!E[id]){E[id]=new Element();if(selectIds.includes(id))E[id].tag='select';}return E[id];},
 createElement(tag){const e=new Element();e.tag=tag;return e;},createTextNode:t=>({textContent:t})};
document.getElementById('dataset').textContent=scripts[0];
document.getElementById('metric').value='B8L2';document.getElementById('opacity').value='95';
document.getElementById('showPairs').checked=true;
const sandbox={console,document,window:{devicePixelRatio:1,addEventListener(){}}};
vm.createContext(sandbox);
vm.runInContext(scripts[1]+'\n;globalThis.T={DATA,selectImage,selectSample,filter,renderSampleGrid,state:()=>({active,sample})}',sandbox);
const T=sandbox.T;
assert.equal(E.imageList.children.length,6);assert.ok(strokes>0);
const hard=T.DATA.images.find(i=>i.samples.filter(s=>s.wild).length>=2);
assert.ok(hard);T.selectImage(hard.id);
const wild=hard.samples.find(s=>s.wild);T.selectSample(wild);
assert.equal(E.sampleSelect.value,wild.id);assert.equal(T.state().sample.id,wild.id);
assert.ok(E.sampleCaption.textContent.length>0);
const normal=hard.samples.find(s=>!s.wild);
if(normal){E.sampleType.value='normal';T.renderSampleGrid();assert.equal(T.state().sample.wild,false);}
E.difficulty.value='简单';T.filter();assert.ok(E.imageList.children.length>0);
assert.equal(T.state().active.difficulty,'简单');
E.search.value='__missing__';T.filter();assert.equal(E.empty.hidden,false);
E.search.value='';T.filter();assert.equal(E.detail.hidden,false);
"""
    subprocess.run(['node','-e',js,str(path)],check=True)


def test_embedded_json_parses(built):
    _, data, _ = built
    assert len(data['images']) == 6
    assert {i['difficulty'] for i in data['images']} == {'简单','中等','困难','单列','待修正GT','待复核'}
    assert data['summary']['difficulty_counts']['简单'] == 134


def test_limited_payload_shape(built):
    _, data, _ = built
    for image in data['images']:
        assert image['photo'].startswith('data:image/jpeg;base64,')
        assert image['models'] and image['samples']
        for sample in image['samples']:
            assert len(sample['points']) % 2 == 0 and len(sample['points']) >= 6
            assert bool(sample['types']) == sample['wild']
            assert sample['geometry'] == 'basic_checks_passed_not_certified'


def test_offline_no_cdn(built):
    _, _, html = built
    assert '<script src=' not in html and '<link rel="stylesheet"' not in html
    assert not re.search(r'\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(',html)
    assert 'cdn.' not in html.lower()


def test_stats_consistency(built):
    _, data, _ = built
    s=data['summary']
    assert s['difficulty_counts']=={'简单':134,'中等':37,'困难':38,'单列':45,'待修正GT':4,'待复核':1}
    for i in data['images']:
        assert i['real']+len(i['samples'])==35
        assert sum(s['wild'] for s in i['samples'])==i['wild']
    assert data['validation']['geometry_issues']==0
    assert data['replay']['passed'] is True
