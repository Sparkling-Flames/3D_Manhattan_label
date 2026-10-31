"""Figure delivery must preserve saved values and unavailable support."""
import pandas as pd
from PIL import Image
from tools.thesis_main.analysis.report_doorway_delta_20261031 import OUT


def test_saved_figure_data_and_export_formats():
    rows=pd.read_csv(OUT/'CHANGED_POOL_CURVES_DATA.csv')
    current=rows[rows.version.eq('Scope corrected')]
    source=pd.read_csv(OUT/'CORRECTED_NATURAL_CURVES.csv')
    paired=current.merge(source[source.metric.eq('B8L2')],on=['pool_id','k'],validate='one_to_one',suffixes=('_figure','_source'))
    assert len(paired)==len(current)
    pd.testing.assert_series_equal(paired.mean_figure,paired.mean_source,check_names=False)
    assert not current.pool_id.str.contains('jtcxE69GiFV-12__manual__space2').any()
    assert rows.pool_id.nunique()==8
    with Image.open(OUT/'CHANGED_POOL_CURVES.png') as im:
        assert im.size==(4200,4800)
        assert all(abs(d-300)<.1 for d in im.info['dpi'])
    assert (OUT/'CHANGED_POOL_CURVES.pdf').read_bytes().startswith(b'%PDF')
    assert '<svg' in (OUT/'CHANGED_POOL_CURVES.svg').read_text(encoding='utf8')
