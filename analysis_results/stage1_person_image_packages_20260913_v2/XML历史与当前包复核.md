# XML历史与当前分配包复核

## 旧版3D加载机制

实际回查Git：2026-03-09 `f8d7872e`、03-25 `0a77f7ed`、05-23 `5b76aca7`的`tools/label_studio_view_config_manual.xml`均使用：

```xml
<HyperText name="vis_3d" value="$vis_3d" valueType="url" inline="false"/>
```

2026-06-10 `1f55f3b8`中英文导入文件沿用`data.vis_3d`，英文明确指向`https://label.sparkle0825.top/tools/vis_3d.html`。当前中英文XML仍使用相同HyperText属性；本轮删减元标签没有更改这一段。任务7的地址仍为`http://175.178.71.217:8000/tools/vis_3d.html`，Project G/H仍为英文HTTPS地址。新Manual不复制旧查询中的参考点，但保留URL加载方式。

用户确认：旧部署在中文入口打开英文task、英文入口打开中文task，均会出现vis_3d错误；希望保留该效果。此次不新增域名拦截、不统一viewer地址、不变更服务器CORS。前面准备新增拦截的说明撤回，未落实为代码。

HyperText的URL加载与浏览器单独访问URL不是同一检查。官方说明确认URL资源可能在可直接访问时仍因CORS无法在标注界面加载：[HumanSignal排障说明](https://support.humansignal.com/hc/en-us/articles/16373613347597-Data-is-not-shown-on-the-labeling-screen)。因此“网址能单独打开”不能否定用户观察。

可确认的是旧XML入口和任务URL分流仍保留；不能从Git单独确认旧线上双向报错的完整原因。5月仓库nginx模板含`Access-Control-Allow-Origin: *`，没有显式按中英文拒绝的规则；实际线上响应、浏览器请求和部署模板可能不同。旧userscript也会单独创建viewer iframe，所以还要区分XML首次资源加载失败和脚本后续预览。尚未重现具体任务的交叉加载，不声称已经验证双向阻断。

本轮只读连通检查：中文viewer请求HTTP 200；英文viewer在浏览器打开显示“状态：就绪”。Python请求英文地址曾出现TLS EOF，这与浏览器结果不同，不据此断言服务器不可用。

## 分配与命名

中文文件为“任务7.xlsx”，sheet依据`export_label/标注人员.xlsx`使用9人的姓名。W017原记录为“张fl”，照原文保留，不猜全名。英文个人文件为Project G，不加姓名。Project H最后只提供20张图片，每人最多做20张，能做多少做多少；此前“20只是规划量、可超过20”的解释撤回。

Project H现已收到复核并定稿为12张门洞与8张同房视角；此前12张草稿已清除，用户原始13条复核记录独立保留。

当前可导入目录为任务7、Project G、Project H；运行时项目数字ID未提供，名称已确认不等于数字ID已绑定。[逐组使用核对](逐组使用核对.md)列出各图实际去向。用户要求先暂停XML核查，未将跨语言无法加载认定为已验证保障。
