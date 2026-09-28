from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
def run():
    checks={}
    with sync_playwright() as p:
        b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content((ROOT/'report/RESULTS_BROWSER.html').read_text(),wait_until='load')
        assert page.locator('#unit option').count()==239;checks['units']=239
        index=page.evaluate("DATA.groups.findIndex(g=>g.code==='uNb9QFRL6hY-21'&&g.condition==='manual')")
        page.select_option('#unit',str(index));page.select_option('#a','8178591994d42ce3');page.select_option('#b','a4e0cac5adec2e1e');text=page.locator('#distance').inner_text();assert '32.50009' in text and '不同组' in text;checks['uNb21_original_pair_display']=text
        for view in ['split_cyclic_6','split_cyclic_9','split_cyclic_12','split_fixed_9','bound_cyclic_9','ospa_gate_6']:
            page.select_option('#view',view);assert page.locator('#members tbody tr').count()==24
        checks['six_configuration_switches']=True
        page.fill('#filter','q9vSo1VnCiC-13');assert page.locator('#unit option').count()>=1;checks['filter_works']=True
        assert not errors;checks['numeric_browser_console_errors']=errors
        page.set_content((ROOT/'clustering_release_report_20260920.html').read_text(),wait_until='load')
        assert page.locator('table').count()>=8;assert page.locator('h2').count()>=10
        assert page.evaluate('Array.from(document.images).every(x=>x.complete&&x.naturalWidth>0)')
        checks['report_tables']=page.locator('table').count();checks['report_embedded_figures_loaded']=page.locator('img').count();checks['QA_scope']='DOM, numeric selection and chart loading only; no new image interpretation'
        b.close()
    (ROOT/'results/BROWSER_CHECK.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(checks)
if __name__=='__main__':run()
