from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


SCHEMA_VERSION = "autolettering.photoshop.v1"

JSX_SOURCE = """#target photoshop
(function () {
    function readText(path) {
        var file = new File(path);
        file.encoding = 'UTF-8';
        if (!file.open('r')) { throw new Error('Cannot open manifest: ' + path); }
        var text = file.read();
        file.close();
        return text;
    }
    function parseJson(text) { return (new Function('return ' + text))(); }
    function textContents(value) { return String(value || '').replace(/\\n/g, '\\r'); }
    function baseName(name) { return String(name).replace(/\\.[^\\.]+$/, ''); }
    function setTextFont(textItem, fontName) {
        if (!fontName) { return; }
        try { textItem.font = fontName; } catch (err) {}
    }
    function setTextDirection(textItem, orientation) {
        try {
            textItem.direction = (orientation == 'vertical') ? Direction.VERTICAL : Direction.HORIZONTAL;
        } catch (err) {}
    }
    function setTextSpacing(textItem, layout) {
        if (layout.line_spacing !== null && layout.line_spacing !== undefined) {
            textItem.leading = UnitValue((layout.font_size || 24) + layout.line_spacing, 'px');
        }
        if (layout.letter_spacing !== null && layout.letter_spacing !== undefined) {
            try { textItem.tracking = layout.letter_spacing; } catch (err) {}
        }
    }
    function moveLayerTopLeft(layer, x, y) {
        var bounds = layer.bounds;
        var currentX = bounds[0].as('px');
        var currentY = bounds[1].as('px');
        layer.translate(UnitValue(x - currentX, 'px'), UnitValue(y - currentY, 'px'));
    }
    function addCleanupPatchLayer(doc, layerData) {
        var patchPath = layerData.cleanup && layerData.cleanup.effective_crop_path;
        if (!patchPath) { return; }
        var patchFile = new File(patchPath);
        if (!patchFile.exists) { return; }
        var sourceDoc = app.open(patchFile);
        sourceDoc.selection.selectAll();
        sourceDoc.selection.copy();
        sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument = doc;
        doc.paste();
        var layer = doc.activeLayer;
        layer.name = 'AL cleanup ' + layerData.record_id;
        moveLayerTopLeft(layer, layerData.bbox.x, layerData.bbox.y);
    }
    function addTextLayer(doc, layerData) {
        var layer = doc.artLayers.add();
        layer.kind = LayerKind.TEXT;
        layer.name = layerData.layer_name;
        var item = layer.textItem;
        item.kind = TextType.PARAGRAPHTEXT;
        item.width = UnitValue(layerData.bbox.width, 'px');
        item.height = UnitValue(layerData.bbox.height, 'px');
        item.contents = textContents(layerData.text);
        item.size = UnitValue(layerData.layout.font_size || 24, 'px');
        setTextFont(item, layerData.font.photoshop_font_name || layerData.font.family_name);
        setTextDirection(item, layerData.layout.orientation);
        setTextSpacing(item, layerData.layout);
        item.position = [UnitValue(layerData.position.x_px, 'px'), UnitValue(layerData.position.y_px, 'px')];
        if (layerData.layout.angle_degrees) { layer.rotate(layerData.layout.angle_degrees); }
    }
    var scriptFile = new File($.fileName);
    var root = scriptFile.parent.fsName;
    var manifest = parseJson(readText(root + '/photoshop-manifest.json'));
    var outputFolder = new Folder(root + '/psd');
    if (!outputFolder.exists) { outputFolder.create(); }
    for (var i = 0; i < manifest.pages.length; i++) {
        var page = manifest.pages[i];
        var doc = app.open(new File(page.image_path));
        for (var j = 0; j < page.layers.length; j++) {
            try { addCleanupPatchLayer(doc, page.layers[j]); } catch (err) {}
            addTextLayer(doc, page.layers[j]);
        }
        var saveFile = new File(outputFolder.fsName + '/' + baseName(page.image_name) + '.psd');
        var options = new PhotoshopSaveOptions();
        doc.saveAs(saveFile, options, false, Extension.LOWERCASE);
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    alert('Autolettering Photoshop import complete: ' + manifest.summary.record_count + ' layers');
}());
"""


def build_photoshop_manifest(
    detection_rows: dict[str, dict],
    font_rows: dict[str, dict],
    layout_rows: list[dict],
    cleanup_rows: dict[str, dict],
    sample_limit: int,
    font_mapping: dict[str, str] | None = None,
) -> dict:
    layers = _manifest_layers(detection_rows, font_rows, layout_rows, cleanup_rows, sample_limit, font_mapping or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "pages": _group_layers_by_page(layers),
        "summary": {
            "record_count": len(layers),
            "page_count": len({layer["image_name"] for layer in layers}),
        },
    }


def write_photoshop_import_jsx(output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(JSX_SOURCE, encoding="utf-8", newline="\n")
    return output


def _manifest_layers(
    detection_rows: dict[str, dict],
    font_rows: dict[str, dict],
    layout_rows: list[dict],
    cleanup_rows: dict[str, dict],
    sample_limit: int,
    font_mapping: dict[str, str],
) -> list[dict]:
    layers: list[dict] = []
    for layout in layout_rows[:sample_limit]:
        record_id = layout["record_id"]
        detection = detection_rows.get(record_id)
        font_row = font_rows.get(record_id)
        if detection is None or font_row is None:
            continue
        layers.append(_layer_record(detection, font_row, layout, cleanup_rows.get(record_id), font_mapping))
    return layers


def _layer_record(
    detection: dict,
    font_row: dict,
    layout_row: dict,
    cleanup_row: dict | None,
    font_mapping: dict[str, str],
) -> dict:
    bbox = detection["selected_text_box_xyxy"]
    layout = layout_row["layout"]
    image_size = _image_size(detection["image_path"])
    return {
        "record_id": detection["record_id"],
        "image_name": detection["image_name"],
        "image_path": detection["image_path"],
        "layer_name": f"AL {detection['record_id']}",
        "text": layout.get("line_breaks") or detection.get("translated_text", ""),
        "translated_text": detection.get("translated_text", ""),
        "group_name": detection.get("group_name"),
        "bbox": _bbox_payload(bbox),
        "position": _position_payload(bbox, image_size),
        "font": _font_payload(font_row, font_mapping),
        "layout": _layout_payload(layout),
        "cleanup": _cleanup_payload(cleanup_row),
        "validation": layout.get("validation", {}),
    }


def _group_layers_by_page(layers: list[dict]) -> list[dict]:
    pages: dict[str, dict] = {}
    for layer in layers:
        page = pages.setdefault(
            layer["image_name"],
            {
                "image_name": layer["image_name"],
                "image_path": layer["image_path"],
                "width": layer["position"]["page_width"],
                "height": layer["position"]["page_height"],
                "layers": [],
            },
        )
        page["layers"].append(layer)
    return list(pages.values())


def _bbox_payload(bbox: list[int]) -> dict:
    x1, y1, x2, y2 = bbox
    return {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1, "xyxy": bbox}


def _position_payload(bbox: list[int], image_size: tuple[int, int]) -> dict:
    x1, y1, x2, y2 = bbox
    width, height = image_size
    return {
        "x_px": x1,
        "y_px": y1,
        "center_x_px": round((x1 + x2) / 2, 3),
        "center_y_px": round((y1 + y2) / 2, 3),
        "x_ratio": round(x1 / width, 6),
        "y_ratio": round(y1 / height, 6),
        "page_width": width,
        "page_height": height,
    }


def _font_payload(font_row: dict, font_mapping: dict[str, str]) -> dict:
    selected = font_row.get("selected_font") or {}
    postscript_name = selected.get("postscript_name")
    family_name = selected.get("family_name")
    mapped_from = _mapped_font_source(font_mapping, postscript_name, family_name)
    photoshop_font_name = font_mapping.get(mapped_from) if mapped_from else postscript_name or family_name
    return {
        "font_id": font_row.get("selected_font_id"),
        "family_name": family_name,
        "postscript_name": postscript_name,
        "photoshop_font_name": photoshop_font_name,
        "font_name_candidates": _font_name_candidates(photoshop_font_name, postscript_name, family_name),
        "mapped_from": mapped_from,
        "filename": selected.get("filename"),
        "path": selected.get("path"),
        "model_confidence": font_row.get("confidence"),
    }


def _mapped_font_source(font_mapping: dict[str, str], *names: str | None) -> str | None:
    for name in names:
        if name and name in font_mapping:
            return name
    return None


def _font_name_candidates(*names: str | None) -> list[str]:
    candidates: list[str] = []
    for name in names:
        if name and name not in candidates:
            candidates.append(name)
    return candidates


def _layout_payload(layout: dict) -> dict:
    return {
        "font_size": layout.get("font_size"),
        "orientation": layout.get("orientation"),
        "angle_degrees": layout.get("angle_degrees", 0.0),
        "line_breaks": layout.get("line_breaks"),
        "line_spacing": layout.get("line_spacing"),
        "letter_spacing": layout.get("letter_spacing"),
        "target_width": layout.get("target_width"),
        "target_height": layout.get("target_height"),
        "overflow_ratio": layout.get("overflow_ratio"),
    }


def _cleanup_payload(cleanup_row: dict | None) -> dict:
    if cleanup_row is None:
        return {
            "status": "missing",
            "method": None,
            "cleaned_crop_path": None,
            "before_after_path": None,
            "replacement_method": None,
            "replacement_crop_path": None,
            "effective_method": None,
            "effective_crop_path": None,
        }
    cleanup = cleanup_row.get("cleanup", {})
    replacement_crop_path = cleanup.get("replacement_crop_path")
    cleaned_crop_path = cleanup.get("cleaned_crop_path")
    replacement_method = cleanup.get("replacement_method")
    method = cleanup.get("method")
    return {
        "status": cleanup_row.get("status"),
        "method": method,
        "cleaned_crop_path": cleaned_crop_path,
        "before_after_path": cleanup.get("before_after_path"),
        "replacement_method": replacement_method,
        "replacement_crop_path": replacement_crop_path,
        "effective_method": replacement_method or method,
        "effective_crop_path": replacement_crop_path or cleaned_crop_path,
    }


def _image_size(image_path: str | Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def write_json(path: str | Path, payload: dict) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output
