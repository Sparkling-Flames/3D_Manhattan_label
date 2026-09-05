## 文献与可复用思想

以下是外部研究，不是本项目已验证的结论。PDF 链接注明版本；不能把模拟研究写成人类实测，也不能把高一致性写成更准确。

1. Peter Welinder, Steve Branson, Serge Belongie, Pietro Perona. (2010). **The Multidimensional Wisdom of Crowds.** *Advances in Neural Information Processing Systems 23*, 2424–2432. [会议PDF](https://papers.nips.cc/paper/4074-the-multidimensional-wisdom-of-crowds.pdf)。借鉴：能力、偏好、噪声不必压成单一能力分数；模型可以表现不同标注策略。边界：原工作并不保证本项目存在可辨认的自然人群类型，二值任务的潜变量模型也不能直接用于多边形。

2. Anne Chao, Lou Jost. (2012). **Coverage-based rarefaction and extrapolation: standardizing samples by completeness rather than size.** *Ecology*, 93(12), 2533–2547. DOI: 10.1890/11-1952.1. [出版社原文](https://esajournals.onlinelibrary.wiley.com/doi/abs/10.1890/11-1952.1)。借鉴：比较相同覆盖完整度，而不仅是相同人数；估计新增标注还会发现多少未覆盖模式。边界：必须先定义稳定模式；错误和聚类碎片不能机械当作新“物种”。本次未确认稳定可直达的官方全文PDF地址，不编造链接。

3. Jan Lorenz, Heiko Rauhut, Frank Schweitzer, Dirk Helbing. (2011). **How social influence can undermine the wisdom of crowd effect.** *Proceedings of the National Academy of Sciences*, 108(22), 9020–9025. DOI: 10.1073/pnas.1008636108. [作者机构PDF](https://www.sg.ethz.ch/publications/2011/lorenz2011how-social-influence/PNAS-2011-Lorenz-9020-5.pdf)。借鉴：独立新增证据、重复自查、接触他人答案，是三种不同的信息条件；分歧收缩不自动表示准确率提升。边界：数值估计实验，不是室内布局，不能预设同样方向。

4. Edward Vul, Harold Pashler. (2008). **Measuring the Crowd Within: Probabilistic Representations Within Individuals.** *Psychological Science*, 19(7), 645–647. DOI: 10.1111/j.1467-9280.2008.02136.x. [作者大学开放仓储](https://escholarship.org/uc/item/7x1799rm)。借鉴：同一个人也有重复判断变异；增加不同人和同人重复不等价。此轮只核查出处与研究框架，未将其效应量用于本项目规划。

5. Jacob Beck, Stephanie Eckman, Christoph Kern, Frauke Kreuter. (2026). **Bias in the Loop: How Humans Evaluate AI-Generated Suggestions.** *Harvard Data Science Review*, 8(2). DOI: 10.1162/99608f92.0e98898d. [已发表全文](https://hdsr.mitpress.mit.edu/pub/nrcn4h7d/release/2)；[2025作者预印本PDF，非最终发表版](https://arxiv.org/pdf/2509.08514)。借鉴：纠错负担、AI态度和错误性质可以分开研究；Wizard-of-Oz 可用于受控模拟系统而非先开发完整自动化。边界：发表版指出多项效果小；不能承诺本项目会有大效果，也不能由短任务推断疲劳阈值。

6. Hope Schroeder, Deb Roy, Jad Kabbara. (2025). **Just Put a Human in the Loop? Investigating LLM-Assisted Annotation for Subjective Tasks.** *Findings of the Association for Computational Linguistics: ACL 2025*, 25771–25795. DOI: 10.18653/v1/2025.findings-acl.1323. [官方PDF](https://aclanthology.org/2025.findings-acl.1323.pdf)。借鉴：建议呈现方式可以改变标签分布，机标人校的数据再用于评价同类模型可能带来评价偏移。版本核查：网页摘要的350人与本次打开的官方PDF摘要410人不一致，因此本说明不把网页人数直接当论文最终人数。边界：主观文本任务，不意味着几何分歧都合理。

7. Yin-Chun Lu. (2026). **Framing the Crowd: How Task Design Shapes Collective Expectation in Crowdsourcing Pedestrian Behavior Change.** *Proceedings of the Extended Abstracts of the 2026 CHI Conference on Human Factors in Computing Systems*, Article 997, 1–6. DOI: 10.1145/3772363.3799172. [ACM原文](https://doi.org/10.1145/3772363.3799172)。借鉴：相同任务目标下，说明的提问框架也可改变判断；HCI变量不只限于正确/错误模型初始化。边界：这是扩展摘要而不是CHI完整长文；原文部分分析把响应当独立观测，不应照搬其显著性分析到本项目的重复worker/task数据。

8. Miguel Monteiro, Loïc Le Folgoc, Daniel Coelho de Castro, Nick Pawlowski, Bernardo Marques, Konstantinos Kamnitsas, Mark van der Wilk, Ben Glocker. (2020). **Stochastic Segmentation Networks: Modelling Spatially Correlated Aleatoric Uncertainty.** *Advances in Neural Information Processing Systems 33*, 12756–12767. [会议PDF](https://papers.nips.cc/paper_files/paper/2020/file/95f8d9901ca8878e291552f001f67692-Paper.pdf)。借鉴：模拟完整且空间一致的几何解，而不是独立抖动每个角点。边界：概率分割网络不是经过验证的人类行为模拟器；本项目当前无需立即训练同等规模网络。

9. Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang. (2024). **No More Ambiguity in 360° Room Layout via Bi-Layout Estimation.** *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 28056–28065. [作者预印本PDF](https://arxiv.org/pdf/2404.09993)；[会议条目](https://openaccess.thecvf.com/content/CVPR2024/html/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.html)。借鉴：enclosed/extended 输出用于候选解释和局部歧义定位。边界：两种输出不是两名独立工人，也不是各自天然正确/错误的真值。
