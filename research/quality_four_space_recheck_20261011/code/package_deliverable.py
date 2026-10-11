from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
def main():
 dst=ROOT/'artifacts';dst.mkdir(exist_ok=True);p=dst/'quality_four_space_recheck_20261011_user.zip'
 files=sorted((ROOT/'user').rglob('*'))
 with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
  for f in files:
   if f.is_file():
    info=zipfile.ZipInfo(f.relative_to(ROOT/'user').as_posix(),date_time=(2026,10,11,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,f.read_bytes(),compresslevel=8)
 b=p.read_bytes();result={'artifact':p.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'entry':'index.html','file_count':sum(f.is_file() for f in files),'original_feedback_sha256':'8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c','QA_states_or_screenshots_in_user_zip':False};(ROOT/'ARTIFACT_MANIFEST.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(result)
if __name__=='__main__':main()
