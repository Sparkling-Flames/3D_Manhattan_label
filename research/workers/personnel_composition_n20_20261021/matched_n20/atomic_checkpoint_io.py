"""Verified atomic CSV exports with per-process unique temporary paths."""
from __future__ import annotations
import csv,gzip,io,json,os,time,traceback
from pathlib import Path
from discover_n20_abc import HERE,sha

def save_csv(path,rows,fields=None,key=None):
    path=Path(path);rows=list(rows)
    if fields is None:fields=list(rows[0])
    token=f'{os.getpid()}.{time.time_ns()}'
    temporary=path.with_name(path.name+'.pending.'+token)
    zipped=str(path).endswith('.gz');phase='write';replaced=False
    try:
        if zipped:
            with temporary.open('wb') as raw:
                with gzip.GzipFile(filename=path.name,fileobj=raw,mode='wb') as compressed:
                    with io.TextIOWrapper(compressed,encoding='utf-8-sig',newline='') as f:
                        writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
                raw.flush();os.fsync(raw.fileno())
        else:
            with temporary.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
                f.flush();os.fsync(f.fileno())
        # Both text and compression writers are closed before readback.
        phase='readback';op=gzip.open if zipped else open
        keys=[];n=0
        with op(temporary,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);assert next(reader)==fields
            for row in reader:
                assert len(row)==len(fields);n+=1
                if key:keys.append(row[fields.index(key)])
        assert n==len(rows)
        if key:assert keys==[str(r[key]) for r in rows] and len(set(keys))==len(keys)
        phase='atomic_replace';os.replace(temporary,path);replaced=True
        return dict(path=str(path.relative_to(HERE)),rows=n,columns=len(fields),bytes=path.stat().st_size,sha256=sha(path))
    except Exception as error:
        record=dict(target=str(path),temporary=str(temporary),pid=os.getpid(),phase=phase,
          expected_rows=len(rows),expected_columns=len(fields),temporary_bytes=temporary.stat().st_size if temporary.exists() else None,
          exception_type=type(error).__name__,exception=str(error),traceback=traceback.format_exc(),
          completed_target_replaced=replaced,root_cause='not established; exception recorded without attributing filesystem, disk or interruption cause')
        failure=path.with_name(path.name+'.IO_FAILURE.'+token+'.json')
        failure.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        raise
