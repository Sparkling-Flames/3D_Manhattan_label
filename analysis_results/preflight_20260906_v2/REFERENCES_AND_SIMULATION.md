# 算法模拟、工人响应与“收敛”：核查文献及可迁移思想

检索日期：2026-09-06。Google Scholar的检索页尝试访问未成功；改用相同英文关键词，在作者、会议、期刊官方页面和论文全文核验。不是系统穷尽综述，不声称导师实际指向下列任何一篇。检索词包括crowdsourcing worker simulation convergence、POMDP iterative improvement workflow、EM crowdsourcing、free-response crowdsourcing control。

## 一、最需要分开的三类研究

**参数/优化收敛。** 先设定工人生成模型，产生模拟响应；用EM或其他算法推断标签、能力和难度，比较似然、参数恢复误差和标签错误率。优化目标变平不等于参数正确或布局正确。

**数据量增加后的统计收敛。** 在固定概率模型的识别条件下，研究人数、任务量和集体信息量与误差率之间的关系。这种收敛不是“反复让同一人改图”，也不支持离开模型假设后仍统一20人足够。

**决策与交互流程控制。** 模拟隐含质量状态、投票和改进过程，算法决定继续收集、修订、复核或停止；效用同时考虑质量与成本。算法不一定直接生成标注，而是在不确定环境中控制人类工作流。这一类尤其值得与导师澄清。

## 二、原始文献与可核实入口

### 1. 平均成对统计量不是新发明
Wassily Hoeffding. 1948. **A Class of Statistics with Asymptotically Normal Distribution.** *The Annals of Mathematical Statistics*, 19(3), 293–325. DOI: 10.1214/aoms/1177730196.
[期刊/Project Euclid入口，含PDF按钮](https://doi.org/10.1214/aoms%2F1177730196)。本轮核对正式文献及摘要。U统计量的理论地位是现成基础；本轮显式有限抽样方差实现经过全部子集检验，但公式本身不能承担全部创新。

### 2. 交叉人员与任务的依赖
Art B. Owen. 2007. **The Pigeonhole Bootstrap.** *The Annals of Applied Statistics*, 1(2), 386–411. DOI: 10.1214/07-AOAS122.
[作者PDF，2007修订稿](https://artowen.su.domains/reports/pbs2.pdf)；[作者归档](https://arxiv.org/abs/0712.1111)。本轮读取作者PDF正文。其分别重抽行列的方法是在交叉、不平衡随机效应背景下讨论的近似性质，不是任何非线性几何聚合都自动有效。本轮固定面板结果使用精确有限抽样协方差，不冒称pigeonhole bootstrap。

### 3. 同时建模能力与难度，确实做了模拟工人
Jacob Whitehill, Paul Ruvolo, Tingfan Wu, Jacob Bergsma, Javier R. Movellan. 2009. **Whose Vote Should Count More: Optimal Integration of Labels from Labelers of Unknown Expertise.** *Advances in Neural Information Processing Systems 22*, 2035–2043.
[会议PDF](https://papers.nips.cc/paper_files/paper/2009/file/f899139df5e1059396431415e770c6dd-Paper.pdf)。作者顺序按PDF首页，而非网页不同顺序的元数据。GLAD将能力、难度与潜在二元真值关联；模拟中4–20工人、2000图像、40次重复，比较参数恢复及标签结果，另有真实人员实验。可以借鉴生成过程、参数恢复和模型错设压力测试的分层；不能把二分类真值模型直接当Manhattan完整几何的合理多解模型。

### 4. 有理论条件的谱初始化＋EM
Yuchen Zhang, Xi Chen, Dengyong Zhou, Michael I. Jordan. 2016. **Spectral Methods Meet EM: A Provably Optimal Algorithm for Crowdsourcing.** *Journal of Machine Learning Research*, 17(102), 1–44.
[官方全文入口](https://jmlr.org/papers/v17/14-511.html)；[官方PDF](https://www.jmlr.org/papers/volume17/14-511/14-511.pdf)。已核对正文及正式元数据。谱方法用于初始化，再以EM精化Dawid–Skene估计，在指定条件下研究统计收敛率，并用合成和真实数据比较。不能把任何EM最后不再变化称为该论文保证的最优正确率。

### 5. 收敛人数取决于集体信息量，而非固定常数
Chao Gao, Yu Lu, Dengyong Zhou. 2016. **Exact Exponent in Optimal Rates for Crowdsourcing.** *Proceedings of the 33rd International Conference on Machine Learning*, PMLR 48, 603–611.
[官方页面](https://proceedings.mlr.press/v48/gaoa16.html)；[官方PDF](https://proceedings.mlr.press/v48/gaoa16.pdf)。核对全文及摘要。在Dawid–Skene模型下，误差指数与工人数及集体Chernoff信息有关，并讨论准确初始化条件下的EM最优性。可借鉴“人数需求条件于人群信息”的思想；不把其渐近界直接变成布局任务的20人硬保证。

### 6. 算法控制人做改进，并不直接代替人标注
Peng Dai, Mausam, Daniel S. Weld. 2010. **Decision-Theoretic Control of Crowd-Sourced Workflows.** *Proceedings of the AAAI Conference on Artificial Intelligence*, 24(1), 1168–1174. DOI: 10.1609/aaai.v24i1.7760.
[AAAI官方页面及PDF入口](https://ojs.aaai.org/index.php/AAAI/article/view/7760)。本轮核对官方摘要和书目信息，未声称逐页审查证明。TurKontrol在质量与成本之间权衡，控制检查和改进构成的迭代工作流；属于不确定性下的规划，而不是直接图像标注算法。

### 7. 从模拟框架到真实参数与现场验证
Peng Dai, Mausam, Daniel S. Weld. 2011. **Artificial Intelligence for Artificial Artificial Intelligence.** *Proceedings of the AAAI Conference on Artificial Intelligence*, 25(1), 1153–1160. DOI: 10.1609/aaai.v25i1.8096.
[AAAI官方页面及PDF入口](https://ojs.aaai.org/index.php/AAAI/article/view/8096)。本轮核对官方摘要和元数据。该工作明确补充前述模型参数学习与真实Mechanical Turk流程控制。可借鉴的顺序是：写明响应/改进模型，实测估计参数，再用现场任务验证策略，不是先设定漂亮收敛结果再找人复现。

### 8. 完整的POMDP工作流路线
Peng Dai, Christopher H. Lin, Mausam, Daniel S. Weld. 2013. **POMDP-based control of workflows for crowdsourcing.** *Artificial Intelligence*, 202, 52–85. DOI: 10.1016/j.artint.2013.06.002.
[出版社页面，含View PDF](https://www.sciencedirect.com/science/article/pii/S000437021300057X)；[作者机构元数据](https://research.google/pubs/pomdp-based-control-of-workflows-for-crowdsourcing/)。本轮核对出版社摘要与元数据，未取得可稳定独立直链PDF，不编造下载地址。该文研究二元投票、迭代改进、切换工作流三类情形，将能力、难度和响应质量与POMDP控制结合，并报告真实平台验证。对本项目，历史独立标注可支持响应模型初查，但不能代替修订转移轨迹或动作成本数据。

### 9. 不是固定选项的开放式响应
Christopher H. Lin, Mausam, Daniel S. Weld. 2012. **Crowdsourcing Control: Moving Beyond Multiple Choice.** *Proceedings of the 28th Conference on Uncertainty in Artificial Intelligence (UAI 2012)*, 491–500.
[作者归档](https://arxiv.org/abs/1210.4870)；[作者PDF](https://arxiv.org/pdf/1210.4870)。本轮读取全文。LazySusan面对未预先穷举所有选项的开放式任务，以概率图模型、EM和动态请求响应进行控制，包含真实平台实验。它比固定二分类更接近开放式布局输出，但仍不能直接解决本项目的几何对应、规则内多解和参考可靠性。

### 10. 较新的规划求解加速方向
Zixuan Deng, Yanping Xiang. 2025. **A partitioning Monte Carlo approach for consensus tasks in crowdsourcing.** *Expert Systems with Applications*, 262, 125559. DOI: 10.1016/j.eswa.2024.125559.
[出版社摘要及章节片段](https://www.sciencedirect.com/science/article/abs/pii/S0957417424024266)。本轮只核对摘要与公开片段，未审查完整定理/PDF。它通过POMDP状态分解和Monte Carlo求解加速信息收集的停止时机决策，在合成与真实任务测试。这里加速的是规划器，不是证明人类标注必然收敛到正确布局。

## 三、本轮做了什么小型模拟

`preflight_deliver_20260906.py::em_demo`是可复现的受约束one-coin二分类EM演示，不是GLAD或上述论文的完整复现，也未拟合本项目工人。300模拟任务、40重复、3/5/10/20/40模拟人员；能力U(0.65,0.90)，共享标签翻转比例0/0.15，最大300轮，单位任务似然变化小于1e−8为优化收敛。未收敛重复不删除。

已保存所有重复、优化轨迹和错误率。20人时两组都40/40优化收敛，但物理模拟真值错误约0.004与0.15125。该差别由假定的共享翻转生成，只说明“优化收敛≠正确性收敛”，不说明本项目有15%错误下限。图中所有样本均标注synthetic。

## 四、对导师可能设想的谨慎解释

一种候选框架是：场景/任务状态＋工人响应模型 → 对标注、复核、修订动作作仿真 → 比较质量与代价的收敛/停止行为 → 少量真实新场景检验预测。该框架与POMDP工作流研究有联系，但它是基于文献的建议，不是导师原话确认。

现有数据足以检验有限人员响应分布、几何偏好、抽样和部分早期预测。要估计多轮修订的状态转移，需要同人初版/修订版、当时看到的候选、动作顺序及成本；要估计疲劳，需要可靠持续工作与休息事件及必要重复。若暂缺，可以做显式参数情景，不能称为经验验证的疲劳模型。正式Manual/机器/Semi比较还需独立正确性及实际初始化来源，不因模拟跑通而自动定稿。
