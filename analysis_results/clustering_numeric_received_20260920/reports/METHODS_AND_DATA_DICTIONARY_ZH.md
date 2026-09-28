# 方法、分母与输出字典

## 输入和对应

canonical ID为版本化作答身份，不等于独立人员数；独立单位为同图同条件的不同worker。原始点、有效点和借用补点并存。上下角色沿用源条件性角色划分；唯一横向绑定用精确DP另查，但不赋予物理真值。跨人默认使用按约定排序的固定点对序号；人工完整映射只覆盖明确确认的一对。

坐标W=1024,H=512，x右增、y下增，使用原球面实现的半像素中心。θ=2π(x+0.5)/W，φ=π(y+0.5)/H−π/2；单位方向r=(cosφ cosθ,cosφ sinθ,sinφ)。球面角距为atan2(||r×s||,r·s)，输出度。图上距离为sqrt(min(|Δx| mod W,W−(|Δx| mod W))²+Δy²)。完整作答距离是所有对应top和bottom端点距离最大值；既不是平均值，也不是差异总和，更无IoU、面积或3D深度权重。

不同有效点数用BLOCK=1e6表示不可相容硬门，这不是实测距离。分区输入保留8位小数，按canonical身份稳定并列选择。原始端点输出不做这种舍入替换。

## 分区

完整链接用簇间最远距离逐步合并、按阈值截断；代表为簇内距离和最小的真实成员，稳定并列。它保证组内两两距离≤阈值，但可能把相近作答分在不同组。

代表半径沿用既有贪心规则：在尚未分组的成员中，先取阈值内邻居最多的真实成员；再比平均距离；再以canonical身份破并列。把其尚未分组邻居归入该组，继续处理其余人。这不是全局最小代表数解，不是所有可能代表的软归属。输出同时给出一个成员与其他已选代表是否也相容。组内成员可以彼此超阈值。若只局部替换人工对应破坏三角不等式，连直径≤2倍半径的额外度量界也不能直接用。

## 精确有限池成对未覆盖

N个固定真实响应，第i位在其他N−1位中有m_i个容差近邻。随机先取k位且i尚未被取到时，i未覆盖的概率是C(N−1−m_i,k)/C(N−1,k)。对i等权平均，得到“随机下一位剩余响应无已观察近邻”的精确概率。组合数上界不足时分子为0；k=N时没有剩余对象，返回未定义，不返回0。

近邻由距离与阈值定义，不使用分区。因此只改成簇规则时此曲线必须完全不变。最终k=N−1的值是有限池中零近邻成员比例；不是对未来陌生人员的风险保证。

## 固定全池标签的后见曲线

全池某簇大小s，随机k人未见该簇的概率p0=C(N−s,k)/C(N,k)，恰见一人的概率p1=s*C(N−s,k−1)/C(N,k)。期望已见簇数Σ(1−p0)，期望单人簇数Σp1，期望重复支持簇数Σ(1−p0−p1)，未见全池质量Σ(s/N)p0。重复少数组可另按s>=2且s/N<=0.2筛选，但这是描述探针，单人仍留总体指标。

## 前缀重分簇

200条全局人员顺序按每图/每个固定子类实际可用人员投影；不重复抽同一人增加人数。每个前缀仅使用自己的距离子矩阵重新聚类。旧成员关系变化用增加一人前后的旧成员两两同簇指示比较，不按簇号直接比较。分母为旧成员对数；不足两旧人时未定义。只看簇数不够，簇数相同仍可能交换成员；K下降也可能仅为算法重分区。

主图固定N>=19面板、k<=18，避免图片面板随k变化。逐图完整N也保留。人员子类长短不同，`images`是簇数等量的图分母，`images_with_remaining_person`才是未覆盖量的可评价图数；两者不得混用。

## 人员轴与训练隔离

复用历史Q/T/S/B、Semi三指标及已有六种候选，不重新发明心理类型。每个轴在同任务/条件内消除任务截距，以连接的worker-task图估计零和人员效应。每个目标楼整体留出，训练拟合、标准化、支持判断、bootstrap及Ward分类均不读取目标楼响应。

继承候选支持：至少6条有效历史行、至少3栋训练楼；200次建筑bootstrap，95%区间及至少80%有效抽样决定正/负/未归类。符号只是相对该测量轴的偏移，不是好坏人格。Ward不均分，组数2/3只作历史最小候选。固定全历史旧名单的曲线明确标hindsight，不能作为留出有效性证据。

新几何特征另起命名空间：pair_disagreement与singleton，不替换Q。借用补点从几何训练子池剔除后重新分组，避免间接同行特征泄漏。旧OSPA30参考/编辑特征来源与当前局部距离不同，未捏造重算或新GT。

四人组合从真实不同人枚举，先固定4个验证人（按图key+canonical ID+validation的SHA排序），所有方法/配置复用同一验证集。不同图和配置的组合重叠不是独立样本；结果先图后建筑汇总，bootstrap是对固定预测/组合结果的条件性建筑重抽，不是人口因果置信区间。

## 3D辅助公式

相机高h取单位1，top仰角α>0，bottom俯角β>0。水平地面下半径ρ/h=cotβ，总高度H/h=1+cotβ*tanα。固定其他输入时，bottom-y影响半径并影响推导高度；top-y不影响半径；共同x改变方位不改变半径/高度。d logρ/dβ=−1/(sinβ cosβ)。近地平线条件数高，跨界记失败，不截断到有限值。该推导以相应竖直角为条件，原上下x不一致、遮挡、OOS及围墙连接不明确均不被拟合抹平。

## 文件解码与主键

- `independent_groups.json`：key=image_id|raw_condition；ids/workers按固定池顺序，matrices含automatic和human_correspondence，labels与representatives包含全部组合。
- `endpoint_differences.csv.gz`：逐原端点坐标与差异，点号1-based；不是点对中点。原点号与按x点对序号不可互换。
- `prefix_nodes.csv.gz`：unit/pool/view/method/subset_mask唯一。mask第i位对应prefix_pool_manifest中第i个canonical ID；标签按mask中递增pool index排列，uint8十六进制编码。Python：`np.frombuffer(bytes.fromhex(text), dtype=np.uint8)`。
- `prefix_arrivals.csv.gz`：每条实际回放的前缀mask、下一人的pool index。终点next_pool_index=-1。人工视图未改的237单元复用自动节点，不制造不同结果。
- `prefix_churn_events.csv.gz`：只存关系变化或簇数下降的非零事件；缺行不代表没回放。method_index依次是sphere的6/9/12×complete/representative，再image同顺序。
- `personnel/subtype_prefix_nodes.csv.gz`：pool对应subtype_prefix_pools.json，config/subtype通过subtype_prefix_roster_aliases.csv连接；顺序仍由同一global_worker_orders投影，非新增随机名单。
- `personnel/actual_fourperson_teams.csv.gz`：unit/team主键，四位真实人员及固定验证人；measurements表同主键。组合汇总indices字段引用这些team序号，不是独立实验ID。
- `review/comment_replies_16_plus_unb.json`：16项原文及uNb补充，defer保持原状态；新的数值解释与用户裁决分存。

CSV.GZ可用pandas.read_csv直接读取。空值、不可计算、无剩余人、无参考和不在训练支持中不是同一个状态；不要统一填零。
