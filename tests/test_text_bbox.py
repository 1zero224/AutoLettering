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


def test_selected_text_bbox_preserves_unscored_wide_multicolumn_candidates():
    detection = {
        "selected_text_box_xyxy": [0, 0, 280, 200],
        "candidate_boxes": [
            {"xyxy": [50, 40, 75, 170], "area": 3250},
            {"xyxy": [105, 40, 130, 170], "area": 3250},
            {"xyxy": [225, 40, 250, 170], "area": 3250},
        ],
    }

    assert selected_text_bbox(detection) == (50, 40, 250, 170)


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


def test_selected_text_bbox_expands_from_selected_column_to_adjacent_text_columns():
    detection = {
        "selected_text_box_xyxy": [1252, 1466, 1285, 1560],
        "candidate_boxes": [
            {"xyxy": [1252, 1466, 1285, 1560], "area": 2404, "score": 0.9569},
            {"xyxy": [1077, 1340, 1324, 1700], "area": 43429, "score": 0.8584},
            {"xyxy": [1250, 1377, 1288, 1465], "area": 2759, "score": 0.8491},
            {"xyxy": [1211, 1378, 1249, 1504], "area": 3856, "score": 0.848},
            {"xyxy": [1172, 1378, 1209, 1529], "area": 4241, "score": 0.8158},
        ],
    }

    assert selected_text_bbox(detection) == (1172, 1377, 1288, 1560)


def test_selected_text_bbox_does_not_bridge_wide_gap_into_neighbor_bubble():
    detection = {
        "selected_text_box_xyxy": [523, 1336, 881, 1679],
        "candidate_boxes": [
            {"xyxy": [523, 1336, 881, 1679], "score": 0.9448},
            {"xyxy": [577, 1368, 612, 1555], "score": 0.8993},
            {"xyxy": [615, 1367, 653, 1462], "score": 0.883},
            {"xyxy": [722, 1401, 757, 1493], "score": 0.8758},
            {"xyxy": [760, 1367, 797, 1463], "score": 0.8095},
            {"xyxy": [537, 1622, 624, 1679], "score": 0.7737},
            {"xyxy": [441, 1336, 520, 1679], "score": 0.7616},
        ],
    }

    assert selected_text_bbox(detection) == (577, 1367, 653, 1555)
