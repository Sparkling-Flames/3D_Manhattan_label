"""Actual offline Chromium UI tests; synthetic answers never enter delivered defaults."""
import csv,hashlib,io,json,tempfile,threading
from functools import partial
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
REASON='答案1主要原因';NOTES='备注'
def field(page,cid,key):return page.locator(f'[data-case-id="{cid}"][data-field="{key}"]')
def download(page,kind):
 with page.expect_download() as pending:page.locator('#download-'+kind).click()
 return Path(pending.value.path()).read_text(encoding='utf-8-sig')
def upload(page,name,text):
 page.locator('#import-receipt').set_input_files({'name':name,'mimeType':'application/json' if name.endswith('.json') else 'text/csv','buffer':text.encode('utf-8')})
 page.wait_for_function("document.getElementById('receipt-status').textContent.includes('导入')")
def snapshot(page):
 return page.evaluate('''()=>({inputs:[...document.querySelectorAll('[data-field]')].map(e=>[e.dataset.caseId,e.dataset.field,e.value]),draft:localStorage.getItem(ReviewReceipt.STORAGE_KEY)})''')
def main():
 checks=[]
 def passed(name):checks.append({'name':name,'passed':True});print(name,flush=True)
 server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(ROOT/'blind_sample/user')))
 threading.Thread(target=server.serve_forever,daemon=True).start();PAGE=f'http://127.0.0.1:{server.server_port}/index.html'
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  context=browser.new_context(accept_downloads=True);page=context.new_page();page.goto(PAGE)
  assert all(v=='' for v in page.locator('[data-field]').evaluate_all('(els)=>els.map(e=>e.value)'))
  passed('fresh_context_all_answers_blank')
  field(page,'C01',REASON).fill('回执测试：逗号,引号"与换行\n第二行')
  field(page,'C01','答案1（可接受/明显问题/严重不可接受/无法判断）').select_option('无法判断')
  field(page,'X01','空间判断（仅 A 可匹配/仅 B 可匹配/两者均可匹配/两者均不匹配/无法判断）').select_option('两者均可匹配')
  json_receipt=download(page,'json');csv_receipt=download(page,'csv')
  field(page,'C01',REASON).fill('修改后将恢复')
  upload(page,'roundtrip.json',json_receipt);assert field(page,'C01',REASON).input_value()=='回执测试：逗号,引号"与换行\n第二行';passed('JSON_export_then_import_restores_answers')
  field(page,'C01',REASON).fill('再次修改')
  upload(page,'roundtrip.csv',csv_receipt);assert field(page,'C01',REASON).input_value()=='回执测试：逗号,引号"与换行\n第二行';passed('CSV_export_then_import_handles_quotes_commas_newlines')
  before=json.loads(download(page,'json'));before_inputs=snapshot(page)
  errors=[]
  for name,mutate in [
   ('missing_field',lambda r:r['answers'][0].pop(REASON)),
   ('invalid_case_id',lambda r:r['answers'][0].update(case_id='C99')),
   ('duplicate_case_id',lambda r:r['answers'][1].update(case_id='C01')),
   ('wrong_version',lambda r:r.update(format_version='wrong')),
   ('extra_field',lambda r:r['answers'][0].update(unexpected='x')),
   ('overlong_answer',lambda r:r['answers'][0].update({REASON:'x'*2001})),
   ('changed_field_schema',lambda r:r['fields'].append('extra'))]:
   invalid=json.loads(json.dumps(before));mutate(invalid);page.locator('#receipt-status').evaluate('(e)=>e.textContent=""');upload(page,name+'.json',json.dumps(invalid,ensure_ascii=False))
   assert '导入被拒绝' in page.locator('#receipt-status').inner_text();assert snapshot(page)==before_inputs;errors.append(name)
  passed('invalid_imports_keep_existing_answers:'+','.join(errors))
  page.locator('#receipt-status').evaluate('(e)=>e.textContent=""');upload(page,'too_large.json',' '*1048577);assert '导入被拒绝' in page.locator('#receipt-status').inner_text();assert snapshot(page)==before_inputs;passed('oversize_import_rejected_without_erasing_answers')
  literal=json.loads(json.dumps(before));payload='<img src=x onerror="window.receiptInjected=true"><script>window.receiptInjected=true</script>';literal['answers'][0][NOTES]=payload
  page.locator('#receipt-status').evaluate('(e)=>e.textContent=""');upload(page,'literal.json',json.dumps(literal));assert field(page,'C01',NOTES).input_value()==payload;assert page.evaluate('window.receiptInjected === undefined');passed('HTML_like_user_text_imported_as_plain_values_only')
  page.reload();assert '已恢复' in page.locator('#draft-status').inner_text();assert field(page,'C01',NOTES).input_value()==payload;passed('actual_page_refresh_restores_valid_local_draft')
  for mode,script in [
   ('getter',"Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError')}})"),
   ('write',"Object.defineProperty(window,'localStorage',{value:{getItem(){return null},setItem(){throw new DOMException('quota','QuotaExceededError')}}})")]:
   failed=browser.new_context(accept_downloads=True);failed.add_init_script(script);q=failed.new_page();q.goto(PAGE);field(q,'C01',REASON).fill('存储失败时仍可下载')
   assert '必须下载回执' in q.locator('#draft-status').inner_text();receipt=download(q,'json');assert json.loads(receipt)['answers'][0][REASON]=='存储失败时仍可下载';assert field(q,'C01',REASON).input_value()=='存储失败时仍可下载';passed('storage_'+mode+'_failure_warns_and_still_exports_current_inputs');failed.close()
  context.close();browser.close()
 result={'engine':'preinstalled /usr/bin/chromium, actual offline UI served on loopback; file:// blocked by managed policy','tests':checks,'passed':len(checks),'failed':0,'synthetic_test_answers_in_default_delivery':False,'downloaded_browser_install_used':False}
 server.shutdown();server.server_close()
 (ROOT/'results/review_receipt_tests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
