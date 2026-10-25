# HOHONET 本轮最终下载索引

实际读取最新 main：`e88d1d443f4000715a50475e085a773661be9c04`；计算版本：`972857b2b3f548316be215400e42d6ef6e639250`；底层数据真人v2。

本表只登记实际存在的文件。最终主报告沿用仓库原主报告更新；没有向GitHub推送。各阶段标签、请求和结果保持原身份。

## 推荐阅读顺序

先看完整主报告或本轮新增章节，再看四个主要换类条件及71行完整条件表；人员名单与精确事件可以单独下载。后续需要图像、票账、几何或再聚合时，再取相应分包。

## 可单独取得的文件与各阶段分包

|文件|大小 MiB|下载|
|---|---:|---|
|人员分类与构成不确定性_主报告_更新至20261025.md|0.12|[本地文件](final/人员分类与构成不确定性_主报告_更新至20261025.md)|
|20261025_新增分类与有效换类章节.md|0.03|[本地文件](final/20261025_新增分类与有效换类章节.md)|
|有效换类条件_20261025.csv|0.00|[本地文件](final/有效换类条件_20261025.csv)|
|FINAL_CONDITIONS_COMPACT.csv|0.13|[本地文件](analysis/FINAL_CONDITIONS_COMPACT.csv)|
|METHOD_ADOPTION_DECISIONS.csv|0.04|[本地文件](analysis/METHOD_ADOPTION_DECISIONS.csv)|
|LABELS_ALL.csv|0.28|[本地文件](final/LABELS_ALL.csv)|
|LABELS_LOBO.csv.gz|0.19|[本地文件](final/LABELS_LOBO.csv.gz)|
|ALL_EVENTS_EXACT.csv.gz|17.50|[本地文件](final/ALL_EVENTS_EXACT.csv.gz)|
|UNIQUE_ENDPOINT_INVENTORY.csv.gz|15.28|[本地文件](final/UNIQUE_ENDPOINT_INVENTORY.csv.gz)|
|CONFIRM_Q_SEPARATION.png|0.38|[本地文件](analysis/figures/CONFIRM_Q_SEPARATION.png)|
|SIZE_THRESHOLD_MECHANISM_ZH.png|0.95|[本地文件](cases_size_threshold/SIZE_THRESHOLD_MECHANISM_ZH.png)|
|HOHONET_换类区分度_阶段01_分类与精确实验设计_20261025.zip|25.98|[下载](https://chatgpt.com/library?file_id=libfile_1d33de76958081918eb161162734dba5&account_id=personal)|
|HOHONET_换类区分度_阶段02A_完整事件与比较结果_20261025.zip|88.09|[下载](https://chatgpt.com/library?file_id=libfile_c76103eb10248191a3d44565baeaf644&account_id=personal)|
|HOHONET_换类区分度_阶段02B_68009团队端点_20261025.zip|45.31|[下载](https://chatgpt.com/library?file_id=libfile_36f7db0ef2888191ae5a96e6147d3520&account_id=personal)|
|HOHONET_换类区分度_阶段02C_四个原图票数机制案例_20261025.zip|14.49|[下载](https://chatgpt.com/library?file_id=libfile_81b119cd9a748191894636359bfdaf8e&account_id=personal)|
|HOHONET_换类区分度_阶段03_反推分类与精确扩展登记_20261025.zip|33.09|[下载](https://chatgpt.com/library?file_id=libfile_c362450b3f7c819199bb177011cb2289&account_id=personal)|
|HOHONET_换类区分度_阶段04A1_前向扩展与7选6完整事件_20261025.zip|106.94|[下载](https://chatgpt.com/library?file_id=libfile_84fae378d1dc8191bac8b0197aec6bf1&account_id=personal)|
|HOHONET_换类区分度_阶段04A2_反推四方法完整事件_20261025.zip|77.04|[下载](https://chatgpt.com/library?file_id=libfile_c583ad32cfbc8191b16868c078013015&account_id=personal)|
|HOHONET_换类区分度_阶段04B_202694端点标量_20261025.zip|90.64|[下载](https://chatgpt.com/library?file_id=libfile_fd63d608e9508191bce09c9a2e323c41&account_id=personal)|
|HOHONET_换类区分度_阶段04C_202694端点几何_20261025.zip|40.91|[下载](https://chatgpt.com/library?file_id=libfile_a8896b1f0eb88191ac5640437c45b1f3&account_id=personal)|
|HOHONET_换类区分度_阶段05_固定块人数路径与28人换7人_20261025.zip|81.12|[下载](https://chatgpt.com/library?file_id=libfile_c4370f9941448191b418d31700f21fb0&account_id=personal)|
|HOHONET_换类区分度_阶段06B_反推与人数阈值机制案例_20261025.zip|10.66|[下载](https://chatgpt.com/library?file_id=libfile_98277f03310481918128616f6de28247&account_id=personal)|
|HOHONET_换类区分度_阶段06C_97552事件与283211端点总账_20261025.zip|46.83|[本地文件](deliverables/HOHONET_换类区分度_阶段06C_97552事件与283211端点总账_20261025.zip)|

精确字节数、SHA256及保存身份见 [DOWNLOAD_INDEX.csv](DOWNLOAD_INDEX.csv)。同名阶段01已经修复并替换为同一下载项的新版本：原67项中66项精确恢复，唯一未取得原字节的是首轮注册脚本，使用早期阶段02版本且已记录；标签、请求和事件没有改变。

## 分包职责与解压位置

- **06A**：最终主报告、全部标签／历史中心、比较表、必要小输入与实际代码。直接解压到仓库根目录，研究文件进入 `research/workers/personnel_exchange_discrimination_20261025/`，主报告进入 `docs/thesis_main/`。更新主报告前可先审阅包内补丁。
- **06C**：97,552事件、事件—端点关联及283,211去重端点库存。也解压到仓库根目录，保留其规范研究目录前缀。
- **01—05及06B**：压缩包内部路径从研究目录开始，解压到上述 `personnel_exchange_discrimination_20261025/` 目录。为避免旧脚本覆盖最终版本，依次解压01—05、06B，最后解压06A和06C。
- **02A／04A1／04A2／05**含完整逐事件指标；**02B／04B／04C／05**含各批端点标量和几何。最终库存逐端点指向真实批次，重复团队只需保留一个端点。
- **02C**是前四例；**06B**是新增反推小类与人数门槛反转两例。没有打包原图全集，仅保留机制案例所需原图与几何。

本轮97,552事件包括95,264严格ABC与2,288直接AC，覆盖170张普通Manual图、22栋楼。283,211去重端点中283,092新计算、119直接复用；记录为失败／不可评分的4,198端点仍在完整账中。

完整字段和恢复步骤见 [DATA_DICTIONARY.md](DATA_DICTIONARY.md)、[REPRODUCTION.md](REPRODUCTION.md)。不需要重新融合才能重聚合已保存结果。

## 保存状态

本独立索引是最后一批文件的下载入口。压缩包内的索引快照可能早于该包自身的保存，因而不列其自身下载身份；此处不会用计划文件冒充已经保存的文件。
