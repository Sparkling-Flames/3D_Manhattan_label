"""Exercise the offline manual-order page with a real Chromium browser.

The browser reads file:// assets, exports a CSV, and verifies version isolation.
It does not modify study inputs or create derived scientific measurements.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from .apply_manual_ring_orders_20261104 import ROOT


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--executable',type=Path)
    parser.add_argument('--single-process',action='store_true')
    args=parser.parse_args()
    out=ROOT/'research/fusion/manual_order_impact_20261104'
    evidence=out/'workbench_validation';evidence.mkdir(exist_ok=True)
    pagefile=ROOT/'research/statistics/research_explorer_v1_r2_20261017/v21-manual-order.html'
    (out/'WORKBENCH_CHECKS.json').write_text(json.dumps({'passed':False,'status':'running'})+'\n')
    results=[];errors=[];failed=[]
    with sync_playwright() as p:
        options=dict(headless=True)
        if args.executable:options['executable_path']=str(args.executable)
        if args.single_process:options['args']=['--single-process','--no-zygote','--in-process-gpu']
        browser=p.chromium.launch(**options)
        page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('requestfailed',lambda request:failed.append({'url':request.url,'failure':request.failure}))
        page.goto(pagefile.as_uri(),wait_until='load')
        page.evaluate('document.fonts.ready')
        page.wait_for_selector('#endpointSelect option',state='attached')
        data=page.evaluate('MANUAL_ORDER_DATA')
        assert len(data['endpoints'])==57 and len(data['images'])==22
        assert page.locator('#endpointSelect option').count()==57
        results.append({'check':'offline_initial_load','passed':True,'endpoints':57,'images':22})
        seen_images=set()
        for e in data['endpoints']:
            page.select_option('#endpointSelect',e['team_key']);page.select_option('#viewMode','assisted')
            page.wait_for_function('document.getElementById("erpImage").complete && document.getElementById("erpImage").naturalWidth===2048')
            image=page.locator('#erpImage').evaluate('(img)=>[img.naturalWidth,img.naturalHeight]')
            assert image==[2048,1024],(e['image'],image)
            seen_images.add(e['image'])
            score=page.locator('#scoreCards strong').first.inner_text()
            expected='未评分' if e['assisted']['B8L2'] is None else f"{e['assisted']['B8L2']:.3f}"
            assert score==expected,(e['team_key'],score,expected)
            assert page.locator('#nodeRows tr').count()==len(e['nodes'])
            assert page.locator('#referenceRows tr').count()==len(e['references'])
            page.select_option('#viewMode','automatic')
            assert page.locator('#scoreCards strong').first.inner_text()=='未评分'
            assert page.locator('#floorPlot polygon').count()==0
        assert len(seen_images)==22
        results.append({'check':'all_saved_endpoints_and_original_images','passed':True,'assisted':57,'automatic':57,'images_loaded':22})
        page.select_option('#viewMode','assisted')
        for image in sorted(seen_images):
            page.select_option('#imageFilter',image)
            assert page.locator('#endpointSelect option').count()==sum(e['image']==image for e in data['endpoints'])
        page.select_option('#imageFilter','')
        for module in data['modules']:
            page.select_option('#moduleFilter',module['module'])
            assert page.locator('#endpointSelect option').count()==int(module['endpoint_identities'])
        page.select_option('#moduleFilter','');page.select_option('#statusFilter','failed')
        assert page.locator('#endpointSelect option').count()==1
        assert page.locator('#scoreCards strong').first.inner_text()=='未评分'
        page.select_option('#statusFilter','scored');assert page.locator('#endpointSelect option').count()==56
        page.select_option('#statusFilter','')
        page.fill('#searchFilter','nonexistent_team_20261104');assert page.locator('#emptyState').is_visible()
        page.fill('#searchFilter','');assert page.locator('#endpointSelect option').count()==57
        results.append({'check':'all_image_module_status_and_empty_filters','passed':True,'image_filters':22,'module_filters':9})
        page.click('#openCandidate')
        assert page.locator('#scoreCards strong').first.inner_text()=='39.616'
        assert '未并入主' in page.locator('#versionBadge').inner_text()
        assert page.locator('#nodeRows tr').count()==9
        page.select_option('#viewMode','assisted')
        assert page.locator('#scoreCards strong').first.inner_text()=='未评分'
        assert '仍自交' in page.locator('#branchNote').inner_text()
        page.select_option('#viewMode','candidate')
        page.check('#showReference')
        options=page.locator('#sourceRecord option').all()
        assert len(options)==5
        page.select_option('#sourceRecord',index=1)
        assert '预处理后的源点位' in page.locator('#sourceInfo').inner_text()
        assert page.locator('#erpOverlay polyline').count()>20
        page.locator('#endpoint').screenshot(path=str(evidence/'coordinate_candidate_desktop.png'),style='.masthead{visibility:hidden}')
        results.append({'check':'coordinate_candidate_isolation_and_source_reference_overlays','passed':True,'candidate_B8L2':39.61561918763198,'fixed_coordinate_B8L2':None})
        with page.expect_download() as download_info:page.click('#exportCsv')
        file=evidence/'exported_fixed_coordinate_endpoints.csv';download_info.value.save_as(file)
        with file.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        assert len(rows)==57
        assert all(r['automatic_B8L2']=='' for r in rows)
        assert sum(r['assisted_B8L2']!='' for r in rows)==56
        assert all(r['human_order_seconds']=='' for r in rows)
        results.append({'check':'CSV_download_preserves_null_and_main_candidate_separation','passed':True,'rows':57,'main_scored':56})
        for status in ['保持','幅度变化','条件变化','需改写','尚不能判断']:
            page.select_option('#conclusionFilter',status)
            assert page.locator('#conclusionRows tr').count()==sum(r['status']==status for r in data['conclusions'])
        page.select_option('#conclusionFilter','')
        assert page.locator('#conclusionRows tr').count()==len(data['conclusions'])
        page.uncheck('#showReference');page.select_option('#sourceRecord','')
        page.select_option('#endpointSelect',data['endpoints'][0]['team_key']);page.select_option('#viewMode','assisted')
        page.evaluate('window.scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(evidence/'desktop.png'))
        page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)')
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(evidence/'mobile.png'))
        page.locator('#endpoint').screenshot(path=str(evidence/'mobile_endpoint.png'))
        results.append({'check':'conclusion_filters_and_responsive_layout','passed':True,'conclusions':len(data['conclusions']),'desktop_width':1440,'mobile_width':390,'horizontal_document_overflow':False})
        assert not errors,errors
        # Rapid filter changes can cancel an old file:// image request. Every
        # one of the 22 images was fully decoded above; distinguish cancellation
        # from a missing/unreadable asset instead of treating them as identical.
        cancelled=[r for r in failed if r['failure']=='net::ERR_ABORTED']
        asset_failures=[r for r in failed if r['failure']!='net::ERR_ABORTED']
        assert not asset_failures,asset_failures
        checks=dict(browser=browser.version,engine='Chromium headless shell' if args.single_process else 'Chromium',
                    url_scheme='file',network_requests_required=False,checks=results,
                    javascript_errors=errors,failed_asset_requests=asset_failures,
                    cancelled_requests_during_rapid_filter_changes=cancelled,
                    all_22_images_fully_decoded=True,
                    data_sha256=hashlib.sha256((pagefile.parent/'v21-manual-order/data.js').read_bytes()).hexdigest(),passed=True,
                    scope='new manual-order page; existing entry banners checked separately; not a whole historical workbench replay')
        (out/'WORKBENCH_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(checks,ensure_ascii=False,indent=2))
        browser.close()


if __name__=='__main__':main()
