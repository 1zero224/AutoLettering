from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image

_DLL_HANDLES: list[object] = []
_LAMA_LARGE_MODEL = None
_LAMA_LARGE_MODULE = None
_PATCHMATCH_MODULE = None


def patchmatch_inpaint(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    patch_match = _load_patchmatch()
    image_array = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask_array = np.array(text_mask.convert("L"), dtype=np.uint8)
    result = patch_match.inpaint(image_array, mask_array, patch_size=3)
    return Image.fromarray(result, mode="RGB")


def lama_large_inpaint(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    model, _ = _load_lama_large()
    cv2 = _require_cv2()
    torch = _require_torch()
    original = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask = np.array(text_mask.convert("L"), dtype=np.uint8) >= 127
    img_t, mask_t, padded_shape = _lama_large_tensors(original, mask, cv2, torch)
    with torch.no_grad():
        output_t = model(img_t, mask_t)
    output = _lama_large_output(output_t, original.shape, padded_shape, cv2)
    keep = (~mask)[:, :, None].astype(np.uint8)
    fill = mask[:, :, None].astype(np.uint8)
    return Image.fromarray((output * fill + original * keep).astype(np.uint8), mode="RGB")


def _load_patchmatch():
    global _PATCHMATCH_MODULE
    if _PATCHMATCH_MODULE is not None:
        return _PATCHMATCH_MODULE
    bt_root = _balloons_root()
    dll_dir = bt_root / "data" / "libs"
    if not (dll_dir / "patchmatch_inpaint.dll").exists():
        raise RuntimeError(f"bt_patchmatch_missing_dll:{dll_dir / 'patchmatch_inpaint.dll'}")
    if hasattr(os, "add_dll_directory"):
        _DLL_HANDLES.append(os.add_dll_directory(str(dll_dir)))
    _PATCHMATCH_MODULE = _load_module_with_cwd(
        "_autolettering_bt_patchmatch",
        bt_root,
        "ballontranslator/modules/inpaint/patch_match.py",
    )
    return _PATCHMATCH_MODULE


def _load_lama_large():
    global _LAMA_LARGE_MODEL, _LAMA_LARGE_MODULE
    if _LAMA_LARGE_MODEL is not None and _LAMA_LARGE_MODULE is not None:
        return _LAMA_LARGE_MODEL, _LAMA_LARGE_MODULE
    bt_root = _balloons_root()
    default_model = bt_root / "data" / "models" / "lama_large_512px.ckpt"
    model_path = Path(os.environ.get("BT_LAMA_LARGE_CKPT", default_model))
    if not model_path.exists():
        raise RuntimeError(f"bt_lama_large_missing_checkpoint:{model_path}")
    _LAMA_LARGE_MODULE = _load_balloons_inpaint_module(bt_root, "lama")
    cwd = Path.cwd()
    os.chdir(bt_root)
    try:
        _LAMA_LARGE_MODEL = _LAMA_LARGE_MODULE.load_lama_mpe(str(model_path), "cpu", use_mpe=False, large_arch=True)
    finally:
        os.chdir(cwd)
    return _LAMA_LARGE_MODEL, _LAMA_LARGE_MODULE


def _lama_large_tensors(original: np.ndarray, mask: np.ndarray, cv2, torch):
    longer = max(original.shape[:2])
    pad_bottom = longer - original.shape[0]
    pad_right = longer - original.shape[1]
    image = cv2.copyMakeBorder(original, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT)
    mask_u8 = cv2.copyMakeBorder(mask.astype(np.uint8) * 255, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT)
    target = int(np.ceil(longer / 64) * 64)
    image = cv2.resize(image, (target, target), interpolation=cv2.INTER_LINEAR)
    mask_u8 = cv2.resize(mask_u8, (target, target), interpolation=cv2.INTER_NEAREST)
    img_t = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    mask_t = torch.from_numpy(mask_u8).unsqueeze(0).unsqueeze(0).float() / 255.0
    mask_t = (mask_t >= 0.5).float()
    return img_t * (1 - mask_t), mask_t, (original.shape, (pad_bottom, pad_right))


def _lama_large_output(output_t, original_shape, padded_shape, cv2) -> np.ndarray:
    output = (output_t.cpu().squeeze(0).permute(1, 2, 0).numpy() * 255)
    output = np.clip(np.round(output), 0, 255).astype(np.uint8)
    _, (pad_bottom, pad_right) = padded_shape
    padded_h = original_shape[0] + pad_bottom
    padded_w = original_shape[1] + pad_right
    output = cv2.resize(output, (padded_w, padded_h), interpolation=cv2.INTER_LINEAR)
    if pad_bottom:
        output = output[:-pad_bottom]
    if pad_right:
        output = output[:, :-pad_right]
    return output


def _load_balloons_inpaint_module(bt_root: Path, module_name: str):
    package_name = "_autolettering_balloons_inpaint"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(bt_root / "ballontranslator" / "modules" / "inpaint")]
        sys.modules[package_name] = package
    full_name = f"{package_name}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    module_path = bt_root / "ballontranslator" / "modules" / "inpaint" / f"{module_name}.py"
    return _load_module(full_name, module_path)


def _load_module_with_cwd(name: str, root: Path, relative_path: str):
    cwd = Path.cwd()
    os.chdir(root)
    try:
        return _load_module(name, root / relative_path)
    finally:
        os.chdir(cwd)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot_load_module:{path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _balloons_root() -> Path:
    configured = os.environ.get("BALLONSTRANSLATOR_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "BallonsTranslator"


def _require_cv2():
    try:
        import cv2
    except ModuleNotFoundError as exc:
        raise RuntimeError("opencv_inpaint_requires_cv2") from exc
    return cv2


def _require_torch():
    try:
        import torch
    except ModuleNotFoundError as exc:
        raise RuntimeError("bt_lama_large_requires_torch") from exc
    return torch
