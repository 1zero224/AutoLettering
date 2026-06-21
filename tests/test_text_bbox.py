from autolettering.text_bbox import selected_text_bbox


def test_selected_text_bbox_unions_small_text_candidates_inside_large_detection():
    detection = {
        "selected_text_box_xyxy": [0, 0, 200, 200],
        "candidate_boxes": [
            {"xyxy": [0, 0, 200, 200], "area": 40000},
            {"xyxy": [60, 40, 90, 160], "area": 3600},
            {"xyxy": [105, 42, 135, 155], "area": 3390},
        ],
    }

    assert selected_text_bbox(detection) == (60, 40, 135, 160)


def test_selected_text_bbox_excludes_low_score_remote_noise():
    detection = {
        "selected_text_box_xyxy": [452, 785, 892, 1145],
        "candidate_boxes": [
            {"xyxy": [452, 785, 892, 1145], "score": 1.0},
            {"xyxy": [620, 944, 654, 1040], "score": 0.9417},
            {"xyxy": [581, 943, 614, 1070], "score": 0.8875},
            {"xyxy": [541, 944, 575, 1040], "score": 0.8454},
            {"xyxy": [461, 1037, 493, 1133], "score": 0.6979},
            {"xyxy": [875, 1010, 892, 1052], "score": 0.519},
        ],
    }

    assert selected_text_bbox(detection) == (541, 943, 654, 1070)


def test_selected_text_bbox_keeps_high_score_vertical_cluster_for_adjacent_record():
    detection = {
        "selected_text_box_xyxy": [280, 959, 720, 1310],
        "candidate_boxes": [
            {"xyxy": [280, 959, 720, 1310], "score": 0.9941},
            {"xyxy": [460, 1139, 494, 1234], "score": 0.9304},
            {"xyxy": [461, 1037, 493, 1133], "score": 0.9226},
            {"xyxy": [420, 1039, 455, 1132], "score": 0.8915},
            {"xyxy": [418, 1156, 455, 1281], "score": 0.8658},
            {"xyxy": [380, 1036, 415, 1226], "score": 0.8644},
            {"xyxy": [340, 1070, 377, 1184], "score": 0.8127},
            {"xyxy": [541, 959, 574, 1040], "score": 0.8009},
            {"xyxy": [620, 959, 654, 1040], "score": 0.7421},
        ],
    }

    assert selected_text_bbox(detection) == (340, 1036, 494, 1281)
