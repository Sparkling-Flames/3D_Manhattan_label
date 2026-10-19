"""Independent streaming CRC, parsed-row count and hash check of all five tables."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,io,json,time
from datetime import datetime,timezone
from pathlib import Path
from pool_io import OUT,read,save,sha


class HashReader(io.RawIOBase):
    def __init__(self,source):self.source=source;self.hash=hashlib.sha256()
    def readable(self):return True
    def readinto(self,buffer):
        data=self.source.read(len(buffer));buffer[:len(data)]=data;self.hash.update(data);return len(data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',default='COMPARISON_INTEGRITY_CHECK.json')
    p.add_argument('--compare-to')
    a=p.parse_args();expected=read(OUT/'COMPARISON_COVERAGE.json');results=[];started=time.monotonic()
    previous={r['family']:r for r in read(OUT/a.compare_to)['files']} if a.compare_to else None
    for family,wanted in expected.items():
        path=OUT/(family+'.csv.gz');before=path.stat()
        with gzip.open(path,'rb') as source:
            h=HashReader(source)
            with io.TextIOWrapper(io.BufferedReader(h),encoding='utf-8-sig',newline='') as stream:
                parser=csv.reader(stream);header=next(parser);n=0
                for row in parser:
                    assert len(row)==len(header),(family,n,'row_width_changed')
                    n+=1
            decompressed_hash=h.hash.hexdigest()
        after=path.stat()
        assert n==wanted,(family,n,wanted)
        assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'file changed while checking'
        record=dict(family=family,file=path.name,rows=n,fields=len(header),bytes=after.st_size,
            compressed_sha256=sha(path),decompressed_csv_sha256=decompressed_hash,gzip_crc_valid=True)
        if previous:
            old=previous[family]
            record['same_as_previous_process']=all(record[k]==old[k] for k in ['rows','fields','bytes','compressed_sha256','decompressed_csv_sha256'])
            assert record['same_as_previous_process'],(family,'changed after previous independent process')
        results.append(record);print(family,n,'valid',flush=True)
    save(OUT/a.out,dict(checked_utc=datetime.now(timezone.utc).isoformat(),files=results,
        elapsed_seconds=time.monotonic()-started,compared_to=a.compare_to,
        method='Independent invocation; stream entire gzip to EOF/CRC, parse every CSV row/width, SHA256 compressed and decompressed bytes, verify stat unchanged while reading.',
        all_passed=True))


if __name__=='__main__':main()
