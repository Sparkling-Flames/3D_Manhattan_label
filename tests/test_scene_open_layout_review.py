import copy
import re
import shutil
import subprocess

import pytest

from tools.thesis_main.analysis.build_scene_open_layout_review import assemble, render


def test_complete_review_preserves_source_and_discussions_and_checks_coverage(tmp_path):
    user = {'schema': 'scene_user_review_v2', 'saved_at': 'now', 'rows': [
        dict(image_id='b_a', building='b', split='valid', user_room='r1', user_type='卧室', user_note='<保留评论>'),
        dict(image_id='b_b', building='b', split='valid', user_room='r1', user_type='卧室', user_note='后续已讨论'),
    ]}
    manifest = dict(schema='scene_open_layout_manifest_v3', source_user=user, rows=[
        dict(image_id=u['image_id'], building='b', number=n, split='valid', path=f'data/{n}.png',
             source_user=u, owner='root', prior_reviews=[], discussion_refs=['B01'] if n == 2 else [],
             review_mode='carry_discussion' if n == 2 else 'new_original')
        for n, u in enumerate(user['rows'], 1)
    ])
    review = dict(image_id='b_a', building='b', number=1, review_mode='new_original',
                  view_basis='individual_original', coarse_type='卧室', functions=['睡眠'], focus='睡眠为主',
                  boundary='暂不归入', boundary_reason='门在远处', room_action='保留原组', related_numbers=[2],
                  room_note='保留候选', ambiguity_note='未见明确线索', comment_interpretation='保留原文',
                  needs_discussion=True, reason='固定床头及外窗')
    part = dict(schema='scene_open_layout_part_v3', reviewer='root', rows=[review])
    cross = dict(schema='scene_open_layout_cross_v3', rows=[dict(image_id='b_a', reviewer='other',
                 viewed_image_ids=['b_a'], verdict='部分支持', reason='仍有疑点', suggested_changes={})])
    discussions = {'b_b': dict(summary='暂不合并，不等于不同房', refs=['B01'])}
    before = copy.deepcopy((manifest, part, cross, discussions))
    result = assemble(manifest, [part], [cross], discussions)
    assert (manifest, part, cross, discussions) == before
    assert result['source_user'] == user
    assert result['rows'][1]['review'] is None
    assert result['rows'][1]['discussion'] == discussions['b_b']
    assert result['summary']['carried'] == 1 and result['summary']['reviewed'] == 1
    assert result['rows'][0]['cross_reviews'][0]['verdict'] == '部分支持'
    page = render(result)
    assert "control('coarse_type'" in page and 'data-field="note"' in page
    assert 'source_user' in page and '\\u003c保留评论>' in page
    for bad_parts, bad_cross, bad_discussions in [([], [cross], discussions), ([part, part], [cross], discussions),
                                               ([part], [], discussions), ([part], [cross], {})]:
        with pytest.raises(ValueError):
            assemble(manifest, bad_parts, bad_cross, bad_discussions)
    broken = copy.deepcopy(part)
    broken['rows'][0]['view_basis'] = 'large_panel_recheck'
    with pytest.raises(ValueError):
        assemble(manifest, [broken], [cross], discussions)
    # Exercise the page's actual JavaScript without opening a browser or local server.
    node = shutil.which('node')
    assert node, 'Node is required for the page save/export check'
    data, script = re.findall(r'<script[^>]*>(.*?)</script>', page, re.S)
    harness = r'''
const assert=require('node:assert/strict');
const elements=new Map(),listeners={},storage=new Map(),boxes=[];
const element=id=>{if(!elements.has(id))elements.set(id,{value:id==='scope'?'issues':'',textContent:'',innerHTML:'',dataset:{},addEventListener(){},insertAdjacentHTML(_,text){this.innerHTML+=text}});return elements.get(id)};
global.document={getElementById:element,querySelectorAll:()=>boxes,addEventListener:(type,f)=>listeners[type]=f};
global.localStorage={getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)};
global.window={scrollTo(){}};
'''
    # JSON is passed as a quoted JavaScript string, never interpolated into shell code.
    import json
    harness += 'element("audit").textContent=' + json.dumps(data) + ';\n' + script
    harness += r'''
assert.equal(makeExport().rows.length,2);
assert.deepEqual(makeExport().source_user,audit.source_user);
assert.ok(element('cards').innerHTML.includes('data-field="coarse_type"'));
assert.ok(element('cards').innerHTML.includes('&lt;保留评论&gt;'));
const controls=fields.map(field=>({dataset:{field},value:'',nextElementSibling:{textContent:''}}));
const box={dataset:{image:'b_a'},querySelectorAll:()=>controls};boxes.push(box);fill();
const coarse=controls.find(f=>f.dataset.field==='coarse_type');
assert.equal(coarse.value,'卧室');assert.equal(coarse.dataset.changed,'false');
assert.equal(makeExport().rows[0].current_classification.coarse_type,'卧室');
assert.deepEqual(makeExport().rows[0].changed_fields,[]);
assert.deepEqual(makeExport().rows[0].user_revision,{});
const target=controls.find(f=>f.dataset.field==='note');target.value='我的备注不能丢';target.closest=()=>box;
listeners.input({target});
assert.equal(edits.b_a.note,'我的备注不能丢');
assert.equal(edits.b_a.status,undefined);
assert.equal(target.dataset.changed,'true');
assert.equal(JSON.parse(storage.get(key)).b_a.note,'我的备注不能丢');
const status=controls.find(f=>f.dataset.field==='status');status.closest=()=>box;status.value='仍需讨论';listeners.input({target:status});
coarse.closest=()=>box;coarse.value='开放复合空间';listeners.input({target:coarse});
assert.equal(edits.b_a.status,'仍需讨论');assert.equal(coarse.dataset.changed,'true');
assert.equal(coarse.nextElementSibling.textContent,'已修改');
coarse.value='卧室';listeners.input({target:coarse});
assert.equal(coarse.dataset.changed,'false');assert.equal(edits.b_a.status,'仍需讨论');
// An explicitly cleared value must not be replaced by its prefill, even after import.
coarse.value='';listeners.input({target:coarse});
assert.equal(makeExport().rows[0].current_classification.coarse_type,'');
const out=makeExport();assert.equal(out.rows[0].user_revision.status,'仍需讨论');
assert.equal(out.form_version,2);assert.equal(out.rows[0].prefill.coarse_type,'卧室');
assert.ok(out.rows[0].changed_fields.includes('coarse_type'));
assert.equal(readImport(out).b_a.coarse_type,'');
assert.deepEqual(out.rows[1].user_revision,{});
assert.deepEqual(out.rows[1].discussion.summary,'暂不合并，不等于不同房');
assert.equal(readImport(out).b_a.note,'我的备注不能丢');
const legacy=structuredClone(out);delete legacy.form_version;
for(const r of legacy.rows){delete r.prefill;delete r.current_classification;delete r.changed_fields}
edits=readImport(legacy);fill();assert.equal(coarse.value,'');assert.equal(coarse.dataset.changed,'true');
const adopt={dataset:{adopt:'b_a'}};
listeners.click({target:{closest:selector=>selector==='[data-adopt]'?adopt:null}});
assert.equal(coarse.value,'卧室');assert.equal(coarse.dataset.changed,'false');
assert.equal(edits.b_a.status,'仍需讨论');assert.equal(edits.b_a.note,'我的备注不能丢');
status.value='已确认';listeners.input({target:status});
coarse.value='卫浴';listeners.input({target:coarse});assert.equal(edits.b_a.status,'已确认');
const bad=structuredClone(out);bad.rows[1].image_id='b_a';assert.throws(()=>readImport(bad));
assert.equal(edits.b_a.note,'我的备注不能丢');
scope.value='all';draw();assert.ok(element('cards').innerHTML.includes('沿用已讨论决定'));
scope.value='carry';assert.equal(selected().length,1);
assert.throws(()=>validateEdits({'unknown':{note:'x'}}));
assert.throws(()=>validateEdits({'b_a':{unexpected:'x'}}));
console.log('page input/save/export/import/filter checks passed');
'''
    check = tmp_path / 'page_check.cjs'
    check.write_text(harness, encoding='utf-8')
    run = subprocess.run([node, str(check)], capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == 0, run.stdout + run.stderr
    broken = copy.deepcopy(part)
    broken['rows'][0]['related_numbers'] = [99]
    with pytest.raises(ValueError):
        assemble(manifest, [broken], [cross], discussions)
