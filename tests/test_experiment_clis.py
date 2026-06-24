import os

from experiments import phase2_detect_text_regions, phase6_nonbubble_cleanup


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


def test_phase2_detection_cli_defaults_ctd_mask_edge_distance_for_real_mask_edges():
    parser = phase2_detect_text_regions.build_parser()

    args = parser.parse_args([])

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
