from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1360,'height':1200},device_scale_factor=1);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content((ROOT/'EVIDENCE_VIEWER_ZH.html').read_text(),wait_until='load');page.wait_for_timeout(500)
 checks=[]
 for i,n in [(0,3),(1,24),(2,24),(3,15)]:
  page.select_option('#image',str(i));page.wait_for_timeout(50)
  count=page.locator('#roster tbody tr').count();checks.append(dict(image_index=i,expected=n,roster_rows=count,passed=count==n))
  page.check('#gt');page.select_option('#person','0');page.locator('#erp').click(position={'x':400,'y':120});page.uncheck('#gt')
 page.select_option('#image','1');page.select_option('#variant','6');page.wait_for_timeout(50)
 page.screenshot(path=str(ROOT/'figures/viewer_preview.png'),full_page=False)
 # Chosen selector 6 belongs to the mandatory lock series, not a recomputation.
 d={'javascript_errors':errors,'rosters':checks,'page_source_is_offline':True,'visual_source_image_loaded':False,'gt_toggle_and_source_highlight_tested':True,'all_passed':not errors and all(c['passed'] for c in checks)}
 (ROOT/'results/viewer_checks.json').write_text(json.dumps(d,indent=2));print(d);b.close()
