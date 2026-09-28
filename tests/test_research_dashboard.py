"""发布边界：测试数据仅在 tmp_path 中生成，绝不接入导师包。"""
import copy
import json
from pathlib import Path

import pytest


def test_coverage_paging_colors_and_scale():
    """Run the actual chart renderer against a Plotly/DOM stub, without a browser."""
    import subprocess
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('tools/thesis_main/analysis/research_dashboard/dashboard.js','utf8');
const nodes=[],plots=[];
function el(tag,text,cls){const n={tag,text,cls,children:[],append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=xs},remove(){}};nodes.push(n);return n;}
const context={el,button:(text,fn)=>Object.assign(el('button',text),{onclick:fn}),palette:['green','amber','blue'],escapePlot:String,shown:String,states:{ready:'ready'},table(){},empty(){},fatal(e){throw e},Plotly:{react(p,t,l){plots.push({t,l});return Promise.resolve()}}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function drawChart('),source.indexOf('function renderView(')),context);
const rows=Array.from({length:49},(_,i)=>({x:'image-'+i,image_id:'i'+i,value:i===48?25:3,series:i<24?'Manual':'Semi',status:'ready',member_ids:[]}));
const chart={id:'coverage',kind:'bar',title:'coverage',group_by_image:false,rows,x_label:'image',x_unit:'',y_label:'count',unit:'份'};
context.drawChart(el('div'),chart,{});
assert.equal(plots[0].t[0].x.length,24);assert.equal(plots[0].t[0].marker.color,'#55755a');
assert.equal(plots[0].l.xaxis.tickvals.length,24);assert.equal(plots[0].l.yaxis.range[0],0);assert.equal(plots[0].l.yaxis.dtick,5);
const paging=nodes.find(n=>n.cls==='zoom-range');assert.equal(paging.children[0].disabled,true);
paging.children[2].onclick();assert.equal(plots[1].t[0].customdata[0][0],'i24');assert.equal(plots[1].t[0].marker.color,'#7b91a0');
assert.deepEqual(plots[1].l.yaxis.range,plots[0].l.yaxis.range);
paging.children[2].onclick();assert.equal(plots[2].t[0].x.length,1);assert.equal(paging.children[2].disabled,true);
paging.children[0].onclick();assert.equal(plots[3].t[0].x.length,24);assert.equal(chart.rows.length,49);
context.drawChart(el('div'),{...chart,id:'another-chart'},{});assert.equal(plots[4].t.flatMap(t=>t.x).length,49);
"""
    subprocess.run(["node", "-e", script], check=True, cwd=Path(__file__).resolve().parents[1])


def test_large_table_search_and_paging_without_browser():
    import subprocess
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('tools/thesis_main/analysis/research_dashboard/dashboard.js','utf8'),nodes=[];
function el(tag,text,cls){const n={tag,text,cls,children:[],classList:{add(){}},setAttribute(){},append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=xs}};nodes.push(n);return n;}
const context={el,button:(text,fn)=>Object.assign(el('button',text),{onclick:fn}),shown:String,states:{},openCase(){}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function table('),source.indexOf('function sourceText(')),context);
context.table(el('div'),[{key:'id',label:'ID'}],Array.from({length:205},(_,id)=>({id})),{});
const body=nodes.find(n=>n.tag==='tbody'),ctl=nodes.find(n=>n.cls==='table-controls');
assert.equal(body.children.length,100);assert.equal(ctl.children[1].disabled,true);
ctl.children[3].onclick();assert.equal(body.children[0].children[0].textContent,'100');
ctl.children[3].onclick();assert.equal(body.children.length,5);assert.equal(ctl.children[3].disabled,true);
ctl.children[0].value='204';ctl.children[0].oninput();assert.equal(body.children.length,1);assert.equal(body.children[0].children[0].textContent,'204');
ctl.children[0].value='missing';ctl.children[0].oninput();assert.equal(body.children.length,0);assert.equal(ctl.children[3].disabled,true);
ctl.children[0].value='';ctl.children[0].oninput();assert.equal(body.children.length,100);
"""
    subprocess.run(["node", "-e", script], check=True, cwd=Path(__file__).resolve().parents[1])

def test_replay_table_selects_one_rule_without_paging():
    import subprocess
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('tools/thesis_main/analysis/research_dashboard/dashboard.js','utf8');
function el(tag,text,cls){return {tag,text,cls,value:'',children:[],classList:{add(){}},setAttribute(){},append(...xs){this.children.push(...xs)},replaceChildren(...xs){this.children=xs}}}
const context={el,option:(value,text)=>Object.assign(el('option',text),{value}),button:(text,fn)=>Object.assign(el('button',text),{onclick:fn}),shown:x=>x==null?'—':String(x),states:{},openCase(){}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function table('),source.indexOf('function sourceText(')),context);
const rows=[];for(let i=0;i<110;i++)for(const tail_fraction of [.1,.2])for(const h of [3,5])rows.push({code:'image-'+i,J:3,m:2,tail_fraction,h,N:8,success_fraction:null,observation_status:'后续观察人数不足'});
const columns=Object.keys(rows[0]).map(key=>({key,label:key})),parent=el('div');context.table(parent,columns,rows,{});
const [controls,result]=parent.children,[rule,h,search,label,count]=controls.children;
const body=()=>result.children[0].children[0].children[1];
assert.equal(body().children.length,110);assert.equal(body().children[0].children.length,4);
assert.equal(body().children[0].children[2].textContent,'—');
rule.value=JSON.stringify([3,2,.2]);rule.onchange();h.value='5';h.onchange();
label.children[0].checked=true;label.children[0].onchange();
assert.equal(body().children.length,110);assert.equal(body().children[0].children.length,columns.length);
assert.equal(body().children[0].children[3].textContent,'0.2');assert.equal(body().children[0].children[4].textContent,'5');
search.value='image-109';search.oninput();assert.equal(body().children.length,1);
search.value='missing';search.oninput();assert.equal(body().children.length,0);
search.value='';search.oninput();assert.equal(body().children.length,110);assert.equal(rows.length,440);
"""
    subprocess.run(["node", "-e", script], check=True, cwd=Path(__file__).resolve().parents[1])


from tools.thesis_main.analysis.research_dashboard.build import build, validate


def test_unavailable_module_does_not_expand_other_versions():
    import subprocess
    script = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('tools/thesis_main/analysis/research_dashboard/dashboard.js','utf8'),buttons=[];
function el(){return {children:[],append(...x){this.children.push(...x)}}}
const mod=status=>({status,charts:[],tables:[],metrics:[],note:'未接入'});
const current={id:'a',version:'current',condition:'current-condition',method:'affinity',modules:{people:mod('not_computed')}};
const baseline={...current,id:'b',method:'complete',modules:{people:mod('ready')}};
const history=Array.from({length:600},(_,i)=>({...baseline,id:'h'+i,version:'history',classification:'class'+i}));
const context={el,button:(text,fn)=>{const b={text,onclick:fn};buttons.push(b);return b},data:{versions:[{id:'current',label:'current'},{id:'history',label:'history'}],views:[current,baseline,...history]},active:'people',label:(k,v)=>v,context:()=>'',metricCards(){},empty(){},states:{not_computed:'未计算'},modules:{people:{chart:'人员',intro:'介绍'}}};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function renderView('),source.indexOf('function imageList(')),context);
context.renderView(el(),current,'');
assert.equal(buttons.filter(b=>b.text.startsWith('查看 ')).length,1);
assert.equal(buttons.filter(b=>b.text.startsWith('切换：')).length,1);
const overview={...baseline,id:'summary',version:'history-20260921-pre-review',method:'old-complete',classification:'old-classification-overview'};
context.data.views.push(overview);
context.dims=['version','condition','method','classification','building','room','image'];context.render=()=>{};context.comparison='old';
buttons.length=0;context.renderView(el(),current,'');
buttons.find(b=>b.text.startsWith('人员分类对照')).onclick();
assert.equal(context.scope.version,'history-20260921-pre-review');
assert.equal(context.scope.classification,'old-classification-overview');
assert.equal(context.scope.method,'old-complete');assert.equal(context.comparison,'');
const shared={...baseline,id:'shared',version:'shared_x_reanalysis_20260922_v1',condition:'raw',classification:'unclassified',building:'',room:'',image:''};
const example={...shared,id:'shared-example',building:'b',room:'r',image:'q9vSo1VnCiC_c421f07780004647a7198c4ac5371e8a'};
context.data.views.push(shared,example);
buttons.length=0;context.renderView(el(),current,'');
buttons.find(b=>b.text.startsWith('共享x重分析')).onclick();
assert.equal(context.scope.version,shared.version);
buttons.length=0;context.renderView(el(),shared,'');
buttons.find(b=>b.text.startsWith('主簇与零散尾部')).onclick();
assert.equal(context.scope.image,example.image);assert.equal(context.active,'stability');
"""
    subprocess.run(["node", "-e", script], check=True, cwd=Path(__file__).resolve().parents[1])


def sample(release="test-a"):
    module = {"status": "ready", "note": "接口测试", "metrics": [], "charts": [], "tables": []}
    modules = {key: copy.deepcopy(module) for key in
               ["overview", "annotation", "stability", "people", "rooms", "features"]}
    modules["overview"]["metrics"] = [{"label": "实际人数", "value": 2, "unit": "人",
        "status": "ready", "definition": "此切片独立参与者", "denominator": None,
        "source_ids": ["s"], "member_ids": ["p1", "p2"]}]
    modules["stability"]["charts"] = [{"id": "curve", "title": "接口曲线", "kind": "line",
        "x_label": "人数", "x_unit": "人", "y_label": "支持比例", "unit": "%",
        "definition": "由分析方提供", "rows": [
            {"x": 1, "value": None, "status": "insufficient", "series": "簇一", "image_id": "i",
             "denominator": 1, "numerator": None, "member_ids": ["p1"], "source_ids": ["s"]},
            {"x": 2, "value": 50, "status": "ready", "series": "簇一", "image_id": "i",
             "denominator": 2, "numerator": 1, "member_ids": ["p1", "p2"], "source_ids": ["s"]}]}]
    return {"schema_version": "research_dashboard_v1", "release": release,
        "versions": [{"id": release, "label": release, "description": "合成接口测试"}],
        "methods": [{"id": "m", "label": "测试方法", "description": "测试"}],
        "classifications": [{"id": "c", "label": "测试分类", "description": "测试"}],
        "sources": [{"id": "s", "label": "测试来源", "description": "仅用于测试"}],
        "participants": [{"id": "p1", "label": "甲"}, {"id": "p2", "label": "乙"}],
        "images": [{"id": "i", "building": "b", "room": "r", "scene": "场景", "source_ids": ["s"]}],
        "cases": [], "views": [{"id": "all", "version": release, "condition": "条件一",
        "method": "m", "classification": "c", "building": "", "room": "", "image": "",
        "image_ids": ["i"], "modules": modules}]}


def test_two_releases_and_empty_package(tmp_path):
    for release in ["test-a", "test-b"]:
        data = sample(release)
        validate(data)
        source = tmp_path / (release + ".json")
        source.write_text(json.dumps(data), encoding="utf-8")
        manifest = {"schema_version": "research_dashboard_manifest_v1", "release": release,
                    "results": source.name, "selected_cases": []}
        out = tmp_path / release
        build(manifest, tmp_path, out)
        payload = (out / "assets/data.js").read_text(encoding="utf-8")
        assert release in payload
        assert ("test-b" if release == "test-a" else "test-a") not in payload
        assert "null" in payload and (out / "index.html").exists()
        assert (out.with_suffix(".zip")).exists()
        assert "https://cdn" not in (out / "index.html").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        build(manifest, tmp_path, out)


@pytest.mark.parametrize("change,match", [
    (lambda d: d["views"][0].update(version="wrong"), "version"),
    (lambda d: d["views"].append(copy.deepcopy(d["views"][0])), "duplicate"),
    (lambda d: d["views"][0]["modules"]["overview"]["metrics"][0].update(value=None), "ready"),
    (lambda d: d["views"][0]["modules"]["overview"]["metrics"][0].update(member_ids=["ghost"]), "member"),
    (lambda d: d["views"][0]["modules"]["stability"]["charts"][0]["rows"][0].update(value=0), "insufficient"),
    (lambda d: d.update(unexpected=[]), "unknown"),
    (lambda d: d["views"][0]["modules"]["overview"]["metrics"][0].pop("definition"), "missing fields"),
    (lambda d: d["sources"][0].update(description="https://example.com/input.json"), "remote"),
    (lambda d: d["views"][0]["modules"]["overview"]["metrics"][0].update(value=float("nan")), "nonfinite"),
])
def test_reject_drift_and_mismatch(change, match):
    data = sample()
    change(data)
    with pytest.raises(ValueError, match=match):
        validate(data)


def with_case(data):
    # Synthetic geometry is an interface fixture, never a research result.
    from tools.label_studio.panorama_studio.geometry import analyze, project_pixel
    layout = {"width": 1024, "height": 512, "coordinate_mode": "pixels", "ordered_pairs": []}
    for n, (x, z) in enumerate([(-2, -3), (3, -3), (3, 2), (-2, 2)]):
        layout["ordered_pairs"].append({"source_pair_id": f"pair-{n}",
            "top": dict(zip(("x", "y"), project_pixel([x, 1.3, z], 1024, 512))),
            "bottom": dict(zip(("x", "y"), project_pixel([x, -1, z], 1024, 512)))})
    geometry = analyze(layout)
    variant = {"id": "raw", "name": "测试点集", "kind": "original", "pointset_version": "points-1",
        "member_ids": ["p1"], "source_ids": ["s"], "cluster_ids": ["cluster-1"],
        "pairs": geometry["pairs"], "connections": [[f"pair-{i}", f"pair-{(i+1)%4}"] for i in range(4)],
        "geometry": geometry, "geometry_pointset_version": "points-1"}
    unavailable = copy.deepcopy(variant)
    unavailable.update(id="perturbation", name="测试扰动（未提供3D）", kind="perturbation")
    del unavailable["geometry"]
    del unavailable["geometry_pointset_version"]
    unavailable["pairs"][0].update(top=[1020, 100], bottom=[4, 400])
    data["cases"] = [{"id": "case-i", "image_id": "i", "version": data["release"], "condition": "条件一",
        "method": "m", "classification": "c", "pointset_version": "points-1", "source_ids": ["s"],
        "width": 1024, "height": 512, "variants": [variant, unavailable]}]
    return data


def test_case_versions_and_release_boundary(tmp_path):
    data = with_case(sample())
    validate(data)
    bad = copy.deepcopy(data)
    bad["cases"][0]["variants"][0]["geometry_pointset_version"] = "stale"
    with pytest.raises(ValueError, match="pointset version"):
        validate(bad)
    bad = copy.deepcopy(data)
    bad["cases"][0]["variants"][0]["pairs"][0]["display_index"] = 7
    with pytest.raises(ValueError, match="numbering"):
        validate(bad)
    source = tmp_path / "results.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    manifest = {"schema_version": "research_dashboard_manifest_v1", "release": data["release"],
                "results": source.name, "selected_cases": []}
    payload = build(manifest, tmp_path, tmp_path / "no-images")
    assert not payload["cases"] and payload["images"] and payload["views"]
    assert "pair-0" not in (tmp_path / "no-images/assets/data.js").read_text(encoding="utf-8")
    manifest["release"] = "wrong"
    with pytest.raises(ValueError, match="release mismatch"):
        build(manifest, tmp_path, tmp_path / "wrong")
    assert not (tmp_path / "wrong").exists()


def browser_fixtures(folder):
    """Two complete replaceable packages, created only in an explicit QA directory."""
    from PIL import Image
    folder.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 512), (135, 155, 130)).save(folder / "fixture.png")
    for release in ["test-a", "test-b"]:
        data = with_case(sample(release))
        data["images"].append({"id": "j", "building": "b", "room": "r", "scene": "场景", "source_ids": ["s"]})
        data["views"][0]["image_ids"].append("j")
        data["versions"].append({"id": "prior-" + release, "label": "另一测试版本", "description": "仅用于对照测试"})
        prior = copy.deepcopy(data["views"][0])
        prior.update(id="prior", version="prior-" + release)
        prior["modules"]["overview"]["metrics"][0]["value"] = 9
        data["views"].append(prior)
        image_view = copy.deepcopy(data["views"][0])
        image_view.update(id="image", building="b", room="r", image="i", image_ids=["i"])
        data["views"].append(image_view)
        if release == "test-b":
            data["methods"][0].update(id="new-method", label="另一套方法")
            data["classifications"][0].update(id="new-classification", label="另一套分类")
            for v in data["views"]:
                v.update(method="new-method", classification="new-classification")
                v["modules"]["overview"]["metrics"][0]["value"] = 3
                v["modules"]["stability"]["charts"][0]["rows"][1].update(value=100, numerator=2)
            for c in data["cases"]:
                c.update(method="new-method", classification="new-classification")
        for v in data["views"]:
            v["modules"]["features"].update(status="not_computed", note="待研究：未计算")
            for status in ["not_computed", "not_met", "unresolved"]:
                row = copy.deepcopy(v["modules"]["stability"]["charts"][0]["rows"][0])
                row.update(x=len(v["modules"]["stability"]["charts"][0]["rows"])+1, status=status)
                v["modules"]["stability"]["charts"][0]["rows"].append(row)
            v["modules"]["people"]["tables"] = [{"id": "replay", "title": "进入顺序", "replay": True,
                "columns": [{"key": k, "label": k, "unit": ""} for k in ["step", "image_id", "member_ids", "source_ids"]],
                "rows": [{"step": 1, "image_id": "i", "member_ids": ["p2"], "source_ids": ["s"]},
                         {"step": 2, "image_id": "i", "member_ids": ["p2", "p1"], "source_ids": ["s"]}]}]
        path = folder / (release + ".json")
        path.write_text(json.dumps(data), encoding="utf-8")
        manifest = {"schema_version": "research_dashboard_manifest_v1", "release": release, "results": path.name,
                    "selected_cases": [{"case_id": "case-i", "image": "fixture.png"}]}
        build(manifest, folder, folder / release)
    manifest = {"schema_version": "research_dashboard_manifest_v1", "release": "empty-qa", "results": None, "selected_cases": []}
    build(manifest, folder, folder / "empty")


if __name__ == "__main__":
    import sys
    browser_fixtures(Path(sys.argv[1]))
