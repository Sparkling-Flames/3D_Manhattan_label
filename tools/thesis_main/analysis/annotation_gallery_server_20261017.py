"""本机标注图片查阅服务；唯一写入是独立补人计划，源标注/评分只读。"""
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import socket
import tempfile
import threading
from urllib.parse import parse_qs,unquote,urlsplit
from urllib.request import urlopen
from urllib.error import URLError
import webbrowser

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'research/statistics/annotation_gallery_20261017/gallery.json'
STATIC=Path(__file__).with_name('annotation_gallery_20261017')
VERSION='annotation_gallery_supplement_plan_20261017_v1'


def existing_gallery_matches(url,version):
    try:
        with urlopen(url+'/api/data',timeout=2) as response:
            document=json.load(response)
            return isinstance(document,dict) and document.get('version')==version
    except (URLError,OSError,ValueError):
        return False


class GalleryServer(ThreadingHTTPServer):
    allow_reuse_address=False

    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()


class PlanStore:
    def __init__(self,path,image_ids):
        self.path=path;self.lock=threading.Lock()
        self.plans={image_id:dict(additional_people=None,note='',updated_at=None) for image_id in image_ids}
        if path.exists():
            saved=json.loads(path.read_text(encoding='utf-8-sig'))
            if saved['version']!=VERSION or not set(saved['plans'])<=set(image_ids):
                raise ValueError('saved plan version or image IDs differ from gallery')
            for image_id,plan in saved['plans'].items():
                self.validate({key:plan[key] for key in ['additional_people','note']})
                self.plans[image_id]=plan

    @staticmethod
    def validate(patch):
        if not isinstance(patch,dict) or not set(patch)<={'additional_people','note'}:
            raise ValueError('only additional_people and note may be updated')
        if 'additional_people' in patch:
            value=patch['additional_people']
            if value is not None and (type(value) is not int or value<0):
                raise ValueError('additional_people must be a nonnegative integer or null')
        if 'note' in patch and not isinstance(patch['note'],str):
            raise ValueError('note must be a string')

    def document(self):
        with self.lock:
            return dict(version=VERSION,plans={key:dict(value) for key,value in self.plans.items()})

    def patch(self,image_id,patch):
        self.validate(patch)
        with self.lock:
            if image_id not in self.plans:raise KeyError(image_id)
            plan=dict(self.plans[image_id],**patch)
            plan['updated_at']=datetime.now(timezone.utc).isoformat(timespec='microseconds')
            merged=dict(self.plans);merged[image_id]=plan
            # 文件替换成功后才提交内存，写失败不会丢掉上一份计划。
            temporary=None
            try:
                with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,
                        prefix='.supplement_plan-',suffix='.tmp',delete=False) as stream:
                    temporary=Path(stream.name)
                    json.dump(dict(version=VERSION,plans=merged),stream,ensure_ascii=False,indent=2)
                    stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,self.path)
            finally:
                if temporary is not None and temporary.exists():temporary.unlink()
            self.plans=merged
            return dict(image_id=image_id,plan=dict(plan),saved_at=plan['updated_at'])


def create_server(data_path=DATA,port=8877,*,root=ROOT,static_dir=STATIC):
    data_path,root,static_dir=Path(data_path),Path(root).resolve(),Path(static_dir)
    gallery=json.loads(data_path.read_text(encoding='utf-8-sig'))
    images={image['image_id']:image for image in gallery['images']}
    if len(images)!=len(gallery['images']) or any(not isinstance(key,str) or not key for key in images):
        raise ValueError('gallery image_id must be unique and nonempty')
    base=lambda image:{key:value for key,value in image.items() if key not in ('annotations','references')}
    overview={key:value for key,value in gallery.items() if key not in ('images','annotations','references')}
    overview['images']=[base(image) for image in gallery['images']]
    store=PlanStore(data_path.with_name('supplement_plan.json'),images)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,format,*args):
            pass

        def send_bytes(self,status,body,content_type,headers=None):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers();self.wfile.write(body)

        def send_json(self,status,payload,headers=None):
            self.send_bytes(status,json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8'),
                            'application/json; charset=utf-8',headers)

        def error(self,status,message):
            self.send_json(status,dict(error=message))

        def file(self,path):
            try:body=path.read_bytes()
            except FileNotFoundError:self.error(404,'file not found');return
            except OSError:self.error(500,'file could not be read');return
            self.send_bytes(200,body,mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

        def do_GET(self):
            route=urlsplit(self.path);path=unquote(route.path)
            if path=='/api/data':self.send_json(200,overview)
            elif path=='/api/plans':self.send_json(200,store.document())
            elif path=='/api/export':
                self.send_json(200,store.document(),{'Content-Disposition':'attachment; filename="supplement_plan.json"'})
            elif path.startswith('/api/images/'):
                image_id=path[len('/api/images/'):]
                if image_id not in images:self.error(404,'unknown image_id');return
                image=images[image_id]
                self.send_json(200,dict(image=base(image),annotations=image.get('annotations',[]),references=image.get('references',[])))
            elif path.startswith('/photo/'):
                image_id=path[len('/photo/'):]
                if image_id not in images:self.error(404,'unknown image_id');return
                kind=parse_qs(route.query).get('kind',['thumb'])[0]
                if kind not in ('thumb','original'):self.error(400,'unknown photo kind');return
                source=images[image_id].get('thumbnail_path' if kind=='thumb' else 'original_path')
                if not source:self.error(404,'photo unavailable');return
                relative=Path(source)
                if relative.is_absolute():self.error(403,'photo path must be repository relative');return
                resolved=(root/relative).resolve()
                if not resolved.is_relative_to(root):
                    self.error(403,'photo path outside workspace');return
                self.file(resolved)
            elif path in ('/','/index.html','/app.css','/app.js'):
                self.file(static_dir/('index.html' if path=='/' else path[1:]))
            else:self.error(404,'unknown route')

        def do_PATCH(self):
            path=unquote(urlsplit(self.path).path)
            if not path.startswith('/api/plans/'):self.error(404,'unknown route');return
            image_id=path[len('/api/plans/'):]
            if image_id not in images:self.error(404,'unknown image_id');return
            origin=self.headers.get('Origin')
            if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':
                self.error(403,'cross-origin updates rejected');return
            if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':
                self.error(415,'application/json required');return
            try:length=int(self.headers.get('Content-Length','0'))
            except ValueError:self.error(400,'invalid body length');return
            if length<1 or length>65536:self.error(400,'invalid body length');return
            try:
                patch=json.loads(self.rfile.read(length).decode('utf-8'))
                response=store.patch(image_id,patch)
            except (ValueError,UnicodeError) as exc:self.error(400,str(exc));return
            except OSError:self.error(500,'plan could not be saved');return
            self.send_json(200,response)

    server=GalleryServer(('127.0.0.1',port),Handler)
    server.plan_store=store
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,default=DATA)
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--open-browser',action='store_true',help='打开浏览器；已有同版本本机服务时直接复用')
    args=parser.parse_args()
    url=f'http://127.0.0.1:{args.port}'
    try:server=create_server(args.data,args.port)
    except OSError:
        version=json.loads(args.data.read_text(encoding='utf-8-sig'))['version']
        if args.open_browser and existing_gallery_matches(url,version):
            webbrowser.open(url)
            raise SystemExit(0)
        raise
    print(f'Annotation gallery: http://127.0.0.1:{server.server_port}',flush=True)
    if args.open_browser:
        threading.Thread(target=webbrowser.open,args=(url,),daemon=True).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
