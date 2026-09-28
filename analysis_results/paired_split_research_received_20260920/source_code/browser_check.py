"""Optional delivery-interface check, not a numerical or semantic validation."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]
errors=[];checks=[]
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    pg=b.new_page(viewport={'width':1440,'height':1080});pg.on('pageerror',lambda e:errors.append(str(e)))
    pg.set_content((R/'ATLAS.html').read_text(),wait_until='load');pg.wait_for_function("document.querySelector('#points').rows.length>1")
    assert pg.locator('#group option').count()==239
    assert pg.locator('#case option').count()==18
    for cid,method,contains in [('0','bound_fixed','2.0479'),('3','split_fixed','2.0809'),('13','split_fixed','28.9785'),('14','split_fixed','26.4097'),('14','split_free','5.3385'),('15','split_fixed','104.8391'),('15','split_cyclic','5.6970')]:
        pg.locator('#case').select_option(cid);pg.locator('#method').select_option(method)
        text=pg.locator('#status').inner_text();assert contains in text,(cid,method,text);checks.append({'case_index':int(cid),'method':method,'display':text})
    pg.locator('#case').select_option('4');assert '点数不同' in pg.locator('#status').inner_text();assert pg.locator('#points tr').count()==1
    pg.locator('#case').select_option('13');pg.locator('#method').select_option('split_fixed');pg.locator('#links').check();pg.locator('#showA').uncheck();pg.locator('#showA').check();pg.locator('#cut').select_option('6')
    pg.screenshot(path=str(R/'results/browser_atlas_check.png'),full_page=False)
    pg.set_content((R/'REPORT_ZH.html').read_text(),wait_until='load');assert pg.locator('h1').count()==1;assert pg.locator('table').count()==3
    assert pg.evaluate('Array.from(document.images).every(x=>x.complete && x.naturalWidth>0)')
    pg.screenshot(path=str(R/'results/browser_report_check.png'),full_page=False)
    b.close()
assert not errors,errors
result={'groups':239,'focused_pairs':17,'dynamic_rules':6,'cutoff_options':4,'browser_test_mode':'set_content_from_authorized_local_bytes','local_navigation_not_tested':True,'http_navigation_attempt':'blocked_by_administrator; no browser policy changed','javascript_errors':errors,'checks':checks,'semantic_validation':False}
(R/'results/BROWSER_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
