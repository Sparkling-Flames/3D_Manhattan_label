from pathlib import Path
import re
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
TOP=ROOT/'research/workers/image_response_v21_20261101'


def test_onset_plot_keeps_group_denominators_and_values():
    d=pd.read_csv(TOP/'HOHONET_v21_image_response_20261101/stage08_figures/01_Onset_by_Difficulty_data.csv.gz')
    for group,n,found in [('Easy',130,123),('Medium',39,25),('Hard',37,15)]:
        r=d[d.metric.eq('B8L2_mean')&d.difficulty.eq(group)].sort_values('k')
        assert r.all_images.eq(n).all() and r.iloc[-1].onsets_at_or_before_k==found
        assert ((r.proportion-r.onsets_at_or_before_k/n).abs()<1e-12).all()
    for ext in ['png','svg','pdf']:
        assert (TOP/f'integration/01_Onset_by_Difficulty.{ext}').stat().st_size>1000


def test_integrated_section_links_all_figures_and_cases():
    page=ROOT/'research/statistics/research_explorer_v1_r2_20261017/v21-results.html'
    html=page.read_text(encoding='utf-8')
    assert html.count('id="image-response"')==1
    section=html.split('<section id="image-response">')[1].split('</section>')[0]
    assert section.count('<figure>')==6
    for url in re.findall(r'(?:href|src)="([^"]+)"',section):
        assert (page.parent/url.split('#')[0]).exists(),url
    for token in ['163图','43图','16升11降','3770','3516/4352','VFua','e9z','pa4','uNb','jh4']:
        assert token in section
    assert '不是在线停标规则' in section
