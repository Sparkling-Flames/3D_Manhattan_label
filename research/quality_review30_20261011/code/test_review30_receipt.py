"""Real Chromium UI and payload checks; synthetic answers stay in temporary browser storage."""
import argparse,hashlib,json,threading
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/workspace/quality_compute_20261010/blind_sample/user')
OLD_KEY='quality_blind_sample_receipt_v1:20261010:C01-C07-X01'
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass

def field(p,cid,name):return p.locator(f'[data-row-id="{cid}"][data-field="{name}"]')
def go(p,cid):p.locator('#go-pair' if cid=='P01' else f'[data-go-case="{cid}"]').click();p.wait_for_function('(id)=>document.querySelector(`[data-panel-id="${id}"]`).hidden===false',arg=cid)
def dl(p,kind):
 with p.expect_download() as x:p.locator('#download-'+kind).click()
 return Path(x.value.path()).read_text(encoding='utf-8-sig')
def upload(p,name,text):
 p.locator('#receipt-status').evaluate('(e)=>e.textContent=""');p.locator('#import-receipt').set_input_files({'name':name,'mimeType':'application/json' if name.endswith('.json') else 'text/csv','buffer':text.encode('utf-8')});p.wait_for_function("document.getElementById('receipt-status').textContent.includes('导入')")
def snapshot(p):return p.evaluate('''()=>({inputs:[...document.querySelectorAll('[data-field]')].map(e=>[e.dataset.rowId,e.dataset.field,e.value]),draft:Object.fromEntries(Object.keys(localStorage).map(k=>[k,localStorage.getItem(k)])),panel:document.querySelector('[data-panel-id]:not([hidden])').dataset.panelId})''')
def main():
 global ROOT,OLD
 ap=argparse.ArgumentParser();ap.add_argument('--review-root',type=Path,default=ROOT);ap.add_argument('--old-user',type=Path,default=OLD);args=ap.parse_args();ROOT=args.review_root;OLD=args.old_user
 checks=[];user=ROOT/'user';hashes_before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in user.iterdir() if p.is_file()};schema=json.load(open(ROOT/'results/receipt_schema_anonymous.json'));order=schema['display_order'];server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(user)));threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}/index.html'
 def passed(s):checks.append({'name':s,'passed':True});print(s,flush=True)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=browser.new_context(accept_downloads=True);ctx.add_init_script(f'localStorage.setItem({json.dumps(OLD_KEY)},"old8-sentinel")');p=ctx.new_page();requests=[];p.on('request',lambda req:requests.append(req.url));p.goto(url)
  assert all(v=='' for v in p.locator('[data-field]').evaluate_all('(els)=>els.map(e=>e.value)'));assert p.locator('[data-panel-id]:visible').get_attribute('data-panel-id')==order[0];assert len(p.locator('[data-go-case]').all())==30;assert '0 / 30' in p.locator('#primary-progress').inner_text();blank=json.loads(dl(p,'json'));assert len(blank['answers'])==30 and len(blank['pair_answers'])==1 and blank['case_ids']==[f'T{i:02d}' for i in range(1,31)] and blank['display_order']==order;passed('fresh_blank_30_unique_plus_separate_optional_pair_and_frozen_order')
  p.locator('#next-case').click();assert order[1] in p.locator('#current-position').inner_text();p.locator('#prev-case').click();assert order[0] in p.locator('#current-position').inner_text();assert '0 / 30' in p.locator('#primary-progress').inner_text();passed('view_navigation_and_blank_export_do_not_count_completion')
  go(p,'T01');field(p,'T01','absolute_quality').select_option('可接受');text='测试,逗号"引号"与换行\n第二行 🙂';field(p,'T01','reason').fill(text)
  go(p,'T07');field(p,'T07','reference_question').select_option('参考/目标有疑问');field(p,'T07','reason').fill('仅填写原因');assert '1 / 30' in p.locator('#primary-progress').inner_text() and '部分填写 1' in p.locator('#primary-progress').inner_text()
  go(p,'T28');field(p,'T28','space_compatibility').select_option('无法判断');assert '2 / 30' in p.locator('#primary-progress').inner_text();go(p,'P01');field(p,'P01','preference').select_option('相近');field(p,'P01','gap').select_option('小');assert '2 / 30' in p.locator('#primary-progress').inner_text() and '1 / 1' in p.locator('#pair-progress').inner_text();passed('only_primary_decisions_count_unknown_valid_reasons_partial_pair_separate')
  j=dl(p,'json');c=dl(p,'csv');go(p,'T01');field(p,'T01','reason').fill('changed');upload(p,'roundtrip.json',j);assert field(p,'T01','reason').input_value()==text;assert p.locator('[data-panel-id]:visible').get_attribute('data-panel-id')=='T07';assert '第 3 份 / 共 30 份' in p.locator('#current-position').inner_text();passed('JSON_roundtrip_restores_and_locates_first_incomplete_in_display_order')
  go(p,'T01');field(p,'T01','reason').fill('changed again');upload(p,'roundtrip.csv',c);assert field(p,'T01','reason').input_value()==text and field(p,'P01','preference').input_value()=='相近';passed('CSV_roundtrip_unicode_quotes_commas_newlines_and_separate_pairs')
  before=snapshot(p);valid=json.loads(j)
  errors=[]
  cases=[('old8.json',(OLD/'responses.json').read_text()),('old8.csv',(OLD/'responses.csv').read_text())]
  for name,fn in [('old_ID',lambda r:r['answers'][0].update(case_id='C01')),('duplicate_ID',lambda r:r['answers'][1].update(case_id='T01')),('wrong_version',lambda r:r.update(format_version='quality_blind_sample_receipt_v1')),('wrong_order',lambda r:r['display_order'].reverse()),('missing_field',lambda r:r['answers'][0].pop('reason')),('overlong',lambda r:r['answers'][0].update(notes='x'*2001)),('bad_option',lambda r:r['answers'][0].update(absolute_quality='unknown')),('bad_pair_identity_atomic',lambda r:(r['answers'][0].update(reason='must not apply'),r['pair_answers'][0].update(left_case_id='T03'))),('extra_pair',lambda r:r['pair_answers'].append(r['pair_answers'][0].copy()))]:
   bad=json.loads(j);fn(bad);cases.append((name+'.json',json.dumps(bad,ensure_ascii=False)))
  cases.append(('oversize.json',' '*1048577))
  for name,bad in cases:upload(p,name,bad);assert '导入被拒绝' in p.locator('#receipt-status').inner_text();assert snapshot(p)==before,name;errors.append(name)
  passed('invalid_old8_versions_IDs_structure_pairs_and_oversize_preserve_answers_storage_position:'+','.join(errors))
  for i in range(3):upload(p,'repeat.json',j);assert snapshot(p)==before
  passed('repeated_import_idempotent_no_duplicate_rows_or_progress')
  payload='<img src=x onerror="window.receiptInjected=true"><script>window.receiptInjected=true</script>';literal=json.loads(j);literal['answers'][0]['notes']=payload;upload(p,'literal.json',json.dumps(literal));assert field(p,'T01','notes').input_value()==payload and p.evaluate('window.receiptInjected===undefined');passed('imported_markup_plain_text_not_executed')
  go(p,'T07');field(p,'T07','absolute_quality').select_option('无法判断');p.locator('#prev-case').click();assert p.locator('[data-panel-id]:visible').get_attribute('data-panel-id')=='T01';assert field(p,'T01','reason').input_value()==text;p.reload();assert '已恢复' in p.locator('#draft-status').inner_text() and p.locator('[data-panel-id]:visible').get_attribute('data-panel-id')=='T01';assert field(p,'T01','notes').input_value()==payload and field(p,'T07','absolute_quality').input_value()=='无法判断';assert p.evaluate(f'localStorage.getItem({json.dumps(OLD_KEY)})')=='old8-sentinel';passed('paging_back_refresh_restores_answers_and_position_old8_storage_untouched')
  all_done=json.loads(j)
  for row in all_done['answers']:row['absolute_quality' if row['case_type']=='quality' else 'space_compatibility']='无法判断'
  upload(p,'all_done.json',json.dumps(all_done));assert '30 / 30' in p.locator('#primary-progress').inner_text();assert p.locator('[data-panel-id]:visible').get_attribute('data-panel-id')==order[-1];passed('all_completed_import_locates_last_primary_and_keeps_optional_count_separate')
  # Load actual image files for every primary panel, not merely filename existence.
  for cid in order:
   go(p,cid);p.locator(f'[data-panel-id="{cid}"] img').evaluate_all('(els)=>els.forEach(e=>e.loading="eager")');p.wait_for_function('(id)=>[...document.querySelector(`[data-panel-id="${id}"]`).querySelectorAll("img")].every(e=>e.complete&&e.naturalWidth>0)',arg=cid)
   assert len(p.locator(f'[data-panel-id="{cid}"] img').all())==4
  go(p,'P01');p.locator('[data-panel-id="P01"] img').evaluate_all('(els)=>els.forEach(e=>e.loading="eager")');p.wait_for_function('()=>[...document.querySelector(`[data-panel-id="P01"]`).querySelectorAll("img")].every(e=>e.complete&&e.naturalWidth>0)');assert len(p.locator('[data-panel-id="P01"] img').all())==8;assert all(x.startswith(f'http://127.0.0.1:{server.server_port}/') for x in requests);passed('all_120_primary_images_and_reused_8_pair_images_load_no_external_network')
  for name,script in [('getter',"Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})"),('quota',"Object.defineProperty(window,'localStorage',{value:{getItem(){return null},setItem(){throw new DOMException('quota','QuotaExceededError')}}})")]:
   fail=browser.new_context(accept_downloads=True);fail.add_init_script(script);q=fail.new_page();q.goto(url);go(q,'T01');field(q,'T01','absolute_quality').select_option('无法判断');field(q,'T01','reason').fill('存储失败仍导出');assert '必须下载回执' in q.locator('#draft-status').inner_text();export=json.loads(dl(q,'json'));assert export['answers'][0]['reason']=='存储失败仍导出' and export['answers'][0]['absolute_quality']=='无法判断';go(q,order[0]);go(q,'T01');assert field(q,'T01','reason').input_value()=='存储失败仍导出';passed('storage_'+name+'_failure_warns_preserves_paging_and_exports');fail.close()
  ctx.close();browser.close()
 server.shutdown();server.server_close();hashes_after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in user.iterdir() if p.is_file()};assert hashes_before==hashes_after;passed('delivered_all_blank_defaults_and_all_image_bytes_unchanged_by_tests')
 result={'engine':'preinstalled /usr/bin/chromium via local loopback HTTP; managed environment blocks file://, Windows double-click not claimed tested','tests':checks,'passed_groups':len(checks),'failed':0,'synthetic_test_answers_in_deliverables':False,'new_browser_install_used':False,'final_owner_Q_ring_representation_check_repeated':False}
 (ROOT/'results/review30_browser_tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print('PASSED',len(checks),'groups')
if __name__=='__main__':main()
