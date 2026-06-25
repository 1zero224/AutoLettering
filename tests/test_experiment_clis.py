from experiments import (
    phase2_detect_text_regions,
    phase2_6_cta_first_cleanup,
    phase6_cleanup_quality,
    phase6_cleanup_gate,
    phase6_cleanup_escalation_gpt_replace,
    phase6_replacement_quality,
    phase6_cleanup_retry,
    phase6_nonbubble_cleanup,
    phase6_nonbubble_gpt_replace,
    phase6_segmented_gpt_replace,
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


def test_phase2_detection_cli_defaults_to_cta_mask_strategy():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args([])

    assert args.detection_strategy == "cta_mask"


def test_phase2_detection_cli_defaults_ctd_mask_edge_distance_for_real_mask_edges():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args([])

    assert args.ctd_max_edge_distance_px == 20.0


def test_phase2_6_cta_first_cleanup_cli_defaults_to_cta_first_contract():
    parser = phase2_6_cta_first_cleanup.build_parser()

    args = parser.parse_args([])

    assert args.sample_limit == 5
    assert args.radius_x == 220
    assert args.radius_y == 180
    assert args.ctd_max_edge_distance_px == 20.0


def test_phase6_nonbubble_cli_can_disable_mimo_locator():
    parser = phase6_nonbubble_cleanup.build_parser()

    args = parser.parse_args(["--skip-mimo"])

    assert args.skip_mimo is True


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
