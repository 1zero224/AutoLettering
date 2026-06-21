import json
from pathlib import Path

from PIL import Image

from autolettering.phase1 import run_phase1


def test_run_phase1_writes_manifest_debug_pages_sample_and_report(tmp_path: Path):
    project_dir = tmp_path / "sample_project"
    output_root = tmp_path / "outputs"
    project_dir.mkdir()
    Image.new("RGB", (100, 200), "white").save(project_dir / "page_01.png")
    (project_dir / "翻译_0.txt").write_text(
        """1,0
-
框内
框外
-
Comment

>>>>>>>>[page_01.png]<<<<<<<<
----------------[1]----------------[0.250,0.500,1]
第一条

>>>>>>>>[missing.png]<<<<<<<<
----------------[1]----------------[0.100,0.200,2]
缺图条目
""",
        encoding="utf-8",
    )

    run_dir = run_phase1(
        project_dir / "翻译_0.txt",
        output_root=output_root,
        run_id="test-run",
        sample_limit=1,
    )

    assert run_dir == output_root / "test-run"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "debug" / "label_points" / "page_01.png").exists()
    assert (run_dir / "reports" / "phase1-report.md").exists()

    sample_records = [
        json.loads(line)
        for line in (run_dir / "samples" / "phase1-sample.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(sample_records) == 1
    assert sample_records[0]["record_id"] == "page_01.png#1"
    assert sample_records[0]["image_name"] == "page_01.png"

    report = (run_dir / "reports" / "phase1-report.md").read_text(encoding="utf-8")
    assert "Available images: 1" in report
    assert "Missing images: 1" in report

