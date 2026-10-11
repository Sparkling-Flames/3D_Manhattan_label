"""Actual Chromium HTTP/pointer/download QA; never modifies reference inputs."""
from pathlib import Path
import json, hashlib, threading, functools, math, copy
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
checks=[]
def check(v,label):
 if not v: raise AssertionError(label)
 checks.append(label)
def js(p,s,arg=None):return p.evaluate(s,arg)
def boot(browser,base,storage_fail=False,width=1440):
 c=browser.new_context(viewport={'width':width,'height':1050},accept_downloads=True)
 if storage_fail:c.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw Error('forced storage failure')}})")
 p=c.new_page();p.errors=[];p.on('pageerror',lambda e:p.errors.append(str(e)));p.goto(base+'/editor/index.html');p.wait_for_function('!!window.workbench');p.wait_for_function('document.querySelector("#photoSource").textContent.includes("1536")');return c,p
def regions(p):return js(p,'workbench.getRegions()')
def draft(p):return js(p,'workbench.getDraft()')
def pointer(p,index,offset):
 args=js(p,'''([i,d])=>{const w=workbench,q=w.getDraft().polygon,a=q[i],b=q[(i+1)%q.length],l=Math.hypot(b[0]-a[0],b[1]-a[1]),mid=[(a[0]+b[0])/2,(a[1]+b[1])/2],n=[-(b[1]-a[1])/l,(b[0]-a[0])/l],s=w.worldToScreen(mid),t=w.worldToScreen(mid.map((v,k)=>v+n[k]*d)),m=document.querySelector('#bev').getScreenCTM(),f=x=>({x:m.a*x[0]+m.c*x[1]+m.e,y:m.b*x[0]+m.d*x[1]+m.f});return [f(s),f(t)]}''',[index,offset])
 p.locator('#bev').scroll_into_view_if_needed()
 # Scrolling changes client coordinates; recompute after scroll.
 args=js(p,'''([i,d])=>{const w=workbench,q=w.getDraft().polygon,a=q[i],b=q[(i+1)%q.length],l=Math.hypot(b[0]-a[0],b[1]-a[1]),mid=[(a[0]+b[0])/2,(a[1]+b[1])/2],n=[-(b[1]-a[1])/l,(b[0]-a[0])/l],m=document.querySelector('#bev').getScreenCTM(),f=x=>({x:m.a*x[0]+m.c*x[1]+m.e,y:m.b*x[0]+m.d*x[1]+m.f});return [f(w.worldToScreen(mid)),f(w.worldToScreen(mid.map((v,k)=>v+n[k]*d)))]}''',[index,offset])
 p.mouse.move(**args[0]);p.mouse.down();p.mouse.move(**args[1],steps=8);p.mouse.up()
def import_value(p,value):
 p.locator('#file').set_input_files({'name':'four_spaces.json','mimeType':'application/json','buffer':json.dumps(value,ensure_ascii=False).encode()});p.wait_for_timeout(100)
def main():
 class Handler(SimpleHTTPRequestHandler):
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(ROOT/'user')));threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
 evidence=ROOT/'results/browser_evidence';evidence.mkdir(exist_ok=True)
 receipt=json.loads((ROOT/'inputs/library/quality_review30_receipt.json').read_text())
 with sync_playwright() as pw:
  b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  c,p=boot(b,base);initial=regions(p);baseline=js(p,'workbench.getBaselines()')
  check([len(r['draft']['polygon']) for r in initial]==[14,13,0,0],'A14/B13 preserved; C/D truly empty')
  check([r['region_id'] for r in initial]==['primary','space_b','space_c','space_d'],'four independently identified slots')
  check(all(r['observation_support']['status']=='not_assessed' for r in initial),'support not inferred or assigned to C/D')
  check(js(p,"document.querySelector('#person').value")=='R02962','T30 exact record selected')
  check(p.locator('#person option').count()==21,'20 current answers plus all/none selector')
  check(p.locator('#topPending').is_disabled() and p.locator('#topPending').is_checked(),'pending top enforced')
  check(p.locator('#confirm').is_disabled(),'empty draft cannot be confirmed')
  pixel=js(p,"(()=>{const c=document.querySelector('#photo'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let colors=new Set;for(let i=0;i<d.length;i+=1024)colors.add(d[i]+','+d[i+1]+','+d[i+2]);return colors.size})()")
  check(pixel>100,'real panorama pixels rendered, not placeholder')
  check(js(p,"document.querySelector('#bev').innerHTML.includes('#c34a64')&&document.querySelector('#bev').innerHTML.includes('#2873d5')"),'GT red and selected annotation blue visible')
  p.screenshot(path=str(evidence/'T30_initial_four_slots.png'),full_page=True)
  x=js(p,'workbench.exportData({applyNoOperationPolicy:true})');check(x['independent_T30_rereview']['status']=='reference_pending' and x['historical_feedback']==receipt,'new T30 state pending; original thirty answers unchanged')
  check(x['GT_modified'] is False and x['scores_recomputed'] is False and not x['records'][0]['reference_ready'],'no GT writes, full reference or score recomputation')
  check(regions(p)==initial,'view and export do not confirm drafts')
  # Rectangle, cut, undo/redo, independent name and explicit confirmation.
  p.locator('#gtSnap').uncheck();js(p,'workbench.setRectangle([-2,-2],[2,2],0,false)');check(len(js(p,'workbench.getPreview()'))==4,'right-angle rectangle preview')
  p.locator('#continueCut').click();check(len(draft(p)['operations'])==1 and not js(p,'workbench.getConfirmation()'),'apply is separate from confirmation')
  p.locator('#orthogonal').uncheck();js(p,'workbench.setLine([1,2],[2,1])');p.locator('#apply').click();check(len(draft(p)['polygon'])==5,'rectangle then cut yields five-point boundary')
  before=draft(p);p.locator('#undo').click();check(len(draft(p)['polygon'])==4,'undo cut');p.locator('#redo').click();check(draft(p)==before,'redo exact cut and operation history')
  p.locator('#regionName').fill('C · QA临时独立空间');p.locator('#regionName').dispatch_event('change');p.locator('#confirm').click();check(js(p,'workbench.getConfirmation().floor_region_confirmed'),'only confirm button creates new floor confirmation')
  check(regions(p)[0]['draft']==initial[0]['draft'] and regions(p)[1]['draft']==initial[1]['draft'],'C drawing leaves A/B current geometry untouched')
  p.locator('#recheckState').select_option('reviewed');p.locator('#recheckVerdict').select_option('matches_selected');p.locator('#recheckTargets').select_option('space_c');p.locator('#recheckReason').fill('QA临时判断，不是用户反馈');p.locator('#saveRecheck').click();check(js(p,'workbench.getRecheck().status')=='reviewed','explicit independent rereview saved')
  check(js(p,'workbench.exportData().historical_feedback')==receipt,'independent rereview never overwrites historical T30 answer')
  out=js(p,'workbench.exportData()');with_download=None
  with p.expect_download() as dl:p.locator('#export').click()
  dp=evidence/'QA_only_roundtrip_export.json';dl.value.save_as(dp);download=json.loads(dp.read_text());check(download['records']==out['records'],'actual browser download matches four-space state')
  check(len(download['records'][0]['space_regions']['regions'])==4 and not download['records'][0]['space_regions']['regions'][3]['polygon'],'four-slot export preserves empty D')
  import_value(p,download);check('已导入' in p.locator('#toast').inner_text(),'browser file input validates and restores export')
  import_value(p,download);check(len(regions(p))==4,'repeated import idempotent; no manufactured before-import clones')
  check(js(p,'workbench.getBaselines()')==baseline,'immutable A/B baseline after edit/import')
  before=regions(p)
  mutations={
   'GT baseline':lambda v:v['records'][0]['original_GT_points_1024x512'][0].__setitem__(0,999),
   'original answers':lambda v:v['historical_feedback']['answers'][29].__setitem__('reason','overwrite'),
   'empty confirmed draft':lambda v:v['records'][0]['space_regions']['regions'][3].__setitem__('completed',True),
   'full-reference flag':lambda v:v['records'][0].__setitem__('reference_ready',True),
   'top borrowing':lambda v:v['records'][0]['space_regions']['regions'][3].__setitem__('top_boundary_pending',False),
   'missing required D':lambda v:v['records'][0]['space_regions']['regions'].pop(),
   'unconfirmed rereview target':lambda v:v['independent_T30_rereview'].__setitem__('matching_region_ids',['space_d'])}
  for label,fn in mutations.items():
   bad=copy.deepcopy(download);fn(bad);import_value(p,bad);check('导入失败' in p.locator('#toast').inner_text() and regions(p)==before,'atomic rejection: '+label)
  # Hide visibility and user-observed support remain separate from coordinates/acceptance.
  p.locator('[data-space-visible="space_d"]').uncheck();p.locator('[data-space-support="space_d"]').select_option('user_reports_not_observed');check(not regions(p)[3]['visible'] and not regions(p)[3]['draft']['polygon'] and regions(p)[3]['observation_support']['source']=='user_statement','explicit observed-support and visibility metadata, no synthetic target')
  p.reload();p.wait_for_function('!!window.workbench');check(len(regions(p))==4 and js(p,'workbench.getRecheck().status')=='reviewed','four spaces and independent rereview survive reload')
  p.locator('[data-space-edit="space_d"]').click();p.locator('#gtSnap').uncheck();js(p,'workbench.setRectangle([-2.5,-2.5],[2.5,2.5],0,false)');p.locator('#apply').click();p.locator('#regionName').fill('D · QA临时独立空间');p.locator('#regionName').dispatch_event('change');p.locator('#confirm').click()
  p.locator('[data-space-edit="primary"]').click();p.locator('[data-decision="full_gt"]').click();p.locator('#confirm').click()
  check(all(js(p,"workbench.getRegions().map(r=>ReviewState.regionStatus(r))")[i]=='confirmed' for i in range(4)),'all four slots can hold independent explicit confirmations')
  complete=js(p,'workbench.exportData()');import_value(p,complete);check(len(regions(p))==4 and all(r['confirmed_version']['floor_region_confirmed'] for r in regions(p)),'roundtrip four explicitly confirmed spaces')
  check(js(p,'workbench.getBaselines()')==baseline and js(p,'workbench.exportData().historical_feedback')==receipt,'four-space confirmations preserve baseline coordinates and original answers')
  cc2,pp=boot(b,base);import_value(pp,complete);check('已导入' in pp.locator('#toast').inner_text() and len(regions(pp))==4,'fresh browser imports full four-space confirmations');js(pp,"workbench.switchRegion('space_c');workbench.setMode('edge')");pp.locator('#gtSnap').uncheck();js(pp,'workbench.setEdge(0,.1)');pp.locator('#apply').click();check(js(pp,'workbench.getRecheck().status')=='reference_pending' and any(k.startswith('T30_rereview_before_reference_change_') for k in js(pp,'workbench.exportData().unrecovered_drafts')),'changed reference archives prior independent rereview and requires renewed review');stale=js(pp,'workbench.exportData()');import_value(pp,stale);k1=len(js(pp,'workbench.exportData().unrecovered_drafts'));import_value(pp,stale);check('已导入' in pp.locator('#toast').inner_text() and len(js(pp,'workbench.exportData().unrecovered_drafts'))==k1,'repeat import of archived manual rereviews avoids nested duplicates');cc2.close()
  check(not p.errors,'editor has no browser JavaScript exceptions');c.close()
  # Actual closing-edge pointer gesture at two viewport sizes, before/after zoom.
  for width in (1100,1700):
   cc,t=boot(b,base,width=width);js(t,"workbench.switchRegion('primary');workbench.setMode('edge')");start=draft(t)
   for zoomed in (False,True):
    if zoomed:
     before_px=js(t,'workbench.worldPerCssPixel()');t.locator('#zoomIn').click();check(abs(js(t,'workbench.worldPerCssPixel()')-before_px/1.3)<1e-10,'snap tolerance follows actual CSS scale after zoom')
    px=js(t,'workbench.worldPerCssPixel()');pointer(t,11,-.8478948561575355+2*px)
    check(len(js(t,'workbench.getPreview()') or [])==13,f'real pointer: 14→13 closing corner merge, width={width}, zoom={zoomed}')
    status=t.locator('#snapStatus').inner_text();check('顶点 14' in status and '14–1 延长线' in status,f'visible vertex14 and closing14–1 snap labels, width={width}, zoom={zoomed}')
    check(t.locator('[data-gt-extension="13"]').count()>0,'closing extension guide visible')
    t.locator('#followGT').click();check(len(js(t,'workbench.getPreview()'))==12,'explicit closing-edge exact follow gives 12 vertices')
    check(draft(t)==start,'pointer and exact snap previews do not edit stored A')
    t.screenshot(path=str(evidence/f'closing14_1_{width}_{int(zoomed)}.png'),full_page=True)
    t.locator('#apply').click();check(draft(t)['operations'][-1]['type']=='edge_follow','exact follow stores resolved line replay')
    t.locator('#undo').click();check(draft(t)==start,'undo exact closing follow restores A')
    # Preview cancel also preserves confirmation.
    js(t,'workbench.setEdge(11,-.8478948561575355)');t.locator('#cancel').click();check(draft(t)==start and not js(t,'workbench.getConfirmation()'),'cancel preview never confirms')
   check(not t.errors,'closing-edge browser exception free');cc.close()
  # Browser storage getter failure must not stop edits and downloads.
  cc,t=boot(b,base,True);t.locator('#gtSnap').uncheck();js(t,'workbench.setRectangle([-2,-2],[2,2],0,false)');t.locator('#apply').click();check('必须导出' in t.locator('#saved').inner_text(),'storage failure prominently requires export')
  with t.expect_download() as dl:t.locator('#export').click()
  dl.value.save_as(evidence/'QA_storage_failure_export.json');check(len(json.loads((evidence/'QA_storage_failure_export.json').read_text())['records'][0]['space_regions']['regions'][2]['polygon'])==4,'download remains usable when localStorage throws');check(not t.errors,'storage failure handled without browser exceptions');cc.close()
  # Prefilled immutable history including all thirty original field values.
  cc=b.new_context();t=cc.new_page();t.goto(base+'/review30/index.html');t.wait_for_function('document.querySelector("#primary-progress").textContent.includes("30 / 30")')
  for row in receipt['answers']+receipt['pair_answers']:
   rid=row.get('case_id',row.get('pair_id'))
   for el in t.locator(f'[data-row-id="{rid}"][data-field]').all():
    field=el.get_attribute('data-field');check(el.input_value()==row[field] and el.is_disabled(),f'prefill locked: {rid}.{field}')
  t.locator('[data-go-case="T30"]').click();check(t.locator('[data-row-id="T30"][data-field="space_compatibility"]').input_value()=='两者均不匹配','T30 historical mismatch preserved')
  t.screenshot(path=str(evidence/'historical_T30_readonly.png'),full_page=True)
  with t.expect_download() as dl:t.locator('#download-json').click()
  dl.value.save_as(evidence/'QA_history_export.json');check(json.loads((evidence/'QA_history_export.json').read_text())==receipt,'history browser export preserves every original answer and dataset identity')
  t.evaluate("async()=>{const xs=[...document.images];xs.forEach(x=>x.loading='eager');await Promise.all(xs.map(x=>x.decode()))}")
  check(all(t.locator('img').nth(i).evaluate('(x)=>x.complete&&x.naturalWidth>0') for i in range(t.locator('img').count())),'all 120 prior real image assets load')
  cc.close();b.close()
 server.shutdown()
 (ROOT/'results/browser_qa.json').write_text(json.dumps({'actual_browser':'Chromium /usr/bin/chromium; Python Playwright; HTTP loopback','checks_passed':len(checks),'checks':checks,'qa_states':'All QA-drawn coordinates and test verdicts are temporary test outputs, never user evidence','real_images':True},ensure_ascii=False,indent=2)+'\n');print('PASS',len(checks),'actual browser checks')
if __name__=='__main__':main()
