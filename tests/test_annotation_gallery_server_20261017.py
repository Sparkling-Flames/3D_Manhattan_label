from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import threading

import pytest

from tools.thesis_main.analysis.annotation_gallery_server_20261017 import create_server, existing_gallery_matches


@contextmanager
def serve(data,root):
    server=create_server(data,port=0,root=root,static_dir=root)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield server.server_port
    finally:server.shutdown();server.server_close();thread.join()


def request(port,method,path,body=None):
    connection=http.client.HTTPConnection('127.0.0.1',port)
    connection.request(method,path,body=json.dumps(body) if body is not None else None,
                       headers={'Content-Type':'application/json'})
    response=connection.getresponse(); payload=response.read();status=response.status;headers=dict(response.getheaders())
    connection.close()
    return status,payload,headers


@pytest.fixture
def source(tmp_path):
    root=tmp_path/'repo';root.mkdir();(root/'thumb.jpg').write_bytes(b'local-photo')
    data=root/'gallery.json'
    data.write_text(json.dumps(dict(version='gallery-v1',images=[dict(image_id='image',thumbnail_path='thumb.jpg',
        original_path='../private.jpg',title='view',annotations=[dict(worker_id='w')],references=[dict(id='r')])])),encoding='utf-8')
    (tmp_path/'private.jpg').write_bytes(b'outside-workspace-photo')
    return root,data


def test_partial_concurrent_save_restart_and_zero_null(source):
    root,data=source
    with serve(data,root) as port:
        assert request(port,'PATCH','/api/plans/image',dict(additional_people=0))[0]==200
        with ThreadPoolExecutor(2) as executor:
            updates=[executor.submit(request,port,'PATCH','/api/plans/image',patch) for patch in
                     [dict(additional_people=3),dict(note='需补充人员')]]
            assert all(future.result()[0]==200 for future in updates)
        plan=json.loads(request(port,'GET','/api/plans')[1])['plans']['image']
        assert plan['additional_people']==3 and plan['note']=='需补充人员'
        assert request(port,'PATCH','/api/plans/image',dict(additional_people=None))[0]==200
    with serve(data,root) as port:
        plan=json.loads(request(port,'GET','/api/plans')[1])['plans']['image']
        assert plan['additional_people'] is None and plan['note']=='需补充人员'
        status,body,headers=request(port,'GET','/api/export')
        assert status==200 and 'attachment' in headers['Content-Disposition']
        assert json.loads(body)['plans']['image']==plan


def test_overview_details_and_only_registered_safe_media(source):
    root,data=source
    with serve(data,root) as port:
        overview=json.loads(request(port,'GET','/api/data')[1])
        assert 'annotations' not in overview['images'][0] and 'references' not in overview['images'][0]
        detail=json.loads(request(port,'GET','/api/images/image')[1])
        assert len(detail['annotations'])==1 and len(detail['references'])==1
        assert request(port,'GET','/photo/image?kind=thumb')[1]==b'local-photo'
        assert request(port,'GET','/photo/image?kind=original')[0]==403
        assert request(port,'GET','/thumb.jpg')[0]==404
        assert request(port,'GET','/photo/../private.jpg')[0]==404
        with pytest.raises(OSError):create_server(data,port=port,root=root,static_dir=root)


def test_startup_recognizes_existing_gallery_without_replacing_service(source):
    root,data=source
    with serve(data,root) as port:
        version=json.loads(data.read_text(encoding='utf-8'))['version']
        url=f'http://127.0.0.1:{port}'
        assert existing_gallery_matches(url,version)
        assert not existing_gallery_matches(url,'different-gallery-version')
        assert request(port,'GET','/api/plans')[0]==200


@pytest.mark.parametrize('patch',[dict(additional_people=-1),dict(additional_people=True),dict(additional_people=1.5),
                                dict(note=3),dict(score=100)])
def test_bad_updates_are_json_and_do_not_write(source,patch):
    root,data=source
    with serve(data,root) as port:
        status,payload,_=request(port,'PATCH','/api/plans/image',patch)
        assert status==400 and 'error' in json.loads(payload)
        assert request(port,'PATCH','/api/plans/unknown',dict(note='bad'))[0]==404
    assert not data.with_name('supplement_plan.json').exists()
