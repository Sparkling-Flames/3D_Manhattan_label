import copy
import json
import re
import shutil
import subprocess

import pytest

from tools.thesis_main.analysis.build_same_room_pair_review import assemble, render


def test_pair_coverage_source_preservation_and_edit_roundtrip(tmp_path):
    raw = [dict(image_id=f'b_{n}', building='b', number=n, split='valid', path=f'data/{n}.png') for n in (1, 2)]
    user = dict(schema='scene_open_layout_user_review_v3', saved_at='now', rows=[
        dict(**r, source_user={'user_note': '<原评论>'}, current_classification={'boundary': '交界候选', 'note': ''}, discussion=None) for r in raw])
    part = dict(schema='same_room_research_pairs_v1', reviewer='a', buildings=['b'], images=[
        dict(image_id=r['image_id'], building='b', number=r['number'], view_basis='individual_original',
             main_visual_space='卧室', expected_annotation_extent='床区围合', ambiguity_and_information='床遮墙脚',
             candidate_numbers=[3-r['number']], note='图像判断') for r in raw], pairs=[
        dict(building='b', a=1, b=2, physical_same='支持', main_visual_alignment='一致',
             extent_alignment='预期相近', difficulty_similarity='预期相近', decision='优先候选', evidence='同一窗墙', differences='床侧不同')])
    before = copy.deepcopy((user, part))
    result = assemble(user, raw, [part])
    assert (user, part) == before
    assert result['source_user'] == user
    assert result['summary']['images'] == 2 and result['summary']['pairs'] == 1
    for broken in [[], [part, part]]:
        with pytest.raises(ValueError):
            assemble(user, raw, broken)
    wrong = copy.deepcopy(part)
    wrong['pairs'][0]['physical_same'] = '待定'
    with pytest.raises(ValueError):
        assemble(user, raw, [wrong])
    wrong = copy.deepcopy(part)
    wrong['images'][0]['candidate_numbers'] = [99]
    with pytest.raises(ValueError):
        assemble(user, raw, [wrong])
    page = render(result)
    data, script = re.findall(r'<script[^>]*>(.*?)</script>', page, re.S)
    harness = r'''
const assert=require('node:assert/strict'), elements=new Map(),listeners={},boxes=[];
const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',addEventListener(){},insertAdjacentHTML(_,s){this.innerHTML+=s}});return elements.get(id)};
global.document={getElementById:el,querySelectorAll:()=>boxes,addEventListener:(k,f)=>listeners[k]=f};
global.localStorage={getItem:()=>null,setItem(){}};global.window={scrollTo(){}};
'''
    harness += 'el("audit").textContent=' + json.dumps(data) + ';\n' + script
    harness += r'''
const id=pairs[0].pair_id;
assert.deepEqual(makeExport().source_user,audit.source_user);
assert.equal(makeExport().pairs[0].current.decision,'优先候选');
assert.deepEqual(makeExport().pairs[0].changed_fields,[]);
assert.ok(el('cards').innerHTML.includes('&lt;原评论&gt;'));
const gid=groups[0].group_id;
assert.equal((el('cards').innerHTML.match(/<fieldset /g)||[]).length,1);
assert.ok(!el('cards').innerHTML.includes('data-pair='));
const controls=fields.map(f=>({dataset:{field:f},value:'',nextElementSibling:{textContent:''}}));
const box={dataset:{group:gid},querySelectorAll:()=>controls};boxes.push(box);fill();
const note=controls.find(f=>f.dataset.field==='note');note.closest=()=>box;note.value='整组评论';listeners.input({target:note});
assert.equal(note.dataset.changed,'true');assert.equal(groupCurrent(gid).status,'');
groupEdits[gid].status='已确认';note.value='改组评论';listeners.input({target:note});assert.equal(groupCurrent(gid).status,'已确认');
note.value='';listeners.input({target:note});assert.equal(note.dataset.changed,'false');
assert.deepEqual(readGroups(makeExport(),edits),groupEdits);
assert.deepEqual(makeExport().pairs[0].user_revision,{});
groupEdits[gid].difficulty_similarity='可能出现小幅歧义';
assert.equal(readGroups(makeExport(),edits)[gid].difficulty_similarity,'可能出现小幅歧义');
const missing=makeExport();missing.group_reviews=[];assert.throws(()=>readGroups(missing,edits));
const altered=makeExport();altered.group_reviews[0].image_ids=['bad'];assert.throws(()=>readGroups(altered,edits));
assert.equal(seedNotes({[id]:{note:'保留旧评论'}})[gid].note,'此前 1/2：保留旧评论');
const bad=makeExport();bad.source_user.rows[0].current_classification.boundary='篡改';
assert.throws(()=>readImport(bad));assert.equal(audit.source_user.rows[0].current_classification.boundary,'交界候选');
assert.throws(()=>validateEdits({[id]:{boundary:'否'}}));
assert.throws(()=>validateEdits({[id]:{decision:'不存在的选项'}}));
edits[id]={difficulty_similarity:'可能出现小幅歧义'};
assert.equal(readImport(makeExport())[id].difficulty_similarity,'可能出现小幅歧义');
const chain=[{pair_id:'a',image_ids:['1','2'],physical_same:'支持'},
 {pair_id:'b',image_ids:['2','3'],physical_same:'支持'},
 {pair_id:'c',image_ids:['1','4'],physical_same:'不支持'}];
const chainGroups=groupPairs(chain);
assert.equal(chainGroups.length,2);assert.equal(chainGroups[0].image_ids.length,3);
assert.equal(chainGroups[0].pairs.length,2);assert.equal(chain.length,3);
// Presentation groups must not invent the unreviewed 1-3 relationship.
assert.deepEqual(chainGroups[0].pairs.map(p=>p.pair_id),['a','b']);
const inconsistent=makeExport();inconsistent.pairs[0].current.decision='不支持';assert.throws(()=>readImport(inconsistent));
console.log('pair review save/import/source preservation checks passed');
'''
    path = tmp_path / 'pair_check.cjs'
    path.write_text(harness, encoding='utf-8')
    node = shutil.which('node')
    assert node, 'Node is required for review-page checks'
    run = subprocess.run([node, str(path)], capture_output=True, text=True, encoding='utf-8')
    assert run.returncode == 0, run.stdout + run.stderr
