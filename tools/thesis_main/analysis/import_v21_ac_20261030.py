"""归档AC科研包；重复内容只存一次，版本差异保留原字节与来源映射。"""
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import json
import stat
import zipfile

from tools.thesis_main.analysis.import_v21_personnel_reselection_20261029 import safe_destination

ROOT = Path(__file__).resolve().parents[3]
DEST = ROOT / 'research/workers/personnel_ac_v21_20261030'


def import_packages(paths, destination):
    destination = Path(destination)
    entries = defaultdict(list)
    archives = {}
    try:
        for path in sorted(paths):
            archives[path.name] = z = zipfile.ZipFile(path)
            for info in z.infolist():
                if info.is_dir():
                    continue
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError('不接收归档符号链接')
                safe_destination(destination, info.filename)
                key = ('source_manifests/' + path.stem + '.json'
                       if info.filename == 'ARCHIVE_MANIFEST.json' else info.filename)
                entries[key].append((path.name, info))
        rows = []
        for relative, versions in entries.items():
            latest_name, latest_info = versions[-1]
            latest = archives[latest_name].read(latest_info)
            for name, info in versions:
                raw = latest if name == latest_name else archives[name].read(info)
                same = raw == latest
                target_rel = relative if same else 'source_variants/' + Path(name).stem + '/' + relative
                target = safe_destination(destination, target_rel)
                if target.exists():
                    if target.read_bytes() != raw:
                        raise ValueError(f'已有文件不同，不覆盖: {target}')
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)
                rows.append(dict(package=name, member=info.filename, path=target_rel,
                                 bytes=len(raw), canonical=same))
        with (destination/'SOURCE_PATH_MAP.csv').open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['package','member','path','bytes','canonical'])
            w.writeheader(); w.writerows(rows)
        receipt = dict(packages=len(archives), archive_entries=len(rows),
                       unique_files=len({r['path'] for r in rows}),
                       differing_versions=sum(not r['canonical'] for r in rows),
                       original_sources_deleted=False, scientific_reaudit=False,
                       precedence='lexical stage order; earlier differing bytes retained in source_variants',
                       validation='safe paths; ZIP read/CRC; existing destination byte equality; no extra hashes')
        (destination/'IMPORT_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return receipt
    finally:
        for z in archives.values():
            z.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path.home()/'Downloads')
    a = p.parse_args()
    packages = list(a.source.glob('HOHONET_v21_AC_*.zip'))
    if len(packages) != 13:
        raise ValueError(f'预期13个正式包，发现{len(packages)}')
    print(json.dumps(import_packages(packages,DEST),ensure_ascii=False))
