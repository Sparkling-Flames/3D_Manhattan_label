from pathlib import Path


def test_quality_core_modules_import():
    import tools.thesis_main.analysis.quality_core as quality_core
    import tools.thesis_main.analysis.quality_core.active_time
    import tools.thesis_main.analysis.quality_core.choice_parser
    import tools.thesis_main.analysis.quality_core.consensus_reliability
    import tools.thesis_main.analysis.quality_core.geometry_metrics
    import tools.thesis_main.analysis.quality_core.report_writer

    assert quality_core.ANALYZE_QUALITY_LEGACY_COMPAT is True


def test_quality_core_contract_flags():
    from tools.thesis_main.analysis.quality_core import contracts

    assert contracts.ANALYZE_QUALITY_LEGACY_COMPAT is True
    assert contracts.FORMAL_PIPELINE_ENTRY is False
    assert contracts.OUTPUT_SCHEMA_CHANGE_ALLOWED is False
    assert contracts.DRY_RUN_ONLY_FOR_SMOKE is True
    assert contracts.NO_WORKER_ROUTING is True
    assert contracts.NO_ADMISSION_DECISION is True
    assert contracts.NO_GT_MUTATION is True


def test_quality_core_boundary_files_exist():
    repo_root = Path(__file__).resolve().parents[1]

    assert (repo_root / "tools/thesis_main/analysis/quality_core/README.md").exists()
    assert (repo_root / "tools/thesis_main/analysis/analyze_quality.py").exists()
    assert (repo_root / "tools/label_studio/official/analyze_quality_formal.py").exists()
