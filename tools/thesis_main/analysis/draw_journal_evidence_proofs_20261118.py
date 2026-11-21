"""Rebuild the panel PDFs and source-data extracts for the journal figure proofs."""
import json
from pathlib import Path
from shutil import copyfile

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from matplotlib.patches import Rectangle

from draw_tomm_cscw_method_panels import quality as q

ROOT = Path(__file__).resolve().parents[3]
THESIS = ROOT / "docs/thesis_main"
BASE = THESIS / "论文提纲_LaTeX_20261028"
OUT = THESIS / "论文写作工作资料/TOMM_CSCW并行准备_20261117/方法与人数图样_20261118"
PANELS = OUT / "panels"
DATA = ROOT / "research/data/doorway_review_20261030/screen439_results_20261031"
STAGE = next((ROOT / "research/workers/image_response_v21_20261101").rglob("stage03_response"))
BLUE, GOLD, GREY = "#006E9C", "#B84B13", "#62717A"
plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "pdf.fonttype":42,
                     "axes.spines.top":False, "axes.spines.right":False})


def save(fig, name):
    fig.savefig(PANELS / (name+".pdf"), bbox_inches="tight", pad_inches=.07)
    plt.close(fig)


def draw_room_edge_changes(ax, layout, lower):
    def vertices(room):
        return np.vstack([np.column_stack([room.xz, h])
                          for h in (np.zeros_like(room.heights), room.heights)])

    old, new = vertices(q.REF), vertices(layout)
    original = np.vstack(q.project(q.REF))
    edited = np.vstack(q.project(layout))
    moved = np.any(~np.isclose(old, new), axis=1)
    count = len(layout.xz)
    edges = [(i + offset, (i + 1) % count + offset)
             for offset in (0, count) for i in range(count)]
    edges += [(i, i + count) for i in range(count)]
    changed = [pair for pair in edges if moved[list(pair)].any()]
    assert len(changed) == (5 if lower else 3)
    for pair in edges:
        changed_edge = pair in changed
        ax.plot(*original[list(pair)].T, color=BLUE,
                ls='--' if changed_edge else '-', lw=1.2)
    for pair in changed:
        ax.plot(*edited[list(pair)].T, color=GOLD, lw=1.8)
    ax.scatter(*original[moved].T, s=17, facecolor='white', edgecolor=BLUE, zorder=4)
    ax.scatter(*edited[moved].T, s=23, facecolor=GOLD, edgecolor='white', lw=.5, zorder=5)
    ax.set_aspect('equal')
    ax.axis('off')


def draw_endpoint_examples(destination, *, cscw_scores=False):
    for kind, _, layout in q.formal_examples():
        lower = kind == "lower"
        metrics = q.score(layout)
        fig = plt.figure(figsize=(3.66, 1.30))
        room = fig.add_axes([.005, .02, .48, .96])
        if cscw_scores:
            draw_room_edge_changes(room, layout, lower)
        else:
            floor, top = q.draw_room(room, layout, highlight=False)
            ring = floor if lower else top
            room.plot(*ring[[1, 2, 3]].T, color=GOLD, lw=1.8, zorder=7)
            room.scatter(*ring[q.K], s=23, facecolor=GOLD, edgecolor='white', lw=.6, zorder=8)
        original_color = BLUE if cscw_scores else GREY
        room.set_xlim(-2.9, 3.15)
        room.set_ylim(-1.45, 4.02)
        zoom = fig.add_axes([.53, .09, .465, .80])
        reference = q.REF.xz[q.K]
        if lower:
            # Actual footprint edges clipped to a window around the moved corner.
            for neighbours in ([1, 2], [2, 3]):
                old = q.REF.xz[neighbours]
                new = layout.xz[neighbours]
                zoom.fill(*np.vstack((old, new[::-1])).T, color='#FAE2CF', zorder=1)
            zoom.plot(*q.REF.xz[[1, 2, 3]].T, '--', color=original_color, lw=1.15)
            zoom.plot(*layout.xz[[1, 2, 3]].T, color=GOLD, lw=1.8)
            x, y = reference
            zoom.plot([x-.17, x-.17, x], [y, y-.17, y-.17], lw=.8, color=GREY)
            zoom.scatter(*reference, s=18, facecolor='white', edgecolor=original_color, zorder=4)
            zoom.scatter(*layout.xz[q.K], s=21, color=GOLD, zorder=4)
            zoom.annotate('0.50 m', xy=(reference+layout.xz[q.K])/2, xytext=(1.48, 2.45),
                          ha='center', va='center', fontsize=8,
                          arrowprops=dict(arrowstyle='-', lw=.7, color=GREY))
            zoom.annotate('', xy=layout.xz[q.K], xytext=reference,
                          arrowprops=dict(arrowstyle='->', color=GREY if cscw_scores else GOLD, lw=1.1, shrinkA=2, shrinkB=2))
            zoom.set(xlim=(.72, 2.64), ylim=(1.50, 2.62))
        else:
            # Elevation of the actual wall from corner 1 to corner 2.
            length = np.linalg.norm(layout.xz[2]-layout.xz[1])
            old_height = q.REF.heights[q.K]
            height = layout.heights[q.K]
            zoom.fill([0, length, length], [old_height, old_height, height], color='#FAE2CF')
            zoom.plot([length, length], [0, old_height], color=BLUE, lw=1.3)
            zoom.plot([0, length], [old_height, old_height], '--', lw=1.15, color=original_color)
            zoom.plot([0, length], [old_height, height], color=GOLD, lw=1.8)
            zoom.plot([length, length], [0 if cscw_scores else old_height, height], color=GOLD, lw=1.5)
            zoom.scatter(length, old_height, s=18, facecolor='white', edgecolor=original_color, zorder=4)
            zoom.scatter(length, height, s=21, color=GOLD, zorder=4)
            dimension_x = length + .14
            for y in (old_height, height):
                zoom.plot([length+.04, dimension_x+.04], [y, y], color=GREY, lw=.65)
            zoom.annotate('', xy=(dimension_x, height), xytext=(dimension_x, old_height),
                          arrowprops=dict(arrowstyle='->' if cscw_scores else '<->', color=GREY, lw=1, shrinkA=0, shrinkB=0))
            zoom.text(dimension_x+.08, (height+old_height)/2, '0.50 m', va='center', fontsize=8)
            zoom.set(xlim=(2.57, 4.85), ylim=(2.57, 3.69))
        zoom.set_aspect('equal')
        zoom.axis('off')
        if cscw_scores:
            from matplotlib.offsetbox import AnnotationBbox, HPacker, TextArea
            from matplotlib.transforms import Bbox
            pieces = [('Q = ', '#16252B', 10, 'normal'), ('100', BLUE, 10, 'normal'),
                      (' → ', GREY, 10, 'normal'), (f'{metrics["Q"]:.2f}', GOLD, 13, 'bold')]
            score = HPacker(children=[TextArea(t, textprops=dict(color=c, size=size, weight=weight))
                                      for t, c, size, weight in pieces], align='baseline', pad=0, sep=0)
            fig.add_artist(AnnotationBbox(score, (.505, -.035), xycoords=fig.transFigure,
                                          annotation_clip=False, box_alignment=(0, .5), frameon=True, pad=.18,
                                          bboxprops=dict(facecolor='white', edgecolor='#A7AEB2', lw=.65)))
        fig.savefig(destination / f'edit_{kind}.pdf',
                    bbox_inches=Bbox.from_extents(0, -.24, 3.66, 1.30) if cscw_scores else None)
        plt.close(fig)
        if cscw_scores:
            continue
        (destination / f'{kind}_score.tex').write_text(f'{metrics["Q"]:.2f}', encoding='ascii')
        (destination / f'{kind}_direction.tex').write_text(f'{metrics["Ddir_deg"]:.2f}', encoding='ascii')


def edit_examples():
    draw_endpoint_examples(PANELS)
    layout=q.E.Layout(q.REF.xz.copy(),np.array([3.,3.,3.3,3.]))
    score=q.score(layout)["Q"]
    assert round(score,2)==98.27
    fig,ax=plt.subplots(figsize=(3.4,2.65))
    _,top=q.draw_room(ax,layout,highlight=True)
    ax.annotate("+0.30 m",top[q.K],(.0,4.35),ha="center",color=GOLD,
                arrowprops={"arrowstyle":"->","color":GOLD})
    ax.text(.5,.00,"Q   100 → 98.27",transform=ax.transAxes,ha="center",color=BLUE,weight="bold",fontsize=13)
    save(fig,"score_scale")


def real_corner():
    case=json.loads((BASE/"figure_package/dot_fig07/data/consensus_case.json").read_text(encoding="utf8"))
    team=case["teams"]["Team 2"]
    turn=team["turns"][0]
    obs=np.array([m["pair"] for m in turn["members"]])
    median=np.asarray(turn["pair"])
    assert turn["label"]=="A" and len(obs)==8 and team["threshold"]==5
    assert len({m["person"] for m in turn["members"]})==len(obs)
    np.testing.assert_allclose(np.median(obs,axis=0),median)
    # Pixel centres use the original 1024 x 512 annotation coordinates.
    pano=Image.open(ROOT/"research/workers/current_dstruct_ac_final_20261104/mechanisms/originals/jtcxE69GiFV-13.png")
    fig,ax=plt.subplots(figsize=(2.65,2.65))
    ax.imshow(pano,extent=[-.5,1023.5,511.5,-.5])
    for x,y in obs:
        ax.plot(*np.array([x,y]).T, color="#91CFE7",lw=.7,alpha=.92)
    ax.plot(*median.T,color=GOLD,lw=1.8,marker="o",ms=3)
    for x,y in median:
        ax.add_patch(Rectangle((x-26,y-15),52,30,fill=False,edgecolor="white",lw=1))
    ax.text(.5,-.025,"8 of 10 drew A · 5 required",transform=ax.transAxes,va="top",ha="center",
            color=BLUE,weight="bold",fontsize=8)
    ax.set(xlim=(565,805),ylim=(445,104));ax.axis("off")
    save(fig,"corner_photo")
    points=np.array(team['candidate']['points']).reshape(-1,2,2)
    np.testing.assert_allclose(points[:,0,0],points[:,1,0])
    az=(points[:,0,0]/1024-.5)*2*np.pi
    el=(.5-points[:,:,1]/512)*np.pi
    r=-1/np.tan(el[:,1])
    foot=np.asarray(team['candidate']['footprint'])
    np.testing.assert_allclose(foot,np.column_stack([r*np.sin(az),-r*np.cos(az)]),atol=1e-12,rtol=0)
    k=team['candidate']['feature_ids'].index(turn['node_id'])
    np.testing.assert_allclose(points[k],median)
    fig,ax=plt.subplots(figsize=(2.9,3.1))
    azimuth,elevation=np.deg2rad([18,25])
    screen_x=foot @ [np.cos(azimuth),np.sin(azimuth)]
    screen_y=foot @ [-np.sin(azimuth),np.cos(azimuth)] * np.sin(elevation)
    floor=np.column_stack([screen_x,screen_y])
    ceiling=floor.copy()
    ceiling[:,1]+=np.cos(elevation)*(1+r*np.tan(el[:,0]))
    ax.fill(*floor.T,color="#EFF4F6")
    for ring in (floor,ceiling): ax.plot(*np.vstack([ring,ring[0]]).T,color=GREY,lw=1.1)
    for i in range(len(foot)): ax.plot(*np.vstack([floor[i],ceiling[i]]).T,color=GREY,lw=.9)
    ax.plot(*np.vstack([floor[k],ceiling[k]]).T,color=GOLD,lw=2.8,marker='o',ms=4)
    ax.annotate("A",ceiling[k],(3,5),textcoords='offset points',weight='bold',color=GOLD)
    ax.set_aspect("equal");ax.axis("off")
    save(fig,"corner_to_edge")
    # Keep both photographic enlargements at the same horizontal scale and alignment.
    fig,axs=plt.subplots(2,1,figsize=(3.8,3.25))
    fig.subplots_adjust(left=.04,right=.94,bottom=.05,top=.97,hspace=.16)
    middle_x=median[0,0]
    np.testing.assert_allclose(obs[:,0,0],obs[:,1,0])
    for j,ax in enumerate(axs):
        x,y=median[j]
        assert all(np.sum(values < m)==np.sum(values > m)==4
                   for values,m in [(obs[:,j,0],x),(obs[:,j,1],y)])
        ax.imshow(pano,extent=[-.5,1023.5,511.5,-.5],interpolation="bilinear")
        ax.set(xlim=(middle_x-15,middle_x+10),ylim=(y+8.5,y-8.5))
        ax.set_aspect("equal")
        ax.axis("off")
        # The orange segment points into the wall edge between the two cutouts.
        end_y=y+8.5 if j==0 else y-8.5
        ax.plot([x,x],[y,end_y],color="white",lw=4.4)
        ax.plot([x,x],[y,end_y],color=GOLD,lw=2.1)
        ax.plot([middle_x-15,middle_x+10],[y,y],color="white",lw=1.5)
        ax.plot([middle_x-15,middle_x+10],[y,y],color=GOLD,lw=.8,ls="--")
        ax.scatter(obs[:,j,0],obs[:,j,1],s=46,facecolors=BLUE,edgecolors="white",lw=.8)
        ax.scatter(x,y,marker="D",s=125,facecolors="none",edgecolors="white",lw=2.7,zorder=4)
        ax.scatter(x,y,marker="D",s=125,facecolors="none",edgecolors=GOLD,lw=1.5,zorder=5)
    save(fig,"corner_detail")


def plateau_data():
    checks=[]
    for stage,domain,group in [("manual","ordinary_manual_main",None),("doorway","doorway_before","Before screening"),
                               ("doorway","doorway_after","After screening")]:
        stats=pd.read_csv(STAGE/stage/"POOL_K_STATISTICS.csv.gz")
        stats=stats[stats.domain==domain]
        saved=pd.read_csv(STAGE/stage/"PLATEAU_SENSITIVITY.csv.gz")
        saved=saved[(saved.domain==domain)&(saved.metric=="B8L2_mean")&(saved.minimum_valid_paths==64)]
        for image,curve in stats.groupby("image"):
            curve=curve.sort_values("k")
            n=int(curve.N.iloc[0])
            for tol in (2,3):
                onset=np.nan
                for k in range(3,n-max(5,int(np.ceil(.15*n)))+1):
                    tail=curve[curve.k>=k]
                    if (len(tail)==n-k+1 and tail.B8L2_valid_n.min()>=64 and
                        tail.B8L2_mean.notna().all() and np.ptp(tail.B8L2_mean)<=tol):
                        onset=k;break
                row=saved[(saved.image==image)&(saved.tolerance==tol)].iloc[0]
                assert onset==row.onset_k or (np.isnan(onset) and pd.isna(row.onset_k)),(image,tol)
                checks.append((domain,image,group or row.difficulty_en,n,tol,onset,row.reason))
            if image=="X7HyMhZNoso-19" and domain=="ordinary_manual_main":ex=curve[curve.k>=3].copy()
    checks=pd.DataFrame(checks,columns=['domain','image','group','pool_size','tolerance','onset','status'])
    checks.to_csv(OUT/'stability_by_image.csv',index=False)
    picked=checks[(checks.image==ex.image.iloc[0])&(checks.tolerance==2)].iloc[0]
    k=int(picked.onset); tail=ex[ex.k>=k];low,high=tail.B8L2_mean.agg(["min","max"])
    assert k==16 and round(high-low,2)==1.74
    ex[['image','k','N','B8L2_mean','B8L2_valid_n']].to_csv(OUT/'example_trajectory.csv',index=False)
    fig,ax=plt.subplots(figsize=(4.8,2.45),layout='constrained')
    ax.fill_between([k,ex.k.max()],low,high,color='#D6EAEF')
    ax.plot(ex.k,ex.B8L2_mean,'.-',color=BLUE,ms=4)
    ax.axvline(k,ls=':',color=GREY)
    ax.annotate(f"First qualifying size: {k}",(k,high),xytext=(.32,.93),textcoords="axes fraction",
                va="top",arrowprops={"arrowstyle":"-","color":GREY},fontsize=9)
    ax.text(.98,.57,f"Tail: {low:.2f}–{high:.2f}\nRange: {high-low:.2f} points",transform=ax.transAxes,
            ha="right",va="bottom",fontsize=9,bbox={"facecolor":"white","edgecolor":"none","alpha":.9})
    ax.set(xlabel="Team size (annotators)",ylabel="Mean team Q")
    save(fig,'tail')
    return checks


def draw_doorway_curves(fixed, targets):
    for completion in (False, True):
        suffix = "_completion" if completion else ""
        measure = "complete" if completion else "q"
        target_measure = "complete_rate" if completion else "mean"
        factor = 100 if completion else 1
        size = (3.65, 1.75 if completion else 2.6)
        ylabel = "Complete outputs (%)" if completion else "Mean team Q"

        fig, ax = plt.subplots(figsize=size, layout="constrained")
        for prefix, color, style in [("before", GREY, "--"), ("after", BLUE, "-")]:
            ax.plot(fixed.k, factor * fixed[f"{prefix}_{measure}"], marker="o", ms=3,
                    ls=style, color=color, label=f"{prefix.capitalize()} screening")
        ax.set(xlabel="Team size (annotators)", ylabel=ylabel, xticks=[3, 6, 10, 14])
        if completion:
            ax.set(ylim=(50, 103), yticks=[60, 80, 100])
        else:
            ax.legend(loc="lower right", frameon=False, fontsize=8)
        save(fig, "door_screen" + suffix)

        fig, ax = plt.subplots(figsize=size, layout="constrained")
        for group, color, marker, name in [("space1", BLUE, "o", "Space 1"),
                                           ("space2", GOLD, "s", "Space 2"),
                                           ("whole_compatible", "#13846B", "^", "Both spaces")]:
            rows = targets[targets.family == group].sort_values("k")
            ax.plot(rows.k, factor * rows[target_measure], color=color, marker=marker, ms=3,
                    label=f"{name} (n={rows.pool_n.iloc[0]})")
        ax.set(xlabel="Team size (annotators)", ylabel=ylabel, xticks=[3, 6, 10, 15])
        if completion:
            ax.set(ylim=(50, 103), yticks=[60, 80, 100])
        else:
            ax.set_ylim(0, 100)
            ax.legend(loc="lower right", frameon=False, fontsize=8)
        save(fig, "door_targets" + suffix)


def doorway(checks):
    image='7y3sRwLe3Va-18'
    fixed=pd.read_csv(DATA/'AGGREGATE_COMMON_SUPPORT.csv').query('3 <= k <= 14').copy()
    assert len(fixed)==12 and fixed.quality_images.eq(17).all()
    fixed[['k','quality_images','before_q','after_q','before_complete','after_complete']].to_csv(OUT/'doorway_fixed_panel.csv',index=False)
    curves=pd.read_csv(DATA/'NATURAL_CURVES.csv')
    screened=curves.query("family=='overall_after' and metric=='B8L2' and k in [3, 6, 14]")
    per_image=screened.pivot(index='image',columns='k',values=['mean','complete_rate','valid'])
    per_image.columns=[f'{measure}_k{k}' for measure,k in per_image.columns]
    onsets=checks[checks.domain=='doorway_after'].pivot(index='image',columns='tolerance',values='onset')
    per_image=per_image.join(onsets.rename(columns={2:'onset_2pt',3:'onset_3pt'}),validate='one_to_one')
    assert len(per_image)==17 and per_image.mean_k14.notna().all()
    for k in (3,6,14):
        np.testing.assert_allclose(per_image[f'mean_k{k}'].mean(),fixed.set_index('k').at[k,'after_q'])
    per_image.to_csv(OUT/'doorway_17_images.csv')
    targets=curves[(curves.image==image)&(curves.metric=='B8L2')&(curves.k>=3)&curves.family.isin(['space1','space2','whole_compatible'])]
    targets[['image','family','pool_n','k','mean','complete_rate','valid','attempts']].to_csv(OUT/'doorway_target_pools.csv',index=False)
    draw_doorway_curves(fixed, targets)
    fig,ax=plt.subplots(figsize=(6.8,2.65),layout='constrained')
    groups=['Easy','Medium','Hard']
    summary=[]
    for i,tol in enumerate([2,3]):
        v=checks[checks.tolerance==tol].groupby('group').onset.agg(['size','count','median'])
        summary.append(v.assign(tolerance=tol))
        for j,g in enumerate(groups):
            y=3-j+(.13 if i==0 else -.13)
            n=int(v.at[g,'size']);det=int(v.at[g,'count']);pct=100*det/n
            ax.hlines(y,0,pct,color='#C5D8E0' if i==0 else '#EDD5C7',lw=2)
            ax.plot(pct,y,'o' if i==0 else 's',color=BLUE if i==0 else GOLD,ms=6,
                    label=f'{tol}-point range' if j==0 else None)
            ax.text(pct+1.4,y,f'{det}/{n}',va='center',fontsize=8)
    pd.concat(summary).rename_axis('group').to_csv(OUT/'stability_summary.csv')
    ax.set(yticks=[3,2,1],yticklabels=['Easy','Moderate','Difficult'],xlabel='Panoramas with a sustained range of mean Q (%)',xlim=(0,110),ylim=(.45,3.4))
    ax.set_xticks([0,25,50,75,100])
    ax.legend(loc='lower right',frameon=False,fontsize=8)
    save(fig,'detection')


def same_room_wall_panels():
    inputs = BASE / "editorial_tools/figure_inputs"
    records = json.loads((inputs / "fig22_four_original_records.json").read_text(encoding="utf-8"))["records"]
    references = json.loads((inputs / "fig22_two_references.json").read_text(encoding="utf-8"))
    links = pd.read_csv(ROOT / "research/same_room/same_room_multiview_20261020/local_features_20261021/LOCAL_BEHAVIOR.csv")
    venues = [THESIS / name / "figure_package/panels/fig14" for name in ("CSCW改稿_20261117", "TOMM改稿_20261117")]

    def export(fig, name):
        fig.savefig(venues[0] / name, dpi=300)
        copyfile(venues[0] / name, venues[1] / name)
        plt.close(fig)

    for ref in references:
        code = ref["image_code"]
        view = code.split("-")[-1]
        entries = [r for r in records if r["pool_meta"]["image"] == code]
        image = np.asarray(Image.open(inputs / (entries[0]["pool_meta"]["image_id"] + ".png")).convert("RGB"))
        width, height = 1024, 512  # Coordinate system of the saved corner pairs.
        scale = image.shape[1] // width
        assert image.shape[:2] == (scale * height, scale * width) and scale >= 1
        photo_extent = (-.5, width-.5, height-.5, -.5)
        ref_pairs = np.asarray(ref["points_1024x512"]).reshape(-1, 2, 2)
        local = links.query("room == 'G057' and image_code == @code and condition == 'manual' and tolerance_deg == 3")
        edges = ref_pairs[np.sort(local.reference_corner.unique()) - 1]
        assert edges.shape == (2, 2, 2)
        top = int(edges[:, 0, 1].min()) - 15
        bottom = int(edges[:, 1, 1].max()) + 15
        span = bottom - top
        left = round(edges[:, :, 0].mean() - span / 2)
        cols = np.arange(left * scale, (left + span) * scale) % image.shape[1]
        # Wrap the panorama at the seam to keep the same physical crop for both people.
        crop = image[top * scale:bottom * scale][:, cols]
        extent = (left-.5, left+span-.5, bottom-.5, top-.5)
        context = plt.figure(figsize=(2.2, 2.2))
        locator = context.add_axes([.02,.63,.96,.35])
        locator.imshow(image, extent=photo_extent)
        locator.add_patch(Rectangle((edges[:,:,0].min()-8, top), np.ptp(edges[:,:,0])+16,
                                    span, fill=False, edgecolor="#ffdc45", linewidth=1.5))
        locator.set_axis_off()
        floor = context.add_axes([.05,.01,.90,.59])
        for person, worker, color, marker in [("A40","W112","#0072b2","o"), ("A41","W113","#d55e00","s")]:
            record, = [r["record"] for r in entries if r["record"]["worker_id"] == worker]
            pairs = np.asarray(record["points"]).reshape(-1, 2, 2)
            hits = local[local.object_id.eq(record["object_id"])]
            assert len(hits) == 2
            observed = pairs[hits.loc[hits.hit.eq(1), "source_pair_index"].astype(int)]
            assert len(observed) == (0 if (view,person) == ("07","A41") else 2)
            fig = plt.figure(figsize=(2.2, 2.2))
            ax = fig.add_axes([0,0,1,1])
            ax.imshow(crop, extent=extent)
            for edge in edges:
                ax.plot(*edge.T, color="#302508", lw=2.3)
                ax.plot(*edge.T, color="#ffdc45", lw=1.6, ls=(0,(3,2)))
            for edge in observed:
                ax.plot(*edge.T, color="white", lw=3)
                ax.plot(*edge.T, color=color, lw=1.65, marker=marker, ms=6,
                        markeredgecolor="white", markeredgewidth=.8)
            ax.set(xlim=extent[:2], ylim=extent[2:])
            ax.set_axis_off()
            export(fig, f"view{view}_{person}.pdf")
            lower = pairs[:,1]
            azimuth = 2*np.pi*(pairs[:,0,0]/width - .5)
            radius = 1/np.tan(np.pi*(lower[:,1]/height - .5))
            xy = np.column_stack([radius*np.sin(azimuth), -radius*np.cos(azimuth)])
            floor.plot(*np.vstack([xy,xy[0]]).T, color=color, ls="-" if person=="A40" else "--", lw=1.65)
            assert len(xy) == (16 if person=="A40" else {"07":9,"10":12}[view])
        floor.plot(0,0,"+",color="#242b30",ms=6)
        floor.set_aspect("equal")
        floor.set_axis_off()
        export(context, f"view{view}_context.pdf")


def main():
    PANELS.mkdir(parents=True,exist_ok=True)
    edit_examples()
    real_corner()
    same_room_wall_panels()
    doorway(plateau_data())
    tom=THESIS/'TOMM改稿_20261117/figure_package'
    for letter in 'abcd':
        copyfile(tom/f'panels/fig10/{letter}.pdf',PANELS/f'size_{letter}.pdf')
    controls=pd.read_csv(BASE/'supplement_sources/geometry/input/q_iou_eight_cases/results_all.csv')
    controls=controls[controls.case=='C4']
    tilt=q.E.Layout(q.REF.xz.copy(),3*(1+.2*q.REF.xz[:,0]/2))
    for n in (4,16):
        layout=q.add_points(tilt,n)
        expected=controls.loc[controls.candidate_nodes==n,'Q'].item()
        assert abs(q.score(layout)['Q']-expected)<.01
        fig,ax=plt.subplots(figsize=(2.8,2.55))
        bottom,top=q.project(layout)
        for ring in (bottom,top):
            ax.plot(*np.vstack([ring,ring[0]]).T,color=BLUE,lw=1.4)
            ax.scatter(*ring.T,s=9,color=GOLD,zorder=3)
        for j in [0,1,n-2,n-1]: ax.plot(*np.vstack([bottom[j],top[j]]).T,color=GREY,lw=.9)
        ax.set_aspect('equal');ax.axis('off')
        save(fig,f'subdivision_{n}')
    fig,ax=plt.subplots(figsize=(3.7,2.5),layout='constrained')
    for key,color,marker,label in [('Q',BLUE,'o','Q'),('prism_iou100',GOLD,'s','Corner-mean prism IoU'),
                                  ('weighted_prism_iou100',GREY,'^','Perimeter-mean prism IoU')]:
        ax.plot(controls.candidate_nodes,controls[key],color=color,marker=marker,ms=4,label=label)
    ax.set(xlabel='Annotated corner pairs',ylabel='Score',xticks=[4,8,12,16],yticks=[70,80,90,100],ylim=(67,103))
    ax.legend(loc='lower center',bbox_to_anchor=(.5,1.01),frameon=False,fontsize=7,ncol=2)
    save(fig,'subdivision_scores')


if __name__=='__main__':
    main()
