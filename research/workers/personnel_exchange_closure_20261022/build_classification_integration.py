"""Preserve identities of inherited classifications and domain-coverage stages."""
from pathlib import Path
import hashlib, shutil
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=HERE/'classification'
PUB=ROOT/'research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy'
V3=ROOT/'research/workers/personnel_useful_taxonomy_v3_20261021'
EFF=ROOT/'research/workers/personnel_effective_exchange_conditions_20261022'

def main():
    OUT.mkdir(exist_ok=True)
    inputs=[]
    def copy(src,name):
        dst=OUT/name;shutil.copyfile(src,dst)
        inputs.append(dict(output=name,source=str(src.relative_to(ROOT)),bytes=dst.stat().st_size,
                           sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),identity='inherited_exact_no_refit'))
    for name in ['CLASS_DEFINITIONS.csv','CLASS_MEMBERS_AND_FEATURES.csv','JOINT_CLASS_MEMBERS_AND_FEATURES.csv',
                 'ALL_METHOD_LABELS_ALL_DATA.csv','PERSONNEL_LABELS_EXPLAINED.csv','CLASS_AUXILIARY_DOMAINS.csv',
                 'FIELD_GUIDE_ZH.md','RAW_GEOMETRIC_SIMILARITY_SUMMARY.csv','RAW_PREDICTION_SUMMARY.csv',
                 'OUTER_STABILITY_SUMMARY.csv']:
        copy(PUB/name,name)
    copy(V3/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz','ALL_METHOD_LABELS_LOBO.csv.gz')
    copy(EFF/'cross_condition_taxonomy/OLD_METHOD_LABELS_TARGET_MAPS.csv.gz','LEGACY_LABELS_TARGET_MAPS.csv.gz')
    copy(ROOT/'research/workers/personnel_taxonomy_20261021/labels/class_catalog.csv','LEGACY_M_SP_A2_CLASS_CATALOG.csv')
    cover=pd.read_csv(V3/'integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv')
    cover['closure_new_pure_domain_search']=False
    cover['closure_new_pure_domain_labels']=0
    cover['closure_status']='保留已筛查/已实验/机会不足的原阶段身份；本轮未重搜纯五域子集'
    cover['closure_relation']='本轮结构+Q/T类别含结构域；不是纯Q+T子集的新分类。Semi自身分类不是跨条件分类。'
    cover.to_csv(OUT/'DOMAIN_SUBSET_COVERAGE_26x2.csv',index=False)
    rows=[
      ('V3_BEHAVIOR','manual','Manual历史终稿结构及条件表达','ALL三粗三细（细层不另分）','59有标签/3未知',
       '结构解释；常规表达→较多转折的定向升质；按n/m控制稀释风险','主采用；本轮大团队扩展','楼外TURN/K3条件，按训练中心对齐，保留其他折的原标签'),
      ('V3_JOINT_QT','manual','Manual自身结构+Q+T','ALL五类；实际楼外可为4/5/6类','57有标签/5未知',
       '可解释的质量—时间方向；n20匹配大块替换','主采用；本轮首要用途实验','不是Manual+Semi联合；较快必须相对源类、折和实际人员子域解释'),
      ('V3_JOINT_QT','semi','Semi自身终稿结构/尺度+Q+T','ALL五类；逐折标签独立','54有标签；缺支持未知',
       '库存记录时间收益与质量取舍；具体成员风险','主采用；本轮匹配替换','Manual与Semi效果分开；不虚构新批初始化编辑轨迹'),
      ('V3_BEHAVIOR','semi','Semi终稿结构、近共线及尺度特征','ALL三粗四细','59有标签/3未知',
       '解释终稿简化、近共线分段和较多转折','保留解释分类；不以本轮联合结果替代其自身验证','新增节点不等同错误；Semi细类原机会支持保留'),
      ('M_structure','manual','旧Manual结构与条件历史','2粗4细','原方法资格域',
       '结构解释、父内细类替换及风险','保留；不被新三类全面替代','m5与m6的既有扩展结果分列，不能合并早期漂亮均值'),
      ('SP_scale','semi','旧Semi面积/高度表达','2粗3细','原方法资格域',
       '尺度方向与有容量时的父内细类用途','保留辅助','不能把SP当成联合类别的天然父类'),
      ('A2_relation','manual','跨图原答几何关系','原A2分区','原方法资格域',
       '原答相似性及指定n17/m9等块替换风险','保留对照','整份原答9/12度分簇阈值不同于融合内部对应参数'),
      ('Rnew2','manual','训练侧真实替换关系','原分区','新来源原支持域',
       '团队替换关系及条件可互换性','保留对照','旧768及新1040候选已实现；直接m2学习负结果保留'),
      ('F01','manual','高Q域中的相对时间','原快慢两类','旧23人；实际可用容量逐图',
       '简单图质量近似时的构成节时','保留条件效率用途','本轮不重复整轮快慢配比搜索；困难图原风险保留'),
      ('MV_QTD / QT+scope+Semi','separate','原五域组合、原输入条件','原方法各自层级','各自有机会人员域',
       '保留多变量分类及真实团队对照身份','保留已完成结果','D为难度适应；scope回答倾向不等于裁定正确率；旧QTDS的S为结构'),
      ('CROSS_CONDITION_NATIVE','separate','同人Manual+Semi楼外历史','原跨条件候选各自分区','原两条件机会支持域',
       '跨条件历史的辅助解释和原替换实验','保留探索/对照；本轮不新拟合','评价目标楼时两条件记录均排除；不合并Manual与Semi终点')]
    pd.DataFrame(rows,columns=['method','evaluation_condition','classification_inputs','hierarchy',
                              'people_support','intended_use','adoption','identity_and_scope']).to_csv(OUT/'CLASSIFICATION_SCHEME_CATALOG.csv',index=False)
    pd.DataFrame(inputs).to_csv(OUT/'INHERITED_SOURCE_MANIFEST.csv',index=False)
    print('classification integration saved',len(rows),'schemes; 52 domain-condition rows')

if __name__=='__main__':main()
