"""仅在127.0.0.1提供109工作台和已明确绑定的原图；不提供正式写入API。"""
from __future__ import annotations
import argparse,json,mimetypes
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,unquote
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/point_edit_review_20261009'
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(OUT),**kwargs)
 def do_GET(self):
  url=urlsplit(self.path)
  if url.path=='/health':
   b=(OUT/'validation.json').read_bytes();self.send_response(200);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  if url.path.startswith('/image/'):
   image_id=unquote(url.path[len('/image/'):]);sources=json.loads((OUT/'image_sources.json').read_text(encoding='utf-8'))
   rel=sources.get(image_id)
   if not rel:self.send_error(404,'Image identity not in review queue');return
   path=(ROOT/rel).resolve()
   if not path.is_relative_to(ROOT) or not path.is_file():self.send_error(404,'Bound original image missing');return
   size=path.stat().st_size;self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(size));self.send_header('Cache-Control','private, max-age=3600');self.end_headers()
   with path.open('rb') as f:
    while chunk:=f.read(1024*1024):self.wfile.write(chunk)
   return
  return super().do_GET()
 def log_message(self,fmt,*args):pass
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8769);a=p.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);print(f'http://127.0.0.1:{a.port}/',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
