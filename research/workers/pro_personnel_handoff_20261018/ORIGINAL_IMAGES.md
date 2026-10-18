# 原图不重复上传：已有GitHub Release

已于本轮通过公开网页确认Release与资产列表存在：

https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015

三个独立ZIP解压到同一目录得到`images/`：

- https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_01_of_03.zip
- https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_02_of_03.zip
- https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/download/quality-original-images-20261015/quality_original_images_20261015_03_of_03.zip

本包`IMAGE_INDEX.csv`来自本地对应Release制作清单，包含image_id、图号、source_path、archive_path及所在分包。覆盖263张：261张研究登记图及2张额外参考视角。额外参考图不增加作答分母。本轮发现该旧清单只覆盖当前261图中的259图；新增2t7WUuJeko7-02、2t7WUuJeko7-03的原图已按source_path补入本ZIP，当前图片对应见IMAGE_COVERAGE.csv；没有重新下载三个大ZIP验证远端每张图的字节。

离线展示页已经改用包内261张预览图，明确是预览，不是原图；坐标、评分与计算输入不变。需要细节审查时取Release原图。若需要恢复原仓库路径，可依据IMAGE_INDEX.csv将解压后的archive_path复制到本研究包内对应source_path；无需GitHub最新代码或上传新Release。

若Pro环境不能下载GitHub资产，先用包内预览完成数值与粗视觉研究，并明确哪些结论需要原图复核，不把未下载的原图说成已查看。
