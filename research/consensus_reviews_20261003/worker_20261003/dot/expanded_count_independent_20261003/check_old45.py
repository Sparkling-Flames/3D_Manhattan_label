import independent_verify as a
import io,json,csv
p=a.ROOT/'old45.wrapper.json';r=json.loads(p.read_text());old=list(csv.DictReader(io.StringIO(r['content'].lstrip('\ufeff'))));new=a.readc(a.D/'curves.csv');key=lambda r:(r['image'],r['method'],r['version'],r['k']);index={key(r):r for r in new}
a.writej('old45_checks.json',dict(old_means=len(old),old_images=len({r['image'] for r in old}),mean_max_difference=max(abs(float(r['iou_mean'])-float(index[key(r)]['iou_mean'])) for r in old),old_git_blob=r['sha']))
