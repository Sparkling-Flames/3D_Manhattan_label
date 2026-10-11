"""Unpack only the delivered ZIP and open both pages in real Chromium."""
from pathlib import Path
from tempfile import TemporaryDirectory
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json,zipfile,threading,functools,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def main():
 artifact=ROOT/'artifacts/quality_four_space_recheck_20261011_user.zip';checks=[]
 def check(v,label):
  assert v,label;checks.append(label)
 with TemporaryDirectory(prefix='quality-four-space-zip-') as d:
  with zipfile.ZipFile(artifact) as z:
   check(z.testzip() is None,'ZIP CRC valid');z.extractall(d)
   raw=z.read('historical_feedback/quality_review30_receipt.json');check(hashlib.sha256(raw).hexdigest()=='8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c','original receipt bytes preserved in user ZIP')
   check(not any('QA_' in n or 'browser_evidence' in n for n in z.namelist()),'no QA judgments or screenshots in user ZIP')
  class Handler(SimpleHTTPRequestHandler):
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=d));threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);p=b.new_page();errors=[];failed=[];p.on('pageerror',lambda e:errors.append(str(e)));p.on('response',lambda r:failed.append(r.url) if r.status>=400 and not r.url.endswith('favicon.ico') else None)
   p.goto(base+'/index.html');p.get_by_role('link',name='打开 T30 四空间工作台').click();p.wait_for_function('!!window.workbench');p.wait_for_function("document.querySelector('#photoSource').textContent.includes('1536')")
   check(p.evaluate('workbench.getRegions().map(r=>r.draft.polygon.length)')==[14,13,0,0],'unpacked artifact retains empty C/D without test coordinates')
   check(p.evaluate('workbench.getRecheck().status')=='reference_pending','unpacked artifact has no QA/user rereview prefilled')
   check(p.locator('#person option').count()==21,'all twenty current answers available independently')
   p.goto(base+'/review30/index.html');p.wait_for_function('document.querySelector("#primary-progress").textContent.includes("30 / 30")');check(p.locator('[data-row-id="T30"][data-field="reason"]').input_value()=='另一种空间','historical T30 original answer preserved in ZIP')
   p.evaluate("async()=>{const xs=[...document.images];xs.forEach(x=>x.loading='eager');await Promise.all(xs.map(x=>x.decode()))}");check(all(p.locator('img').nth(i).evaluate('(x)=>x.complete&&x.naturalWidth>0') for i in range(p.locator('img').count())),'all historical real views load from ZIP alone')
   check(not errors and not failed,'no missing executable assets or browser exceptions');b.close()
  server.shutdown()
 report={'checks_passed':len(checks),'checks':checks,'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'runtime':'actual Chromium; fresh temporary ZIP extraction and HTTP only','file_url_tested':False};(ROOT/'results/artifact_smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(report)
if __name__=='__main__':main()
