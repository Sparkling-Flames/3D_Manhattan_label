"""Read-only display contract for the frozen same-room independent review."""
from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder
import pandas as pd


def test_interface_matches_sources():
    interface = builder.read(builder.SAME_ROOM_REVIEW)
    assert interface['schema'] == 'same_room_review_display_v1'
    assert interface['data_release'] == 'v2'
    assert interface['snapshot_id'] == builder.SNAPSHOT == 'v2_integrated_analysis_20261019'
    assert interface['source_commit'] == 'e83286b7814afc614253aa392050e9a3851ae058'
    ids = [spec['id'] for spec in interface['tables']]
    assert len(ids) == len(set(ids)) == 13
    for spec in interface['tables']:
        source = builder.ROOT / spec['source']
        assert source.is_file(), spec['source']
        frame = pd.read_csv(source, encoding='utf-8-sig')
        assert frame.columns.tolist() == spec['columns'], spec['id']
        assert len(frame) == spec['rows'], spec['id']
    tables, provenance = builder.load_declared_tables(interface)
    for spec in interface['tables']:
        assert len(tables[spec['id']]) == spec['rows']
        assert provenance[spec['id']] == spec['source']


def test_module_tabs_resolve():
    interface = builder.read(builder.SAME_ROOM_REVIEW)
    assert interface['module']['id'] == 'same_room_review'
    tabs = interface['module']['tabs']
    assert len(tabs) == 13
    assert all(title.strip() for title, _ in tabs)
    assert [tid for _, tid in tabs] == [spec['id'] for spec in interface['tables']]


def test_documents_exist_and_are_small():
    interface = builder.read(builder.SAME_ROOM_REVIEW)
    assert len(interface['documents']) == 1
    assert interface['documents'][0]['path'].endswith('/review/ADOPTED_INTERPRETATION.json')
    for spec in interface['documents']:
        path = builder.ROOT / spec['path']
        assert path.is_file()
        assert path.stat().st_size < 200_000
        assert builder.read(path)
