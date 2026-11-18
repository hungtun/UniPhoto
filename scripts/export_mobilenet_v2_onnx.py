#!/usr/bin/env python3
"""Export torchvision MobileNetV2 (float32, unquantized, exact weights) to ONNX.

Produces:
  - data/models/mobilenet_v2.onnx
  - build/bundled-models/mobilenet_v2.onnx (removing legacy mobilenet_v2.pth)

Works 100% offline even when the `onnx` Python package is not installed by
folding Conv2d + BatchNorm2d analytically in float64 -> float32 and encoding a
standard opset-13 ONNX ModelProto directly using protobuf wire format.
Validates equivalence against PyTorch via OpenCV `cv2.dnn.readNetFromONNX` for
both `batch=1` and `batch=16` (`cosine_similarity > 0.999999`, `max_abs_diff < 1e-4`).
"""

from __future__ import annotations

import shutil
import ssl
import struct
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

ssl._create_default_https_context = ssl._create_unverified_context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ONNX = PROJECT_ROOT / "data" / "models" / "mobilenet_v2.onnx"
DEFAULT_BUNDLED_ONNX = PROJECT_ROOT / "build" / "bundled-models" / "mobilenet_v2.onnx"
LEGACY_BUNDLED_PTH = PROJECT_ROOT / "build" / "bundled-models" / "mobilenet_v2.pth"


# ---------------------------------------------------------------------------
# Minimal Pure-Python Protobuf Wire Encoder for ONNX ModelProto (Opset 13)
# ---------------------------------------------------------------------------

def _encode_varint(value: int) -> bytes:
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while True:
        bits = value & 0x7F
        value >>= 7
        if value:
            out.append(bits | 0x80)
        else:
            out.append(bits)
            break
    return bytes(out)


def _encode_tag(field_number: int, wire_type: int) -> bytes:
    return _encode_varint((field_number << 3) | wire_type)


def _field_varint(field_number: int, value: int) -> bytes:
    return _encode_tag(field_number, 0) + _encode_varint(value)


def _field_bytes(field_number: int, payload: bytes) -> bytes:
    return _encode_tag(field_number, 2) + _encode_varint(len(payload)) + payload


def _field_str(field_number: int, text: str) -> bytes:
    return _field_bytes(field_number, text.encode("utf-8"))


def _field_f32(field_number: int, val: float) -> bytes:
    return _encode_tag(field_number, 5) + struct.pack("<f", val)


def _onnx_attr_int(name: str, val: int) -> bytes:
    # AttributeProto: name=1, i=3, type=20 (INT=2)
    return (
        _field_str(1, name)
        + _field_varint(3, val)
        + _field_varint(20, 2)
    )


def _onnx_attr_ints(name: str, vals: Sequence[int]) -> bytes:
    # AttributeProto: name=1, ints=8 (repeated int64), type=20 (INTS=7)
    parts = [_field_str(1, name)]
    for v in vals:
        parts.append(_field_varint(8, int(v)))
    parts.append(_field_varint(20, 7))
    return b"".join(parts)


def _onnx_tensor_f32(name: str, arr: np.ndarray) -> bytes:
    # TensorProto: dims=1, data_type=2 (FLOAT=1), name=8, raw_data=9
    arr_le = np.ascontiguousarray(arr, dtype="<f4")
    parts = [_field_varint(1, int(d)) for d in arr_le.shape]
    parts.append(_field_varint(2, 1))
    parts.append(_field_str(8, name))
    parts.append(_field_bytes(9, arr_le.tobytes()))
    return b"".join(parts)


def _onnx_tensor_i64(name: str, arr: np.ndarray) -> bytes:
    # TensorProto: dims=1, data_type=2 (INT64=7), name=8, raw_data=9
    arr_le = np.ascontiguousarray(arr, dtype="<i8")
    parts = [_field_varint(1, int(d)) for d in arr_le.shape]
    parts.append(_field_varint(2, 7))
    parts.append(_field_str(8, name))
    parts.append(_field_bytes(9, arr_le.tobytes()))
    return b"".join(parts)


def _onnx_value_info_f32(name: str, dims: Sequence[int | str]) -> bytes:
    # Dimension: dim_value=1 or dim_param=2
    dim_msgs = []
    for d in dims:
        if isinstance(d, str):
            dim_msgs.append(_field_bytes(1, _field_str(2, d)))
        else:
            dim_msgs.append(_field_bytes(1, _field_varint(1, int(d))))
    shape_proto = b"".join(dim_msgs)
    # TypeProto.Tensor: elem_type=1 (FLOAT=1), shape=2
    tensor_type = _field_varint(1, 1) + _field_bytes(2, shape_proto)
    # TypeProto: tensor_type=1
    type_proto = _field_bytes(1, tensor_type)
    # ValueInfoProto: name=1, type=2
    return _field_str(1, name) + _field_bytes(2, type_proto)


def _onnx_node(
    op_type: str,
    inputs: Sequence[str],
    outputs: Sequence[str],
    name: str,
    attrs: Sequence[bytes] = (),
) -> bytes:
    # NodeProto: input=1, output=2, name=3, op_type=4, attribute=5
    parts: List[bytes] = []
    for inp in inputs:
        parts.append(_field_str(1, inp))
    for out in outputs:
        parts.append(_field_str(2, out))
    parts.append(_field_str(3, name))
    parts.append(_field_str(4, op_type))
    for attr in attrs:
        parts.append(_field_bytes(5, attr))
    return b"".join(parts)


def _fold_conv_bn(conv: nn.Conv2d, bn: nn.BatchNorm2d) -> Tuple[np.ndarray, np.ndarray]:
    """Fold Conv2d + BatchNorm2d weights & biases in float64 precision, returning float32."""
    w = conv.weight.detach().cpu().numpy().astype(np.float64)
    if conv.bias is not None:
        b = conv.bias.detach().cpu().numpy().astype(np.float64)
    else:
        b = np.zeros(w.shape[0], dtype=np.float64)

    gamma = bn.weight.detach().cpu().numpy().astype(np.float64)
    beta = bn.bias.detach().cpu().numpy().astype(np.float64)
    mean = bn.running_mean.detach().cpu().numpy().astype(np.float64)
    var = bn.running_var.detach().cpu().numpy().astype(np.float64)
    eps = float(bn.eps)

    scale = gamma / np.sqrt(var + eps)
    w_folded = (w * scale[:, None, None, None]).astype(np.float32)
    b_folded = ((b - mean) * scale + beta).astype(np.float32)
    return w_folded, b_folded


def _build_mobilenet_v2_onnx_bytes_direct(model: nn.Module) -> bytes:
    """Serialize torchvision MobileNetV2 (classifier=Identity) to ONNX ModelProto bytes."""
    nodes: List[bytes] = []
    initializers: List[bytes] = []

    # Shared Clip bounds for ReLU6 (opset 13 Clip inputs: [x, min, max])
    initializers.append(_onnx_tensor_f32("clip_min_0", np.array(0.0, dtype=np.float32)))
    initializers.append(_onnx_tensor_f32("clip_max_6", np.array(6.0, dtype=np.float32)))

    conv_idx = 0
    clip_idx = 0
    add_idx = 0

    def emit_conv_bn_act(
        inp_name: str,
        conv: nn.Conv2d,
        bn: nn.BatchNorm2d,
        has_relu6: bool,
        prefix: str,
    ) -> str:
        nonlocal conv_idx, clip_idx
        w_f32, b_f32 = _fold_conv_bn(conv, bn)
        w_name = f"{prefix}_conv{conv_idx}_w"
        b_name = f"{prefix}_conv{conv_idx}_b"
        conv_out = f"{prefix}_conv{conv_idx}_out"
        initializers.append(_onnx_tensor_f32(w_name, w_f32))
        initializers.append(_onnx_tensor_f32(b_name, b_f32))

        kh, kw = conv.kernel_size
        sh, sw = conv.stride
        ph, pw = conv.padding
        dh, dw = conv.dilation
        attrs = [
            _onnx_attr_ints("dilations", [dh, dw]),
            _onnx_attr_int("group", int(conv.groups)),
            _onnx_attr_ints("kernel_shape", [kh, kw]),
            _onnx_attr_ints("pads", [ph, pw, ph, pw]),
            _onnx_attr_ints("strides", [sh, sw]),
        ]
        nodes.append(
            _onnx_node(
                op_type="Conv",
                inputs=[inp_name, w_name, b_name],
                outputs=[conv_out],
                name=f"Conv_{conv_idx}",
                attrs=attrs,
            )
        )
        conv_idx += 1

        if has_relu6:
            act_out = f"{prefix}_relu6_{clip_idx}_out"
            nodes.append(
                _onnx_node(
                    op_type="Clip",
                    inputs=[conv_out, "clip_min_0", "clip_max_6"],
                    outputs=[act_out],
                    name=f"Clip_{clip_idx}",
                )
            )
            clip_idx += 1
            return act_out
        return conv_out

    cur = "input"
    features: Iterable[nn.Module] = model.features  # type: ignore[assignment]
    for blk_idx, blk in enumerate(features):
        blk_prefix = f"feat{blk_idx}"
        if hasattr(blk, "conv") and hasattr(blk, "use_res_connect"):
            # InvertedResidual block
            res_input = cur
            sub_layers = list(blk.conv.children())
            idx = 0
            while idx < len(sub_layers):
                sub = sub_layers[idx]
                if isinstance(sub, nn.Sequential):
                    sub_children = list(sub.children())
                    c_mod = sub_children[0]
                    bn_mod = sub_children[1]
                    has_act = len(sub_children) >= 3 and isinstance(
                        sub_children[2], nn.ReLU6
                    )
                    assert isinstance(c_mod, nn.Conv2d) and isinstance(
                        bn_mod, nn.BatchNorm2d
                    )
                    cur = emit_conv_bn_act(
                        cur, c_mod, bn_mod, has_act, f"{blk_prefix}_s{idx}"
                    )
                    idx += 1
                elif (
                    isinstance(sub, nn.Conv2d)
                    and idx + 1 < len(sub_layers)
                    and isinstance(sub_layers[idx + 1], nn.BatchNorm2d)
                ):
                    bn_mod = sub_layers[idx + 1]
                    has_act = (
                        idx + 2 < len(sub_layers)
                        and isinstance(sub_layers[idx + 2], nn.ReLU6)
                    )
                    cur = emit_conv_bn_act(
                        cur, sub, bn_mod, has_act, f"{blk_prefix}_proj"
                    )
                    idx += 3 if has_act else 2
                else:
                    raise RuntimeError(
                        f"Unexpected layer in InvertedResidual {blk_idx}: {type(sub)}"
                    )

            if bool(blk.use_res_connect):
                add_out = f"{blk_prefix}_add_{add_idx}_out"
                nodes.append(
                    _onnx_node(
                        op_type="Add",
                        inputs=[res_input, cur],
                        outputs=[add_out],
                        name=f"Add_{add_idx}",
                    )
                )
                add_idx += 1
                cur = add_out
        else:
            # Conv2dNormActivation sequential block
            sub_children = list(blk.children())
            c_mod = sub_children[0]
            bn_mod = sub_children[1]
            has_act = len(sub_children) >= 3 and isinstance(sub_children[2], nn.ReLU6)
            assert isinstance(c_mod, nn.Conv2d) and isinstance(bn_mod, nn.BatchNorm2d)
            cur = emit_conv_bn_act(cur, c_mod, bn_mod, has_act, blk_prefix)

    # GlobalAveragePool: [batch, 1280, 7, 7] -> [batch, 1280, 1, 1]
    gap_out = "global_avg_pool_out"
    nodes.append(
        _onnx_node(
            op_type="GlobalAveragePool",
            inputs=[cur],
            outputs=[gap_out],
            name="GlobalAveragePool_0",
        )
    )

    # Flatten(axis=1): [batch, 1280, 1, 1] -> [batch, 1280] for any batch >= 1
    nodes.append(
        _onnx_node(
            op_type="Flatten",
            inputs=[gap_out],
            outputs=["output"],
            name="Flatten_0",
            attrs=[_onnx_attr_int("axis", 1)],
        )
    )

    input_vi = _onnx_value_info_f32("input", ["batch", 3, 224, 224])
    output_vi = _onnx_value_info_f32("output", ["batch", 1280])

    # GraphProto: node=1, name=2, initializer=5, input=11, output=12
    graph_parts: List[bytes] = [_field_bytes(1, n) for n in nodes]
    graph_parts.append(_field_str(2, "mobilenet_v2_feature_extractor"))
    for init in initializers:
        graph_parts.append(_field_bytes(5, init))
    graph_parts.append(_field_bytes(11, input_vi))
    graph_parts.append(_field_bytes(12, output_vi))
    graph_proto = b"".join(graph_parts)

    # OperatorSetIdProto: domain="" (1), version=13 (2)
    opset_proto = _field_str(1, "") + _field_varint(2, 13)

    # ModelProto: ir_version=7 (1), producer_name=2, producer_version=3, graph=7, opset_import=8
    model_proto = (
        _field_varint(1, 7)
        + _field_str(2, "uniphoto-onnx-exporter")
        + _field_str(3, "1.0")
        + _field_bytes(7, graph_proto)
        + _field_bytes(8, opset_proto)
    )
    return model_proto


def load_pretrained_mobilenet_v2() -> Tuple[nn.Module, str]:
    """Load exact torchvision MobileNetV2 ImageNet weights offline-first."""
    candidates: List[Path] = []
    torch_hub_dir = (
        Path(
            torch.hub.get_dir()
            if hasattr(torch.hub, "get_dir")
            else str(Path.home() / ".cache" / "torch" / "hub")
        )
        / "checkpoints"
    )
    if torch_hub_dir.is_dir():
        candidates.extend(sorted(torch_hub_dir.glob("mobilenet_v2*.pth")))
    default_cache = Path.home() / ".cache" / "torch" / "hub" / "checkpoints"
    if default_cache.is_dir() and default_cache != torch_hub_dir:
        candidates.extend(sorted(default_cache.glob("mobilenet_v2*.pth")))
    candidates.extend(
        [
            PROJECT_ROOT / "data" / "models" / "mobilenet_v2.pth",
            LEGACY_BUNDLED_PTH,
        ]
    )

    for cand in candidates:
        if cand.is_file() and cand.stat().st_size > 1_000_000:
            state_dict = torch.load(str(cand), map_location="cpu", weights_only=True)
            model = mobilenet_v2(weights=None)
            if "classifier.1.weight" not in state_dict:
                model.classifier = nn.Identity()
                model.load_state_dict(state_dict)
            else:
                model.load_state_dict(state_dict)
                model.classifier = nn.Identity()
            model.eval()
            return model, str(cand)

    model = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
    model.classifier = nn.Identity()
    model.eval()
    return model, "MobileNet_V2_Weights.DEFAULT"


def export_mobilenet_v2_to_onnx(dest_path: Path) -> Tuple[nn.Module, str]:
    """Export MobileNetV2 to `dest_path`, using torch.onnx.export or pure-Python fallback."""
    model, weight_source = load_pretrained_mobilenet_v2()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(".onnx.tmp")

    exported_mode = ""
    try:
        dummy = torch.zeros(1, 3, 224, 224, dtype=torch.float32)
        torch.onnx.export(
            model,
            dummy,
            str(tmp_path),
            export_params=True,
            opset_version=13,
            do_constant_folding=True,
            input_names=["input"],
            output_names=["output"],
            dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}},
            dynamo=False,
        )
        exported_mode = "torch.onnx.export(dynamo=False)"
    except Exception:
        onnx_bytes = _build_mobilenet_v2_onnx_bytes_direct(model)
        tmp_path.write_bytes(onnx_bytes)
        exported_mode = "direct-protobuf-folded-conv-bn(opset=13)"

    tmp_path.replace(dest_path)
    return model, f"{exported_mode} from {weight_source}"


def validate_onnx_equivalence(model: nn.Module, onnx_path: Path) -> None:
    """Validate cv2.dnn ONNX output against PyTorch for both batch=1 and batch=16."""
    net = cv2.dnn.readNetFromONNX(str(onnx_path))

    rng = np.random.RandomState(20261118)
    # Mix random normalized ImageNet inputs and structured synthetic image patterns
    batch16 = rng.randn(16, 3, 224, 224).astype(np.float32)
    yy, xx = np.mgrid[0:224, 0:224].astype(np.float32) / 224.0
    batch16[0, 0] = (xx - 0.485) / 0.229
    batch16[0, 1] = (yy - 0.456) / 0.224
    batch16[0, 2] = (0.5 * (xx + yy) - 0.406) / 0.225

    with torch.no_grad():
        pt_out_16 = model(torch.from_numpy(batch16)).cpu().numpy().astype(np.float32)
        pt_out_1 = model(torch.from_numpy(batch16[:1])).cpu().numpy().astype(np.float32)

    # 1) Test batch=1 in cv2.dnn
    single_outputs: List[np.ndarray] = []
    for i in range(16):
        net.setInput(batch16[i : i + 1])
        out_i = net.forward()
        assert out_i.shape == (1, 1280), f"Unexpected batch=1 shape: {out_i.shape}"
        assert out_i.dtype == np.float32, f"Unexpected dtype: {out_i.dtype}"
        single_outputs.append(out_i.copy())
    cv_single_stacked = np.vstack(single_outputs)

    # 2) Test batch=16 in cv2.dnn (and re-run batch=1 afterwards to test dynamic re-shape!)
    net.setInput(batch16)
    cv_batch_16 = net.forward().copy()
    assert cv_batch_16.shape == (16, 1280), f"Unexpected batch=16 shape: {cv_batch_16.shape}"

    net.setInput(batch16[:1])
    cv_after_batch_1 = net.forward().copy()
    assert cv_after_batch_1.shape == (1, 1280), (
        f"Unexpected batch=1 shape after batch=16: {cv_after_batch_1.shape}"
    )

    for label, got, ref in (
        ("batch=1 (16 images)", cv_single_stacked, pt_out_16),
        ("batch=16", cv_batch_16, pt_out_16),
        ("batch=1-after-batch=16", cv_after_batch_1, pt_out_1),
    ):
        max_abs_diff = float(np.max(np.abs(got - ref)))
        dot = np.sum(got * ref, axis=1)
        norms = np.linalg.norm(got, axis=1) * np.linalg.norm(ref, axis=1)
        cos_sims = dot / np.maximum(norms, 1e-12)
        min_cos = float(np.min(cos_sims))
        mean_cos = float(np.mean(cos_sims))
        print(
            f"  [check] {label}: min_cos={min_cos:.8f} mean_cos={mean_cos:.8f} "
            f"max_abs_diff={max_abs_diff:.3e}"
        )
        if min_cos <= 0.999999:
            raise AssertionError(
                f"{label} cosine similarity {min_cos:.8f} <= 0.999999"
            )
        if max_abs_diff >= 1e-4:
            raise AssertionError(
                f"{label} max_abs_diff {max_abs_diff:.3e} >= 1e-4"
            )


def main() -> None:
    print(f"Exporting MobileNetV2 ONNX -> {DEFAULT_DATA_ONNX}")
    model, mode_desc = export_mobilenet_v2_to_onnx(DEFAULT_DATA_ONNX)
    size_mb = DEFAULT_DATA_ONNX.stat().st_size / (1024.0 * 1024.0)
    print(f"  Exported via {mode_desc} ({size_mb:.2f} MB)")

    validate_onnx_equivalence(model, DEFAULT_DATA_ONNX)

    DEFAULT_BUNDLED_ONNX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DEFAULT_DATA_ONNX, DEFAULT_BUNDLED_ONNX)
    print(f"  Synced bundled copy -> {DEFAULT_BUNDLED_ONNX}")

    if LEGACY_BUNDLED_PTH.exists():
        LEGACY_BUNDLED_PTH.unlink()
        print(f"  Removed legacy PyTorch checkpoint -> {LEGACY_BUNDLED_PTH}")

    print("ONNX_EXPORT_AND_VALIDATION_OK")


if __name__ == "__main__":
    main()
