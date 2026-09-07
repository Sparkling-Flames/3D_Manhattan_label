import json
import numpy as np
import pandas as pd
import pytest
from tools.thesis_main.analysis.prepare_uncertainty_visual_review import ARCHIVE, helpers, select, studio_data, preview_order


def test_order_audit_distinguishes_start_direction_from_changed_adjacency():
    from tools.thesis_main.analysis.audit_uncertainty_review_order import ring_edges
    assert ring_edges([0,1,2,3]) == ring_edges([2,3,0,1]) == ring_edges([3,2,1,0])
    assert ring_edges([0,1,2,3]) != ring_edges([3,2,0,1])  # Actual V01 proposal


def test_studio_two_assignments_and_bad_suffix():
    data = {'cases': [{'image_id': 'x'}]}
    assert studio_data('window.STUDIO_IMAGES={};window.STUDIO_DATA=' + json.dumps(data) + ';') == data
    with pytest.raises(ValueError):
        studio_data('window.STUDIO_DATA={"cases": []};unsafe();')
    actual = (ARCHIVE / 'analysis_results/panorama_studio_20260906_v2/data.js').read_text(encoding='utf-8')
    assert len(studio_data(actual)['cases']) == 12


def test_original_roles_seam_roundtrip_and_no_sort():
    audit, renderer = helpers()
    floor = np.array([[-3.,-1.,-3.], [3.,-1.,-3.], [3.,-1.,3.], [-3.,-1.,3.]])
    top = floor.copy(); top[:,1] = 1
    pixels = audit.project(np.stack([floor, top], axis=1).reshape(-1,3))
    snapshot = pixels.copy()
    f,t,mapping = audit.lift(pixels)
    assert np.allclose(f, floor) and np.allclose(t, top)
    assert mapping == [1,0,3,2,5,4,7,6]
    assert np.array_equal(pixels,snapshot)
    crossing = pixels.reshape(-1,2,2)[[0,2,1,3]].reshape(-1,2)
    with pytest.raises(ValueError, match='invalid_original_order'):
        audit.footprint(crossing)
    assert renderer.perspective(np.zeros((512,1024,3),dtype=np.uint8),0).size == (480,320)
    texture = np.full((512,1024,3), 120, dtype=np.uint8)
    for topview in (True,False):
        image = renderer.render(texture,f,t,top=topview,size=128)
        assert image.size == (128,128)
        assert (np.array(image) == 120).any()


def test_selection_counts_prior_review_exclusion_and_determinism():
    census = pd.read_csv(ARCHIVE / 'review_results/census/images_380.csv', keep_default_na=False)
    chosen = select(census)
    assert len(chosen) == chosen.image_id.nunique() == 50
    assert chosen.population_role.value_counts().to_dict() == {'historical_annotated':30,'candidate_without_historical_annotation':20}
    assert chosen.human30_id.eq('').all() and chosen.ai50_id.eq('').all()
    assert chosen.phase.eq('calibration').sum() == 5
    assert chosen.building_id.nunique() >= 15
    pd.testing.assert_frame_equal(chosen, select(census.sample(frac=1, random_state=42)))


def test_preview_order_preserves_coordinates_and_rejects_ambiguous_pairing():
    audit, _ = helpers()
    valid = np.array([[100,100],[100,400],[350,100],[350,400],[600,100],[600,400],[850,100],[850,400]], float)
    crossed = valid.reshape(-1,2,2)[[0,2,1,3]].reshape(-1,2).tolist()
    fixed, mapping, method = preview_order(crossed, audit)
    assert fixed == [crossed[i] for i in mapping]
    assert sorted(mapping) == list(range(8))
    assert audit.footprint(fixed).is_valid and method == 'existing_pairs_azimuth_order'
    grouped = np.vstack([valid[::2],valid[1::2]]).tolist()
    fixed, mapping, method = preview_order(grouped, audit)
    assert fixed == [grouped[i] for i in mapping]
    assert method == 'unique_vertical_pairing_then_azimuth_order'
    with pytest.raises(ValueError, match='already_computable'):
        preview_order(valid.tolist(), audit)
    ambiguous = [[100,100],[100,110],[100,400],[100,410],[600,100],[600,400]]
    with pytest.raises(ValueError, match='nonunique_vertical_pairing'):
        preview_order(ambiguous, audit)


def test_hd_adapter_preserves_original_pair_identity_and_vector_resolution():
    from tools.thesis_main.analysis.upgrade_uncertainty_review_hd import paired_payload, overlay_svg
    audit, _ = helpers()
    points = [[100,400],[100,100],[350,100],[350,400],[650,100],[650,400],[850,100],[850,400]]
    payload = paired_payload(points,audit)
    assert payload['ordered_pairs'][0] == {'source_pair_id':'raw:1/0','top':{'x':100.,'y':100.},'bottom':{'x':100.,'y':400.}}
    svg=overlay_svg(points,audit)
    assert 'width="2048" height="1024" viewBox="0 0 1024 512"' in svg
    assert 'href="panorama.png"' in svg
    assert svg.count('<circle')==len(points)
