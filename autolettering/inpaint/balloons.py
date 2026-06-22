from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types

import numpy as np
from PIL import Image

_DLL_HANDLES: list[object] = []
_AOT_MODEL = None
_AOT_MODULE = None
_LAMA_LARGE_MODEL = None
_LAMA_LARGE_MODULE = None
_PATCHMATCH_MODULE = None


def aot_inpaint(crop: Image.Image, text_mask: Image.Image) -> Image.Image:
    model, _ = _load_aot()
    cv2 = _require_cv2()
    torch = _require_torch()
    original = np.array(crop.convert("RGB"), dtype=np.uint8)
    mask = np.array(text_mask.convert("L"), dtype=np.uint8)
    img_t, mask_t, image_shape, mask_original, pad_bottom, pad_right = _aot_tensors(original, mask, cv2, torch)
    with torch.no_grad():
        output_t = model(img_t, mask_t)
    output = _aot_output(output_t, image_shape, pad_bottom, pad_right, cv2)
    if output.shape[:2] != original.shape[:2]:
        output = cv2.resize(output, (original.shape[1], original.shape[0]), interpolation=cv2.INTER_LINEAR)
        mask_original = (mask >= 127)[:, :, None].astype(np.uint8)
    keep = 1 - mask_original
    result = (output * mask_original + original * keep).astype(np.uint8)
    return Image.fromarray(_restore_grayscale_if_mono(original, result), mode="RGB")


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


def _load_aot():
    global _AOT_MODEL, _AOT_MODULE
    if _AOT_MODEL is not None and _AOT_MODULE is not None:
        return _AOT_MODEL, _AOT_MODULE
    bt_root = _balloons_root()
    default_model = bt_root / "data" / "models" / "aot_inpainter.ckpt"
    model_path = Path(os.environ.get("BT_AOT_CKPT", default_model))
    if not model_path.exists():
        raise RuntimeError(f"bt_aot_missing_checkpoint:{model_path}")
    if str(bt_root) not in sys.path:
        sys.path.insert(0, str(bt_root))
    _AOT_MODULE = _load_module_with_cwd(
        "_autolettering_bt_aot",
        bt_root,
        "ballontranslator/modules/inpaint/aot.py",
    )
    device = os.environ.get("BT_AOT_DEVICE", "cpu")
    _AOT_MODEL = _AOT_MODULE.load_aot_model(str(model_path), device)
    return _AOT_MODEL, _AOT_MODULE


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


def _aot_tensors(original: np.ndarray, mask_u8: np.ndarray, cv2, torch):
    max_size = int(os.environ.get("BT_AOT_INPAINT_SIZE", "2048"))
    image = original
    mask = mask_u8
    if max(original.shape[:2]) > max_size:
        ratio = max_size / max(original.shape[:2])
        target_w = max(1, int(round(original.shape[1] * ratio)))
        target_h = max(1, int(round(original.shape[0] * ratio)))
        image = cv2.resize(original, (target_w, target_h), interpolation=cv2.INTER_AREA)
        mask = cv2.resize(mask_u8, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

    image_shape = image.shape
    mask_original = (mask >= 127)[:, :, None].astype(np.uint8)
    pad_bottom = 128 - image.shape[0] if image.shape[0] < 128 else 0
    pad_right = 128 - image.shape[1] if image.shape[1] < 128 else 0
    image = cv2.copyMakeBorder(image, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT)
    mask = cv2.copyMakeBorder(mask, 0, pad_bottom, 0, pad_right, cv2.BORDER_REFLECT)

    img_t = torch.from_numpy(image).permute(2, 0, 1).unsqueeze(0).float() / 127.5 - 1.0
    mask_t = torch.from_numpy(mask).unsqueeze(0).unsqueeze(0).float() / 255.0
    mask_t = (mask_t >= 0.5).float()
    device = os.environ.get("BT_AOT_DEVICE", "cpu")
    if device != "cpu":
        img_t = img_t.to(device)
        mask_t = mask_t.to(device)
    img_t *= 1 - mask_t
    return img_t, mask_t, image_shape, mask_original, pad_bottom, pad_right


def _aot_output(output_t, image_shape, pad_bottom: int, pad_right: int, cv2) -> np.ndarray:
    output = ((output_t.cpu().squeeze(0).permute(1, 2, 0).numpy() + 1.0) * 127.5)
    output = np.clip(np.round(output), 0, 255).astype(np.uint8)
    if pad_bottom:
        output = output[:-pad_bottom]
    if pad_right:
        output = output[:, :-pad_right]
    if output.shape[:2] != image_shape[:2]:
        output = cv2.resize(output, (image_shape[1], image_shape[0]), interpolation=cv2.INTER_LINEAR)
    return output


def _restore_grayscale_if_mono(original: np.ndarray, result: np.ndarray) -> np.ndarray:
    channel_spread = np.abs(original.astype(np.int16) - original.mean(axis=2, keepdims=True)).mean()
    if channel_spread > 3.0:
        return result
    luminance = np.round(result @ np.array([0.299, 0.587, 0.114])).astype(np.uint8)
    return np.repeat(luminance[:, :, None], 3, axis=2)


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
