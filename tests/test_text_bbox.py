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


def test_selected_text_bbox_does_not_bridge_light_text_to_separate_upper_art():
    detection = {
        "selected_text_box_xyxy": [286, 277, 393, 361],
        "candidate_boxes": [
            {"xyxy": [286, 277, 393, 361], "score": 0.9165, "polarity": "light_on_dark"},
            {"xyxy": [276, 219, 357, 268], "score": 0.8132, "polarity": "light_on_dark"},
            {"xyxy": [366, 344, 387, 358], "score": 0.7312, "polarity": "light_on_dark"},
            {"xyxy": [281, 224, 352, 264], "score": 0.8138, "polarity": "dark_on_light"},
        ],
    }

    assert selected_text_bbox(detection) == (286, 277, 393, 361)


def test_selected_text_bbox_excludes_panel_border_and_neighbor_text_for_gbc06_02_record_3():
    detection = {
        "selected_text_box_xyxy": [826, 490, 1192, 758],
        "search_region_xyxy": [752, 490, 1192, 850],
        "candidate_boxes": [
            {"xyxy": [826, 490, 1192, 758], "area": 14882, "score": 0.9221},
            {"xyxy": [906, 539, 940, 728], "area": 4859, "score": 0.9194},
            {"xyxy": [866, 604, 901, 668], "area": 1571, "score": 0.8749},
            {"xyxy": [1028, 520, 1061, 616], "area": 2380, "score": 0.8349},
            {"xyxy": [987, 490, 1022, 590], "area": 2609, "score": 0.8232},
            {"xyxy": [752, 784, 1192, 850], "area": 20603, "score": 0.8061},
            {"xyxy": [1065, 490, 1102, 558], "area": 2117, "score": 0.7576},
            {"xyxy": [752, 490, 824, 758], "area": 6260, "score": 0.7498},
        ],
    }

    assert selected_text_bbox(detection) == (866, 539, 940, 728)


def test_selected_text_bbox_includes_lower_score_adjacent_column_for_gbc06_02_record_2():
    detection = {
        "selected_text_box_xyxy": [892, 391, 1324, 751],
        "search_region_xyxy": [892, 391, 1332, 751],
        "candidate_boxes": [
            {"xyxy": [892, 391, 1324, 751], "area": 18203, "score": 0.9947},
            {"xyxy": [1065, 462, 1102, 558], "area": 3076, "score": 0.9112},
            {"xyxy": [1028, 520, 1061, 616], "area": 2380, "score": 0.9109},
            {"xyxy": [1027, 463, 1061, 519], "area": 1588, "score": 0.8615},
            {"xyxy": [987, 463, 1022, 590], "area": 3267, "score": 0.8465},
            {"xyxy": [906, 539, 940, 728], "area": 4859, "score": 0.7374},
        ],
    }

    assert selected_text_bbox(detection) == (906, 462, 1102, 728)


def test_selected_text_bbox_uses_selected_candidate_polarity_over_light_bubble_false_positive():
    detection = {
        "selected_text_box_xyxy": [177, 1116, 617, 1376],
        "search_region_xyxy": [177, 1116, 617, 1476],
        "candidate_boxes": [
            {"xyxy": [177, 1116, 617, 1376], "score": 0.934, "polarity": "dark_on_light"},
            {"xyxy": [350, 1243, 380, 1302], "score": 0.8939, "polarity": "dark_on_light"},
            {"xyxy": [490, 1142, 526, 1362], "score": 0.8425, "polarity": "dark_on_light"},
            {"xyxy": [531, 1146, 566, 1298], "score": 0.7776, "polarity": "dark_on_light"},
            {"xyxy": [338, 1209, 387, 1308], "score": 0.9328, "polarity": "light_on_dark"},
            {"xyxy": [177, 1397, 617, 1476], "score": 0.8146, "polarity": "light_on_dark"},
        ],
    }

    assert selected_text_bbox(detection) == (350, 1243, 380, 1302)


def test_selected_text_bbox_joins_short_vertical_glyph_fragment_above_selected_column():
    detection = {
        "selected_text_box_xyxy": [177, 1116, 617, 1376],
        "search_region_xyxy": [177, 1116, 617, 1476],
        "candidate_boxes": [
            {"xyxy": [177, 1116, 617, 1376], "score": 0.934, "polarity": "dark_on_light"},
            {"xyxy": [350, 1243, 380, 1302], "score": 0.8939, "polarity": "dark_on_light"},
            {"xyxy": [343, 1215, 381, 1243], "score": 0.7528, "polarity": "dark_on_light"},
            {"xyxy": [338, 1209, 387, 1308], "score": 0.9328, "polarity": "light_on_dark"},
            {"xyxy": [490, 1142, 526, 1362], "score": 0.8425, "polarity": "dark_on_light"},
            {"xyxy": [531, 1146, 566, 1298], "score": 0.7776, "polarity": "dark_on_light"},
        ],
    }

    assert selected_text_bbox(detection) == (343, 1215, 381, 1302)


def test_selected_text_bbox_keeps_adjacent_column_when_selected_column_is_tight():
    detection = {
        "selected_text_box_xyxy": [196, 1158, 230, 1222],
        "search_region_xyxy": [13, 1051, 453, 1411],
        "candidate_boxes": [
            {"xyxy": [196, 1158, 230, 1222], "area": 1796, "score": 0.9398, "polarity": "dark_on_light"},
            {"xyxy": [157, 1158, 191, 1347], "area": 3908, "score": 0.9172, "polarity": "dark_on_light"},
            {"xyxy": [350, 1243, 380, 1302], "area": 1184, "score": 0.7637, "polarity": "dark_on_light"},
            {"xyxy": [116, 1402, 453, 1411], "area": 3033, "score": 0.7587, "polarity": "dark_on_light"},
            {"xyxy": [343, 1215, 381, 1243], "area": 696, "score": 0.6823, "polarity": "dark_on_light"},
        ],
    }

    assert selected_text_bbox(detection) == (157, 1158, 230, 1347)
