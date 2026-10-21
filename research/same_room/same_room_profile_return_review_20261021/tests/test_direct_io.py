import unittest,tempfile,json,gzip
from pathlib import Path
import pandas as pd
from direct_io import read_csv,read_json,write_csv,write_bytes,open_data,data_exists
class DirectIOTest(unittest.TestCase):
 def test_csv_headers_and_order(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'events.csv.parts';p.mkdir()
   (p/'a.csv').write_text('id,value\n1,a\n2,b\n');(p/'b.csv').write_text('id,value\n3,c\n')
   (p/'index.json').write_text(json.dumps({'kind':'csv','parts':[{'path':'a.csv'},{'path':'b.csv'}]}))
   self.assertEqual(read_csv(Path(d)/'events.csv.gz').id.tolist(),[1,2,3])
 def test_writes_are_plain(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.csv.gz';write_csv(pd.DataFrame({'id':[1]}),p,index=False)
   self.assertFalse(p.exists());self.assertEqual(p.with_suffix('').read_text(),'id\n1\n')
   q=Path(d)/'x.json.gz';write_bytes(q,gzip.compress(b'{"a":1}'))
   self.assertEqual(q.with_suffix('').read_bytes(),b'{"a":1}')
   with open_data(q,'wt') as f:f.write('{"a":2}')
   self.assertEqual(read_json(q),{'a':2})
 def test_duplicate_json_keys_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.json.parts';p.mkdir()
   for name in ['a.json','b.json']:(p/name).write_text('{"same":1}')
   (p/'index.json').write_text(json.dumps({'kind':'dict','parts':[{'path':'a.json'},{'path':'b.json'}]}))
   with self.assertRaises(ValueError):read_json(Path(d)/'x.json')
if __name__=='__main__':unittest.main()
