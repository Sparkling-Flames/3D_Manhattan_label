01–05最终图、可编辑工程与可运行代码 · 2026-11-07

这是只包含已完成五案的独立交付。
每案目录包含main.png、reverse.png、presentation.blend、full_model.blend、简短说明与渲染核验。共10张正式图、10个可编辑工程。
OVERVIEW.png为五案主视图总览，REVERSE_OVERVIEW.png为反向总览。

code/包含仅这五案的可运行代码、10份最终几何快照及10份无几何的材质/世界/渲染模板。代码从快照重新创建全工程，不是从原照片重新推断模型；原始全景不属于运行依赖。模板不是额外场景模型。按code/README_中文.md运行。

使用Blender 5.2.3 LTS，CPU Cycles、96 samples、AgX，正式图宽2400像素。只将渲染透明背景合成为白色，未重绘模型像素。不保证旧版Blender可以读取5.2工程。

五案是照片支持的解释模型，不是GT或1:1实测还原。模型距离、位置不代表实测精度。05的未知边界仍保持开放，不据此补完整房间。

MODEL_CHECK.json记录10工程在本发布目录的重开检查；code/verification记录10快照及渲染复现检查。PACKAGE_VALIDATION.json记录包内容；FILES.csv列出交付文件大小和SHA256（不含自身和根清单），MANIFEST.json另覆盖FILES.csv。没有原照片、旧稿、历史试图或LaTeX。
