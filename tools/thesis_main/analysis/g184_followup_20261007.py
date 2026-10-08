"""复用已保存候选追踪同房身份、定位与达票环节，不新增融合规则。"""
import json
from collections import Counter
import numpy as np

from .research_artifact_io import ROOT,read_csv,write_csv,write_json
from .paired_split_research.study import angular
from .point_route_panel_20261005 import build_routes,member_key

SOURCE=ROOT/'analysis_results/adaptive_point_20261007/expanded'
OUT=SOURCE/'g184'


def trace_support(keys,result):
    overlaps=[]
    for g in result['identity_groups']:
        members={member_key(m) for m in g['members']};hit=len(keys&members)
        if hit:overlaps.append(dict(group=g['feature_id'],overlap=hit,support=g['support']))
    complete=[g for g in overlaps if g['overlap']==len(keys)]
    stage=('retained' if any(g['support']>=result['minimum_support'] for g in complete)
           else 'one_group_below_vote' if complete else 'split_before_vote')
    return dict(stage=stage,groups=overlaps)


def run():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from PIL import Image
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    OUT.mkdir(exist_ok=True)
    images={i['image']:i for i in json.loads((SOURCE/'inputs.json').read_text(encoding='utf-8'))['images']}
    states=json.loads((SOURCE/'candidates.json').read_text(encoding='utf-8'))['states']
    idx={(s['image'],s['route']):s['result'] for s in states}
    paths={r['image']:r['image_path'] for r in read_csv(SOURCE/'same_room_followup.csv')}
    reviews=json.loads((SOURCE/'review_requests.json').read_text(encoding='utf-8'))
    room=[];ledger=[];traces=[];sensitivity=[]
    fig,axes=plt.subplots(3,3,figsize=(21,11))
    for ax,(code,path) in zip(axes.flat,paths.items()):
        im=images[code];counts=Counter(len(r['points'])//2 for r in im['records'])
        room.append(dict(image=code,n=len(im['records']),pair_count_distribution=dict(sorted(counts.items())),
                         paired_count=len(idx[code,'paired']['candidate'].get('points') or [])//2,
                         adaptive_count=len(idx[code,'adaptive_incidence_v1']['candidate'].get('points') or [])//2,
                         semantic_cross_view_mapping='not_assigned'))
        ax.imshow(Image.open(path));ax.axis('off');ax.set_title(code+'  N='+str(len(im['records'])))
    fig.suptitle('G184既有同房分类：九个视角，未自动绑定跨视角墙角身份',fontsize=15)
    fig.tight_layout();fig.savefig(OUT/'room_overview.png',dpi=130);plt.close(fig)
    for request in reviews:
        code=request['image'];g=request['group'];im=images[code];records={r['id']:r for r in im['records']}
        joint={member_key(m) for m in g['joint_members']}
        buckets={'joint':g['joint_members'],'top_only':[m for m in g['top_members'] if member_key(m) not in joint],
                 'bottom_only':[m for m in g['bottom_members'] if member_key(m) not in joint]}
        trace=trace_support(joint,idx[code,'paired'])
        pp=np.asarray([m['points'] for m in g['joint_members']])
        traces.append(dict(image=code,n=len(im['records']),vote_minimum=idx[code,'paired']['minimum_support'],
                           top_support=g['top_support'],bottom_support=g['bottom_support'],joint_support=g['joint_support'],
                           joint_top_diameter_deg=float(angular(pp[:,0]-.5,pp[:,0]-.5).max()),
                           joint_bottom_diameter_deg=float(angular(pp[:,1]-.5,pp[:,1]-.5).max()),**trace))
        for theta in (5,9,12):
            routes=build_routes(im['records'],theta)
            for route in ('paired','top_anchor','bottom_anchor'):
                result=routes[route];t=trace_support(joint,result)
                sensitivity.append(dict(image=code,threshold=theta,route=route,tracked_joint_n=len(joint),stage=t['stage'],groups=t['groups']))
        photo=Image.open(paths[code]);x=g['center'][0][0]
        fig,axes=plt.subplots(1,3,figsize=(12,7))
        for ax,(kind,members),color,title in zip(axes,buckets.items(),('#ef3333','#ff9a00','#b855ff'),('原右下共同来源','只进入上端组的原点对','只进入下端组的原点对')):
            ax.imshow(photo,extent=(0,1024,512,0))
            for m in members:
                pair=np.asarray(m['points']);ax.plot(pair[:,0],pair[:,1],'-o',color=color,lw=1,ms=4,alpha=.8)
                ledger.append(dict(image=code,category=kind,record=m['id'],worker=m['worker'],processed_pair_index=m['pair_index'],
                    x=float(pair[0,0]),top_y=float(pair[0,1]),bottom_y=float(pair[1,1]),
                    annotation_pairs=len(records[m['id']]['points'])//2,
                    interpretation=('user_confirmed_wall_corner_endpoint_targets_unresolved' if code.endswith('-41') and (OUT/'USER_REVIEW.md').exists() else 'user_confirmed_same_corner' if code.endswith('-41') and kind=='joint' else 'shown_source_not_individually_certified')))
            ax.set_xlim(max(0,x-80),min(1024,x+110));ax.set_ylim(470,45);ax.axis('off');ax.set_title(title+'：'+str(len(members))+'人')
        fig.suptitle(code+' 原始基准点对；三列人员分开展示，非三个墙角；未改坐标',fontsize=12)
        fig.tight_layout();fig.savefig(OUT/(code+'_marginal_sources.png'),dpi=145);plt.close(fig)
    write_json(OUT/'room_inventory.json',room);write_json(OUT/'support_trace.json',traces)
    write_csv(OUT/'source_ledger.csv',ledger);write_json(OUT/'threshold_trace.json',sensitivity)
    write_json(OUT/'field_contract.json',dict(input='Saved current-bundle-derived 137-image candidates and inputs; G184 from existing room classification',
        units='processed_pair_index is zero-based in retained top/bottom input ring; one row per source pair/category',
        trace='Track the displayed joint members, not all people observing the physical corner. Distances in degrees; no GT or new fusion rule.',
        review='41 joint six confirmed in parent USER_REVIEW.md; subsequent orange/purple category-level same-corner and upper-target evidence in local USER_REVIEW.md when present. Shared room is not shared corner certification.',
        count='Different original pair counts describe expression differences, not a complete semantic annotation classifier.'))
    lines=['# G184：标法、定位与达票环节','',
        '同房九个视角共167份既有作答，来源与原图总览见room_inventory.json、room_overview.png。没有增加独立房间或新人员；本轮不改融合算法。', '',
        '## 26／41：首先是联合支持与边际支持的差别','',
        '|图|上／下／共同支持|绑定法中共同来源|上／下最大夹角|', '|---|---|---|---|']
    for r in traces:
        lines.append(f"|{r['image']}|{r['top_support']}／{r['bottom_support']}／{r['joint_support']}|{r['stage']}，最低票数{r['vote_minimum']}|{r['joint_top_diameter_deg']:.3f}°／{r['joint_bottom_diameter_deg']:.3f}°|")
    lines+=['','9°下26的五份、41的六份共同来源各自已经完整成组，低于9票才未进入绑定输出；并非这批观察已被绑定聚类拆散。用户对41同角定位分散的判断保留，但这六份分散在当前9°门内仍相容。', '',
        '独立／混合的新增支持来自不同人员集合：26额外上5人／下5人，41额外上3人／下5人。这些人的另一端位置与共同组不同。究竟是同目标定位分散，还是不同上下目标，需结合原图判断；不能只凭它们未进入联合组就判为不同标法，也不能默认都是定位噪声。', '',
        'threshold_trace.json仅跟踪同一批已展示共同成员在5／9／12°下是否同组和达票，不按参考分数选门限。41在5°拆成5＋1，9°／12°完整成6人组但未达9票；26在三门限均为完整5人组而未达票。', '',
        '## 同房跟进范围','',
        '九图均保存原作答点对数分布与五路已有结果。26和41新增节点已有不同实体角依据；其余七视角不能由点对数相同或同房关系直接认证相同标法／墙角。67原有玻璃顶与天花板分歧单列，不混为41的三个墙角。', '',
        ((OUT/'USER_REVIEW.md').read_text(encoding='utf-8') if (OUT/'USER_REVIEW.md').exists() else '下一项人工判断优先看41橙色与紫色来源的上下目标，已有红色六份无需重审。确认后才能判断独立端点的增量来自克服定位分散还是拼合了不同目标。')]
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':run()
