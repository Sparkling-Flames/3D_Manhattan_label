# 五案最终代码（01–05）

本独立包只含01–05。代码从最终JSON快照重新构建全工程的网格、曲线、对象、集合、相机、灯光及修饰器；材质节点、世界环境和渲染设置由无几何的原生Blender模板保真。不是只打开完整模型重渲，也不是从照片重新推断几何。原始全景照片不是运行依赖。

## 环境和命令

已验证Blender 5.2.3 LTS、CPU Cycles，入口使用Python 3.9以上及标准库。保持run.py、scripts/、snapshots/和assets/相对位置即可整体移动。

```bash
python scripts/verify_package.py
python run.py --blender "/你的路径/blender" --case all --variant both --output "./rebuilt_output"
python run.py --blender "/你的路径/blender" --case 01 --variant presentation --render --views main reverse --output "./rendered_output"
python run.py --blender "/你的路径/blender" --case 01 --variant presentation --render --views main --percentage 25 --samples 8 --output "./quick_preview"
```

`--case`只接受01至05、对应完整目录名或all；all只处理本包五案。`--variant`为presentation、full_model或both。视图仅main/reverse。正式渲染默认原尺寸、96 samples，`--threads`默认4。macOS可执行文件通常为/Applications/Blender.app/Contents/MacOS/Blender；Windows按实际安装位置填写blender.exe。

## 内容和结果

- 10份JSON快照：顶点、边、面、UV、法线属性、变换、修饰器、集合、曲线、相机和灯光。
- 10份无几何着色模板：材质节点、程序纹理、世界与渲染设置，不是额外场景模型。
- scripts/提供快照导出、重建、重渲、白底合成与清单校验。
- 输出模型可直接编辑；validation.json记录保存并重新打开后的比对，validation_all.json汇总本次运行。渲染生成main.png/reverse.png和原生*_rgba.png。
- presentation为展示状态；full_model保留完整模型状态，可能遮挡内部。

修改快照或重建模型会形成新版本。导出器针对本批静态场景，不是通用Blender转换器；会拒绝不支持的对象、依赖、修饰器及未打包外部图像。

## 验证和边界

10个模型的结构与材质指纹重建检查通过，五案主视图在25%尺寸、8 samples下与冻结源模型逐像素一致。发布目录另实测一例CLI重建，详见verification/。这不表示重新渲染了所有正式高清图。

模型为照片支持的解释模型，不认证实测精度。未知边界保持原样；本包没有原照片、历史试验、GT或论文LaTeX。MANIFEST.json包含代码及必要输入哈希。
