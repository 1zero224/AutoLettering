from __future__ import annotations


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
    function clampRgb(value) {
        value = Number(value);
        if (isNaN(value)) { return 0; }
        return Math.max(0, Math.min(255, value));
    }
    function setTextColor(textItem, rgba) {
        if (!rgba || rgba.length < 3) { return; }
        try {
            var color = new SolidColor();
            color.rgb.red = clampRgb(rgba[0]);
            color.rgb.green = clampRgb(rgba[1]);
            color.rgb.blue = clampRgb(rgba[2]);
            textItem.color = color;
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
    function textAnchorNote(layerData) {
        if (layerData.photoshop && layerData.photoshop.text_layer_name_suffix) {
            return layerData.photoshop.text_layer_name_suffix;
        }
        return '';
    }
    function moveLayerTopLeft(layer, x, y) {
        var bounds = layer.bounds;
        var currentX = bounds[0].as('px');
        var currentY = bounds[1].as('px');
        layer.translate(UnitValue(x - currentX, 'px'), UnitValue(y - currentY, 'px'));
    }
    function moveLayerTop(layer, y) {
        var bounds = layer.bounds;
        var currentY = bounds[1].as('px');
        layer.translate(UnitValue(0, 'px'), UnitValue(y - currentY, 'px'));
    }
    function applyVerticalTopAnchor(layer, layerData) {
        var anchorY = layerData.photoshop && layerData.photoshop.vertical_top_anchor_y_px;
        if (anchorY !== null && anchorY !== undefined) {
            moveLayerTop(layer, layerData.photoshop.vertical_top_anchor_y_px);
        }
    }
    function addRepairedImageLayer(doc, page) {
        if (!page.repaired_image_path) { return false; }
        var repairedFile = new File(page.repaired_image_path);
        if (!repairedFile.exists) { return false; }
        var sourceDoc = app.open(repairedFile);
        sourceDoc.selection.selectAll();
        sourceDoc.selection.copy();
        sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument = doc;
        doc.paste();
        var layer = doc.activeLayer;
        layer.name = '修复图像';
        moveLayerTopLeft(layer, 0, 0);
        return true;
    }
    function addCleanupPatchLayer(doc, layerData) {
        var patchPath = layerData.cleanup && layerData.cleanup.effective_crop_path;
        if (!patchPath) { return; }
        var patchFile = new File(patchPath);
        if (!patchFile.exists) { return; }
        var patchPosition = (layerData.cleanup && layerData.cleanup.position) || layerData.position;
        var sourceDoc = app.open(patchFile);
        sourceDoc.selection.selectAll();
        sourceDoc.selection.copy();
        sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
        app.activeDocument = doc;
        doc.paste();
        var layer = doc.activeLayer;
        layer.name = layerData.cleanup_layer_name || ('AL cleanup ' + layerData.record_id);
        moveLayerTopLeft(layer, patchPosition.x_px, patchPosition.y_px);
    }
    function addTextLayer(doc, layerData) {
        var layer = doc.artLayers.add();
        layer.kind = LayerKind.TEXT;
        layer.name = layerData.text_layer_name || layerData.layer_name;
        var item = layer.textItem;
        item.kind = TextType.PARAGRAPHTEXT;
        item.width = UnitValue(layerData.text_bbox.width, 'px');
        item.height = UnitValue(layerData.text_bbox.height, 'px');
        item.contents = textContents(layerData.text);
        item.size = UnitValue(layerData.layout.font_size || 24, 'px');
        setTextFont(item, layerData.font.photoshop_font_name || layerData.font.family_name);
        setTextDirection(item, layerData.layout.orientation);
        setTextColor(item, layerData.layout.text_color);
        setTextSpacing(item, layerData.layout);
        item.position = [UnitValue(layerData.text_position.x_px, 'px'), UnitValue(layerData.text_position.y_px, 'px')];
        layer.name = (layerData.text_layer_name || layerData.layer_name) + textAnchorNote(layerData);
        if (layerData.layout.angle_degrees) { layer.rotate(layerData.layout.angle_degrees); }
        applyVerticalTopAnchor(layer, layerData);
    }
    function nameOriginalLayer(doc) {
        try {
            doc.activeLayer = doc.backgroundLayer;
            var background = doc.activeLayer;
            background.name = '原图';
            return;
        } catch (err) {}
        try {
            var layer = doc.layers[doc.layers.length - 1];
            layer.name = '原图';
        } catch (err2) {}
    }
    var scriptFile = new File($.fileName);
    var root = scriptFile.parent.fsName;
    var manifest = parseJson(readText(root + '/photoshop-manifest.json'));
    var outputFolder = new Folder(root + '/psd');
    if (!outputFolder.exists) { outputFolder.create(); }
    for (var i = 0; i < manifest.pages.length; i++) {
        var page = manifest.pages[i];
        var doc = app.open(new File(page.image_path));
        nameOriginalLayer(doc);
        var hasRepairedImage = addRepairedImageLayer(doc, page);
        for (var j = 0; j < page.layers.length; j++) {
            if (!hasRepairedImage) {
                try { addCleanupPatchLayer(doc, page.layers[j]); } catch (err) {}
            }
        }
        for (var k = page.layers.length - 1; k >= 0; k--) {
            addTextLayer(doc, page.layers[k]);
        }
        var saveFile = new File(outputFolder.fsName + '/' + baseName(page.image_name) + '.psd');
        var options = new PhotoshopSaveOptions();
        doc.saveAs(saveFile, options, false, Extension.LOWERCASE);
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }
    alert('Autolettering Photoshop import complete: ' + manifest.summary.record_count + ' layers');
}());
"""
