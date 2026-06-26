from PIL import Image, ImageDraw

from experiments import (
    phase2_detect_text_regions,
    phase2_6_cta_first_cleanup,
    phase2_cta_threshold_sweep,
    phase3_context_font_selection,
    phase6_cleanup_quality,
    phase6_cleanup_gate,
    phase6_cleanup_escalation_gpt_background_repair,
    phase6_cleanup_escalation_gpt_replace,
    phase6_gpt_artifact_gate,
    phase6_replacement_quality,
    phase6_cleanup_retry,
    phase6_nonbubble_cleanup,
    phase6_nonbubble_gpt_replace,
    phase6_segmented_gpt_replace,
    phase7_8_integrated_smoke,
    phase7_8_gpt_quality_gate_smoke,
)


def test_phase2_detection_cli_accepts_ctd_mask_strategy():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args(
        [
            "--detection-strategy",
            "ctd_mask",
            "--ctd-max-edge-distance-px",
            "16",
        ]
    )

    assert args.detection_strategy == "ctd_mask"
    assert args.ctd_max_edge_distance_px == 16


def test_phase6_gpt_artifact_gate_experiment_writes_near_square_grid(tmp_path):
    source_run = tmp_path / "phase6-gpt"
    cleaned = source_run / "fallback_cleaned" / "page-1.png"
    replacement = source_run / "fallback_replacement_crop" / "page-1.png"
    cleaned.parent.mkdir(parents=True)
    replacement.parent.mkdir(parents=True)
    Image.new("RGB", (120, 120), "white").save(cleaned)
    image = Image.new("RGB", (120, 120), "white")
    ImageDraw.Draw(image).rectangle((45, 10, 80, 110), fill=(45, 45, 45))
    image.save(replacement)

    run_dir = phase6_gpt_artifact_gate.run_artifact_gate_experiment(
        [source_run],
        output_root=tmp_path / "outputs",
        run_id="artifact-gate",
    )

    assert (run_dir / "gpt-artifact-gate-results.json").exists()
    assert (run_dir / "visuals" / "gpt-artifact-gate-grid.png").exists()


def test_phase2_detection_cli_defaults_to_cta_mask_strategy():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args([])

    assert args.detection_strategy == "cta_mask"


def test_phase2_detection_cli_defaults_ctd_mask_edge_distance_for_real_mask_edges():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args([])

    assert args.ctd_max_edge_distance_px == 20.0


def test_phase2_cta_threshold_sweep_cli_accepts_repeatable_thresholds():
    parser = phase2_cta_threshold_sweep.build_parser()

    args = parser.parse_args(
        [
            "--phase2-run-dir",
            "outputs/runs/phase2",
            "--output-root",
            "outputs/runs",
            "--run-id",
            "sweep",
            "--threshold",
            "40",
            "--threshold",
            "80",
        ]
    )

    assert args.phase2_run_dir == "outputs/runs/phase2"
    assert args.output_root == "outputs/runs"
    assert args.run_id == "sweep"
    assert args.thresholds == [40.0, 80.0]


def test_phase2_cta_threshold_sweep_cli_leaves_default_thresholds_to_runner():
    parser = phase2_cta_threshold_sweep.build_parser()

    args = parser.parse_args(["--phase2-run-dir", "outputs/runs/phase2"])

    assert args.thresholds is None


def test_phase2_6_cta_first_cleanup_cli_defaults_to_cta_first_contract():
    parser = phase2_6_cta_first_cleanup.build_parser()

    args = parser.parse_args([])

    assert args.sample_limit == 5
    assert args.radius_x == 220
    assert args.radius_y == 180
    assert args.ctd_max_edge_distance_px == 20.0
    assert args.phase6_gpt_quality_run_dir is None


def test_phase2_6_cta_first_cleanup_cli_accepts_gpt_quality_runs():
    parser = phase2_6_cta_first_cleanup.build_parser()

    args = parser.parse_args(
        [
            "--phase6-gpt-quality-run-dir",
            "outputs/runs/quality-a",
            "--phase6-gpt-quality-run-dir",
            "outputs/runs/quality-b",
        ]
    )

    assert args.phase6_gpt_quality_run_dir == ["outputs/runs/quality-a", "outputs/runs/quality-b"]


def test_phase3_context_font_selection_cli_defaults_to_dry_run_contract():
    parser = phase3_context_font_selection.build_parser()

    args = parser.parse_args(
        [
            "--font-comparison-run-dir",
            "outputs/runs/phase3",
            "--layout-run-dir",
            "outputs/runs/phase4",
            "--cleanup-run-dir",
            "outputs/runs/phase6",
        ]
    )

    assert args.font_comparison_run_dir == "outputs/runs/phase3"
    assert args.layout_run_dir == "outputs/runs/phase4"
    assert args.cleanup_run_dir == "outputs/runs/phase6"
    assert args.sample_limit == 1
    assert args.candidate_limit == 16
    assert args.call_mimo is False


def test_phase6_nonbubble_cli_can_disable_mimo_locator():
    parser = phase6_nonbubble_cleanup.build_parser()

    args = parser.parse_args(["--skip-mimo"])

    assert args.skip_mimo is True
    assert args.fallback_edit_padding_px == 16
    assert args.fallback_mask_expand_px == 0
    assert args.fallback_gpt_mask_shape == "rect"


def test_phase6_nonbubble_cli_accepts_fallback_gpt_mask_geometry():
    parser = phase6_nonbubble_cleanup.build_parser()

    args = parser.parse_args(
        [
            "--fallback-edit-padding-px",
            "32",
            "--fallback-mask-expand-px",
            "10",
            "--fallback-gpt-mask-shape",
            "text_ink",
        ]
    )

    assert args.fallback_edit_padding_px == 32
    assert args.fallback_mask_expand_px == 10
    assert args.fallback_gpt_mask_shape == "text_ink"


def test_phase6_nonbubble_cli_builds_mimo_config_from_env(monkeypatch):
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    config = phase6_nonbubble_cleanup._mimo_config_from_env()

    assert config.base_url == "https://mimo.example/v1"
    assert config.api_key == "secret-value"
    assert config.model == "mimo-v2.5"
    assert config.thinking_type == "disabled"


def test_phase6_cleanup_quality_cli_builds_mimo_config_from_env(monkeypatch):
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    config = phase6_cleanup_quality._mimo_config_from_env()

    assert config.base_url == "https://mimo.example/v1"
    assert config.api_key == "secret-value"
    assert config.model == "mimo-v2.5"
    assert config.max_completion_tokens == 900
    assert config.thinking_type == "disabled"


def test_phase6_replacement_quality_cli_builds_mimo_config_from_env(monkeypatch):
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    config = phase6_replacement_quality._mimo_config_from_env()

    assert config.base_url == "https://mimo.example/v1"
    assert config.api_key == "secret-value"
    assert config.model == "mimo-v2.5"
    assert config.max_completion_tokens == 1200
    assert config.thinking_type == "disabled"


def test_phase6_cleanup_retry_cli_builds_mimo_config_from_env(monkeypatch):
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "secret-value")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    config = phase6_cleanup_retry._mimo_config_from_env()

    assert config.base_url == "https://mimo.example/v1"
    assert config.api_key == "secret-value"
    assert config.model == "mimo-v2.5"
    assert config.max_completion_tokens == 900
    assert config.thinking_type == "disabled"


def test_phase6_cleanup_gate_cli_defaults_to_quality_gate_contract():
    parser = phase6_cleanup_gate.build_parser()

    args = parser.parse_args(
        [
            "--cleanup-run-dir",
            "outputs/runs/phase6",
            "--cleanup-quality-run-dir",
            "outputs/runs/quality",
        ]
    )

    assert args.cleanup_run_dir == "outputs/runs/phase6"
    assert args.cleanup_quality_run_dir == "outputs/runs/quality"
    assert args.sample_limit == 20
    assert args.min_usable_score == 7


def test_phase6_cleanup_escalation_gpt_cli_defaults_to_tight_segment_contract():
    parser = phase6_cleanup_escalation_gpt_replace.build_parser()

    args = parser.parse_args(["--gate-run-dir", "outputs/runs/gate"])

    assert args.gate_run_dir == "outputs/runs/gate"
    assert args.sample_limit == 5
    assert args.context_padding == 16
    assert args.rect_mask_expand_px == 2
    assert args.max_segment_chars == 8
    assert args.max_segment_height == 640
    assert args.call_gpt_image is False
    assert args.single_segment is False


def test_phase6_cleanup_escalation_gpt_background_cli_defaults_to_background_repair_contract():
    parser = phase6_cleanup_escalation_gpt_background_repair.build_parser()

    args = parser.parse_args(["--gate-run-dir", "outputs/runs/gate"])

    assert args.gate_run_dir == "outputs/runs/gate"
    assert args.sample_limit == 5
    assert args.mask_dilation_px == 6
    assert args.call_gpt_image is False


def test_phase6_segmented_gpt_cli_defaults_to_readable_tight_context():
    parser = phase6_segmented_gpt_replace.build_parser()

    args = parser.parse_args(["--detection-run-dir", "outputs/runs/phase2"])

    assert args.context_padding == 16
    assert args.rect_mask_expand_px == 2
    assert args.max_segment_chars == 8
    assert args.max_segment_height == 640


def test_phase6_nonbubble_gpt_cli_defaults_to_readable_tight_context():
    parser = phase6_nonbubble_gpt_replace.build_parser()

    args = parser.parse_args(["--detection-run-dir", "outputs/runs/phase2"])

    assert args.context_padding == 16
    assert args.rect_mask_expand_px == 2


def test_phase7_8_quality_gate_smoke_cli_requires_existing_quality_run_contract():
    parser = phase7_8_gpt_quality_gate_smoke.build_parser()

    args = parser.parse_args(
        [
            "--detection-run-dir",
            "outputs/runs/phase2",
            "--cleanup-run-dir",
            "outputs/runs/phase6",
            "--phase6-gpt-quality-run-dir",
            "outputs/runs/phase6-quality",
            "--run-id",
            "quality-smoke",
        ]
    )

    assert args.detection_run_dir == "outputs/runs/phase2"
    assert args.cleanup_run_dir == "outputs/runs/phase6"
    assert args.phase6_gpt_quality_run_dir == "outputs/runs/phase6-quality"
    assert args.output_root == "outputs/runs"
    assert args.run_id == "quality-smoke"
    assert args.sample_limit == 1


def test_phase7_8_integrated_smoke_cli_accepts_gpt_quality_runs():
    parser = phase7_8_integrated_smoke.build_parser()

    args = parser.parse_args(
        [
            "--detection-run-dir",
            "outputs/runs/phase2",
            "--cleanup-run-dir",
            "outputs/runs/phase6-a",
            "--cleanup-run-dir",
            "outputs/runs/phase6-b",
            "--layout-run-dir",
            "outputs/runs/phase4",
            "--font-selection-run-dir",
            "outputs/runs/phase3",
            "--phase6-gpt-quality-run-dir",
            "outputs/runs/quality-a",
            "--phase6-gpt-quality-run-dir",
            "outputs/runs/quality-b",
        ]
    )

    assert args.phase6_gpt_quality_run_dir == ["outputs/runs/quality-a", "outputs/runs/quality-b"]


def test_phase6_segmented_gpt_cli_builds_api_configs_from_env(monkeypatch):
    monkeypatch.setenv("GPT_IMAGE_BASE_URL", "https://gpt.example/v1/images/edits")
    monkeypatch.setenv("GPT_IMAGE_API_KEY", "secret-value")
    monkeypatch.setenv("GPT_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "mimo-secret")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    gpt_config = phase6_segmented_gpt_replace._gpt_config_from_env()
    mimo_config = phase6_segmented_gpt_replace._mimo_config_from_env()

    assert gpt_config.base_url == "https://gpt.example/v1/images/edits"
    assert gpt_config.api_key == "secret-value"
    assert gpt_config.model == "gpt-image-2"
    assert mimo_config.base_url == "https://mimo.example/v1"
    assert mimo_config.api_key == "mimo-secret"
    assert mimo_config.model == "mimo-v2.5"
    assert mimo_config.max_completion_tokens == 1600
    assert mimo_config.thinking_type == "disabled"


def test_phase2_6_cta_first_cleanup_cli_builds_api_configs_from_env(monkeypatch):
    monkeypatch.setenv("GPT_IMAGE_BASE_URL", "https://gpt.example/v1/images")
    monkeypatch.setenv("GPT_IMAGE_API_KEY", "secret-value")
    monkeypatch.setenv("GPT_IMAGE_MODEL", "gpt-image-2")
    monkeypatch.setenv("MIMO_BASE_URL", "https://mimo.example/v1")
    monkeypatch.setenv("MIMO_API_KEY", "mimo-secret")
    monkeypatch.setenv("MIMO_VISION_MODEL", "mimo-v2.5")

    gpt_config = phase2_6_cta_first_cleanup._gpt_config_from_env()
    mimo_config = phase2_6_cta_first_cleanup._mimo_config_from_env()

    assert gpt_config.base_url == "https://gpt.example/v1/images"
    assert gpt_config.api_key == "secret-value"
    assert gpt_config.model == "gpt-image-2"
    assert mimo_config.base_url == "https://mimo.example/v1"
    assert mimo_config.api_key == "mimo-secret"
    assert mimo_config.model == "mimo-v2.5"
    assert mimo_config.max_completion_tokens == 1024
    assert mimo_config.thinking_type == "disabled"
