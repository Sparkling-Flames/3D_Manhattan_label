"""Portable CJK font selection for research plots; no session path dependency."""
from pathlib import Path
import os
import matplotlib.pyplot as plt
from matplotlib import font_manager

def configure_cjk_font(requested=None):
    explicit=requested or os.environ.get('HOHONET_CJK_FONT')
    if explicit and not Path(explicit).is_file():
        raise FileNotFoundError(f'CJK font does not exist: {explicit}')
    paths=([Path(explicit)] if explicit else [])+[
        Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/msyh.ttc',
        Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts/simhei.ttf',
        Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'),
        Path('/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'),
        Path('/System/Library/Fonts/PingFang.ttc')]
    chosen=next((p for p in paths if p.is_file()),None)
    if chosen:
        font_manager.fontManager.addfont(str(chosen))
        family=font_manager.FontProperties(fname=str(chosen)).get_name()
    else:
        known={f.name for f in font_manager.fontManager.ttflist}
        family=next((name for name in ['Noto Sans CJK SC','Microsoft YaHei','SimHei','PingFang SC'] if name in known),None)
        if family is None:
            raise FileNotFoundError('No CJK font found. Supply --font PATH or set HOHONET_CJK_FONT.')
    plt.rcParams['font.family']=family
    plt.rcParams.update({'axes.unicode_minus':False,'svg.fonttype':'none','font.size':10,
        'axes.spines.top':False,'axes.spines.right':False})
    return str(chosen) if chosen else family
