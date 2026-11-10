"""Plot matched feedback associations and verified Semi outcomes."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
BASE=Path(__file__).resolve().parents[3]/"research/difficulty/participant_feedback_20261109"
OUT=BASE/"figures"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8,"pdf.fonttype":42,"ps.fonttype":42,"svg.fonttype":"none"})
s=pd.read_csv(BASE/"results/difficulty_association_summary.csv")
f=plt.figure(figsize=(7.48,3.6))
a=f.add_axes([.225,.29,.225,.51])
rows=[]
for metric,comparison in [("omission","same_image_target"),("omission","same_person_same_building_image_centered"),("simplified","same_image_target"),("simplified","same_person_same_building_image_centered")]:
 r=s[(s.condition=="manual")&(s.factor=="occlusion")&(s.metric==metric)&(s.comparison==comparison)].iloc[0]
 rows.append(r)
for y,r in zip([3,2,1,0],rows):
 x=100*r.mean_difference; lo=100*r.lower_95; hi=100*r.upper_95
 a.plot([lo,hi],[y,y],color="#21618C",lw=1.3)
 a.plot(x,y,"o",color="#21618C",ms=4)
 a.text(x,y+.22,f"{x:+.2f}",ha="center",fontsize=7.5,color="#21618C")
a.set_yticks([3,2,1,0],["Omitted area\nSame image (72)","Omitted area\nSame person (24)","Simplification\nSame image (72)","Simplification\nSame person (24)"])
a.set_ylim(-.5,3.65);a.set_xlim(-9,4);a.set_xticks([-8,-4,0,4]);a.axvline(0,color="#9AA4AB",lw=.7,ls="--")
a.set_xlabel("Report − no report\n(percentage points)",fontsize=8)
a.tick_params(axis="y",length=0,pad=5)
for side in ["left","right","top"]:a.spines[side].set_visible(False)
f.text(.02,.96,"(a) Manual: reported occlusion and geometry",weight="bold",fontsize=9,va="top")
f.text(.02,.86,"1,016 responses; comparisons within image or person",fontsize=7.5)
f.text(.02,.045,"Bars: 95% cluster-resampling intervals.\nOmitted area is a fraction of the reference footprint.",fontsize=7.2,va="bottom")
m=f.add_axes([.50,.24,.49,.54]);m.set_xlim(0,5.3);m.set_ylim(0,3.25);m.axis("off")
f.text(.50,.96,"(b) Semi: reports and local outcomes",weight="bold",fontsize=9,va="top")
f.text(.50,.86,"138 responses on six known-defect tasks",fontsize=7.5)
states=["known_defect_retained_unchanged","known_duplicate_retained_after_other_edits","localized_duplicate_removed_exact","unknown_after_edit"]
heads=["Unchanged\nRetained","Edited\nRetained","Edited\nRemoved*","Edited\nUnknown"]
fills=["#F7E8D6","#F7E8D6","#DEF0E9","#E9ECEF"]
r=pd.read_csv(BASE/"inputs/figure_right_data.csv")
for col,h in enumerate(heads):m.text(1.17+col*1.025+.49,3.02,h,ha="center",va="center",fontsize=7.2)
matrix=[]
for key,label,n,y in [("specific_issue_reported","Specific issue\n(n = 89)",89,1.35),("acceptable_only","Acceptable only\n(n = 49)",49,.16)]:
 d=r[r.model_report_status.eq(key)].groupby("error_specific_state").responses.sum();counts=[int(d.get(k,0)) for k in states];assert sum(counts)==n;matrix.append(counts)
 m.text(0,y+.50,label,va="center",fontsize=7.5)
 for j,count in enumerate(counts):
  x=1.17+j*1.025;m.add_patch(Rectangle((x,y),.98,.98,facecolor=fills[j],edgecolor="white"))
  m.text(x+.49,y+.61,str(count),ha="center",fontsize=14,weight="bold");m.text(x+.49,y+.24,f"{100*count/n:.1f}%",ha="center",fontsize=7.3)
assert matrix==[[8,0,32,49],[12,1,0,36]]
f.text(.50,.045,"* Exact removal of the inserted duplicate.\nUnknown: edited; issue-specific correction unverified.",fontsize=7.2,va="bottom")
for ext in ["png","pdf","svg"]:f.savefig(OUT/f"participant_feedback.{ext}",dpi=300,facecolor="white")
plt.close(f)
print(OUT)
