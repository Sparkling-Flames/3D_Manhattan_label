"""Offline regression tests. Run: python -m unittest -v test_portability.py"""
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parent

class PortableAuditTests(unittest.TestCase):
    def run_cli(self,*args,cwd=None,script=None):
        return subprocess.run([sys.executable,'-I','-S',str(script or ROOT/'audit.py'),*map(str,args)],cwd=cwd,capture_output=True,text=True)

    def test_relocated_default_source_reproduces_identical_outputs(self):
        with tempfile.TemporaryDirectory(prefix='gt-audit-') as tmp:
            tmp=pathlib.Path(tmp);pkg=tmp/'moved-package';out=tmp/'replay'
            shutil.copytree(ROOT,pkg,ignore=shutil.ignore_patterns('__pycache__'))
            result=self.run_cli('--out',out,cwd=tmp,script=pkg/'audit.py')
            self.assertEqual(result.returncode,0,result.stderr)
            for name in ['audit.json','validation.json']:
                self.assertEqual((ROOT/name).read_bytes(),(out/name).read_bytes(),name)

    def test_explicit_source_and_output(self):
        with tempfile.TemporaryDirectory(prefix='gt-audit-cli-') as tmp:
            out=pathlib.Path(tmp)/'results'
            result=self.run_cli('--source',ROOT/'fixtures/audit_input.json','--out',out,cwd=tmp)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((ROOT/'audit.json').read_bytes(),(out/'audit.json').read_bytes())

    def test_fixture_complete_and_hashes_verified(self):
        f=json.loads((ROOT/'fixtures/audit_input.json').read_text());v=json.loads((ROOT/'validation.json').read_text())
        self.assertEqual(len([x for x in f['images'] if x.get('confirmed_review')]),5)
        self.assertEqual(len([x for x in f['images'] if len(x['reference_points_1024x512'])==16]),35)
        self.assertTrue(v['all_replays_match']);self.assertTrue(v['source_unchanged'])
        self.assertEqual(hashlib.sha256((ROOT/'audit.json').read_bytes()).hexdigest(),v['audit_json_sha256'])

    def test_scope_cut_and_small_offset_not_conflated(self):
        a=json.loads((ROOT/'audit.json').read_text());p=next(x for x in a['images'] if x['image_code']=='pRbA3pwrgk9-02')
        right=p['edges'][1]['nearest_parallel_gt_support'];bottom=p['edges'][2]['nearest_parallel_gt_support']
        self.assertEqual(right['finite_segment_projection_overlap_h'],0)
        self.assertAlmostEqual(bottom['overlap_fraction_of_manual_projection'],.6998378496278347,places=12)
        self.assertAlmostEqual(bottom['max_abs_support_offset_h'],.004142749008012151,places=12)
        self.assertEqual(a['screenshot']['top_matches'][0]['image_code'],'q9vSo1VnCiC-12')
        self.assertFalse(a['screenshot']['top_matches'][0]['is_in_imported_confirmed_five'])
        self.assertEqual(a['screenshot']['compared_candidate_count'],35)

    def test_changed_gt_rejected(self):
        with tempfile.TemporaryDirectory(prefix='gt-audit-gt-') as tmp:
            tmp=pathlib.Path(tmp);source=tmp/'changed_gt.json'
            f=json.loads((ROOT/'fixtures/audit_input.json').read_text())
            f['images'][0]['reference_points_1024x512'][0][0]+=.1
            source.write_text(json.dumps(f))
            result=self.run_cli('--source',source,'--out',tmp/'out',cwd=tmp)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('original selected GT snapshots',result.stderr)
            self.assertFalse((tmp/'out/audit.json').exists())

    def test_changed_confirmation_fails_without_overwriting_output(self):
        with tempfile.TemporaryDirectory(prefix='gt-audit-reject-') as tmp:
            tmp=pathlib.Path(tmp);source=tmp/'changed.json';out=tmp/'out';out.mkdir()
            f=json.loads((ROOT/'fixtures/audit_input.json').read_text())
            next(x for x in f['images'] if x.get('confirmed_review'))['confirmed_review']['polygon'][0][0]+=.1
            source.write_text(json.dumps(f));(out/'audit.json').write_text('do not overwrite')
            result=self.run_cli('--source',source,'--out',out,cwd=tmp)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('original five',result.stderr)
            self.assertEqual((out/'audit.json').read_text(),'do not overwrite')

if __name__=='__main__':unittest.main()
