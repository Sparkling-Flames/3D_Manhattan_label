import csv,hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PlainTablesTests(unittest.TestCase):
 def test_plain_tables_are_complete_and_readable(self):
  p=ROOT/'research/statistics/archive_layout_20261021/PLAIN_TABLES.json'
  for item in json.loads(p.read_text(encoding='utf8')):
   total=0
   for f in item['plain_files']:
    path=ROOT/f['path'];self.assertEqual(path.suffix,'.csv')
    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),f['sha256'])
    with path.open(encoding='utf8',newline='') as h:
     r=csv.reader(h);self.assertEqual(next(r),item['header']);n=sum(1 for _ in r)
    self.assertEqual(n,f['rows']);total+=n
   self.assertEqual(total,item['rows'])
if __name__=='__main__':unittest.main()
