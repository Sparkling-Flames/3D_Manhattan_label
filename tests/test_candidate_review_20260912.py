from tools.thesis_main.analysis.audit_candidate_review_20260912 import coverage
from pathlib import Path
import json


def test_history_exit_and_model_exposure_are_different_budget_constraints():
    rows = [dict(worker_id=11, unassisted_manual_included=True, assistance_exposure='none'),
            dict(worker_id=1, unassisted_manual_included=True, assistance_exposure='none'),
            dict(worker_id=2, unassisted_manual_included=False, assistance_exposure='model_preannotation'),
            dict(worker_id=3, unassisted_manual_included=False, assistance_exposure='none')]
    c = coverage(rows, {1, 2, 3, 4})
    assert c['manual_included'] == 2  # W11历史仍在。
    assert c['manual_active19'] == 1
    assert c['clean_workers'] == [4]  # Semi或无效旧作答都不是未看过。
    assert c['max_pooled_manual'] == 3 and c['max_active19_manual'] == 2
    assert coverage(rows + [rows[0]], {1, 2, 3, 4}) == c


def test_room_batch_review_and_legacy_import(tmp_path):
    from playwright.sync_api import sync_playwright

    out = Path(__file__).resolve().parents[1] / 'analysis_results/candidate_review_20260912_v2'
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100})
        errors, dialogs = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: (dialogs.append(d.message), d.dismiss()))
        page.route('https://**', lambda r: r.abort())
        page.goto((out / '候选图片审查台.html').as_uri())
        assert page.locator('.card').count() == 112 and page.locator('.group').count() == 22
        assert page.get_by_role('link', name='GitHub文件页').count() == 0
        assert '相似场景标注与跨房间预测' in page.locator('.legend').inner_text()
        group = page.locator('#G179')
        group.locator('[data-group-key=adoption]').select_option('建议采用')
        group.locator('[data-purpose="同房间收敛预测"]').check()
        group.locator('[data-purpose="相似场景标注与跨房间预测"]').check()
        group.locator('[data-group-key=note]').fill('同房08与65作来源；门口范围待核对')
        source = group.locator('.card').nth(0)
        source.locator('[data-key=selection]').select_option('采用')
        source.locator('[data-key=collection]').select_option('仅复用历史')
        target = group.locator('.card').nth(1)
        target.locator('[data-key=selection]').select_option('采用')
        target.locator('[data-key=collection]').select_option('需要新增标注')
        target.locator('[data-key=target_band]').select_option('9–15人')
        target.locator('textarea').fill('保留范围差异')
        assert '新增人图 9–15' in page.locator('#stats').inner_text()
        assert '新增 9–15' in group.locator('.group-summary').inner_text()
        panel = page.locator('#warningPanel')
        assert not panel.evaluate('(e)=>e.open')
        assert not page.locator('#warning').is_visible()
        assert page.locator('#warningSummary').inner_text() == page.evaluate("'提示（'+document.querySelector('#warning').textContent.split('\\n').filter(Boolean).length+'条，点击展开／收起）'")
        page.locator('#warningSummary').click()
        assert page.locator('#warning').is_visible()
        page.locator('#warningSummary').click()
        assert not page.locator('#warning').is_visible()
        # 审图不固定预测身份；旧role字段仅为兼容记录。
        assert page.locator('[data-key=role]').count() == 0
        assert '尚未同时选定来源和目标' not in page.locator('#warning').text_content()
        assert '新增人图 9–15' in page.locator('#stats').inner_text()
        target.locator('[data-key=collection]').select_option('待定')
        assert '预算不完整' in page.locator('#warning').text_content()
        target.locator('[data-key=collection]').select_option('需要新增标注')
        # 有条件采用的组单列，不静默并入拟采用预算。
        group.locator('[data-group-key=adoption]').select_option('满足条件后采用')
        assert '新增人图 0' in page.locator('#stats').inner_text()
        assert '条件组 1' in page.locator('#stats').inner_text()
        group.locator('[data-group-key=adoption]').select_option('建议采用')
        target.locator('[data-key=selection]').select_option('备选')
        assert '新增人图 0' in page.locator('#stats').inner_text()
        target.locator('[data-key=selection]').select_option('采用')
        target.locator('[data-key=target_band]').select_option('21人及以上')
        assert '新增人图 21以上' in page.locator('#stats').inner_text()
        assert '不可达' in page.locator('#warning').text_content()
        target.locator('[data-key=target_band]').select_option('9–15人')
        page.locator('#basis').select_option('active19')
        page.locator('#budget').fill('380')
        page.locator('#budget').press('Tab')
        with page.expect_download() as info:
            page.locator('#export').click()
        exported = json.loads(Path(info.value.path()).read_text(encoding='utf-8'))
        assert exported['schema'] == 'candidate_review_user_decisions_v5'
        assert len(exported['groups']) == 22 and len(exported['decisions']) == 112
        assert exported['groups'][0]['adoption'] == '建议采用'
        assert len(exported['groups'][0]['purposes']) == 2
        page.reload()
        assert page.evaluate('exportData().groups') == exported['groups']
        assert page.evaluate('exportData().decisions') == exported['decisions']
        assert page.locator('[data-key=difficulty]').first.locator('option').all_text_contents() == ['未定', '简单', '中等', '困难']
        for level in ['简单', '中等', '困难']:
            target.locator('[data-key=difficulty]').select_option(level)
            assert '新增人图 9–15' in page.locator('#stats').inner_text()
        # 旧版非简单不能擅自映射为中等或困难；原记录保留。
        v4 = json.loads(json.dumps(exported))
        v4['schema'] = 'candidate_review_user_decisions_v4'
        for item in v4['decisions']:
            item['role'] = '可替代视点'
            item['difficulty'] = '非简单'
        migrated4 = page.evaluate('(v)=>validateImport(v)', v4)
        first4 = next(iter(migrated4['images'].values()))
        assert first4['selection'] == '备选' and first4['role'] == '待定'
        assert first4['difficulty'] == '未定' and first4['legacy_review']['difficulty'] == '非简单'
        bad = json.loads(json.dumps(exported))
        bad['groups'][0]['note'] = '不得部分覆盖'
        bad['decisions'][-1]['role'] = '非法用途'
        f = tmp_path / 'bad.json'
        f.write_text(json.dumps(bad), encoding='utf-8')
        page.locator('#import').set_input_files(str(f))
        page.wait_for_timeout(150)
        assert dialogs and '导入失败' in dialogs[-1]
        assert page.evaluate('exportData().groups') == exported['groups']
        # v3旧优先级不转换成房间采用结论，原决定完整保留。
        old = json.loads(json.dumps(exported))
        old['schema'] = 'candidate_review_user_decisions_v3'
        old.pop('groups')
        for r in old['decisions']:
            r.pop('role')
            r.pop('legacy_review')
            r['difficulty'] = '非简单'
            r['decision'] = '候选纳入'
            r['priority'] = 'P1 首批优先'
            r['legacy_target'] = 10
        f = tmp_path / 'old.json'
        f.write_text(json.dumps(old), encoding='utf-8')
        page.locator('#import').set_input_files(str(f))
        page.wait_for_function("exportData().groups.every(g=>g.adoption==='待定')")
        migrated = page.evaluate('exportData()')
        assert migrated['decisions'][1]['role'] == '待定'
        assert migrated['decisions'][1]['legacy_review']['priority'] == 'P1 首批优先'
        assert migrated['decisions'][1]['note'] == '保留范围差异'
        assert '新增人图 0' in page.locator('#stats').inner_text()
        for version in ['v1', 'v2']:
            numeric = json.loads(json.dumps(old))
            numeric['schema'] = 'candidate_review_user_decisions_' + version
            for r in numeric['decisions']:
                r['target'] = 10
                r.pop('target_band')
            restored = page.evaluate('(v)=>validateImport(v)', numeric)
            assert restored['images'][old['decisions'][1]['image_id']]['target_band'] == '9–15人'
            assert restored['groups'] == {}
        page.locator('#adoptionFilter').select_option('待定')
        assert page.locator('.group').count() == 22
        # 同一图片重复引用不加预算，矛盾用途拒绝冒算。
        assert page.evaluate("""() => {
          const r=D.images[1], s={role:'预测检验图',selection:'采用',collection:'需要新增标注',target_band:'9–15人'};
          return sumImages([{r,s},{r,s}],'pooled').lo;
        }""") == 9
        assert page.evaluate("needRange({manual_included:7},{target_band:'9–15人'},'pooled')") == [2,8]
        assert page.evaluate('[0,8,9,15,16,20,21].map(bandFor)') == [
            '未定','0–8人','9–15人','9–15人','16–20人','16–20人','21人及以上']
        page.evaluate("state={};groupState={};document.querySelector('#budget').value='';document.querySelector('#basis').value='pooled';document.querySelector('#adoptionFilter').value='';render();")
        page.evaluate("document.querySelectorAll('.pano').forEach(i=>i.loading='eager')")
        page.wait_for_function("[...document.querySelectorAll('.pano')].every(i=>i.complete&&i.naturalWidth>0)")
        page.screenshot(path=str(out / 'results/审查页预览.png'))
        page.locator('.card').nth(1).locator('.edit').scroll_into_view_if_needed()
        page.screenshot(path=str(out / 'results/逐图填写预览.png'))
        assert not errors
        result = dict(groups=22, cards=112, local_images_loaded=112,
                      group_adoption_and_purposes='passed', conditional_budget_separate='passed',
                      per_image_roles_and_ranges='passed', duplicate_image_budget='passed',
                      role_selection_collection_independent='passed', expected_difficulty_three_levels='passed',
                      v4_non_simple_not_guessed='passed',
                      roundtrip_and_atomic_import='passed', old_priority_preserved_not_adopted='passed',
                      javascript_errors=errors, note='测试选择，不是用户审查数据。')
        (out / 'results/browser_qa.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        browser.close()
