"""
Conditional VLM planner.

Resolves weights only via Model Manager slot `planner.default_model`
(never hardcodes a vendor model id in call sites).

If the bound model is missing / unloadable, returns None so the Rule Engine
result is used (degraded path).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from backend.ai_engine.models.manager import manager as model_manager
from backend.ai_engine.planner.rules import RuleResult
from backend.ai_engine.runtime import vram
from backend.ai_engine.schema import GenerateRequest
from backend.config import get_settings

log = logging.getLogger(__name__)

_PLANNER_SLOT = "planner.default_model"

_SYSTEM = """You are an image-edit planner for a local ComfyUI engine.
Given a user instruction and optional rule hint, output ONLY valid JSON:
{
  "task_type": "edit.clothing_replace|edit.object_replace|edit.face|edit.hair|edit.background|edit.remove_object|edit.add_object|edit.inpaint|edit.outpaint|edit.style_transfer|edit.general_instruction|image.img2img|image.upscale|video.i2v|...",
  "confidence": 0.0-1.0,
  "targets": [{"label": "shirt", "role": "replace_region"}],
  "positive": "English edit instruction for the diffusion model",
  "negative": "negative prompt",
  "perception": ["grounding", "sam2"],
  "identity": {"enabled": true, "method": "pulid"},
  "post_hints": ["face_detailer", "color_match"]
}
Prefer surgical edit task types over generic img2img when objects are named.
"""


@dataclass
class VlmPlanResult:
    task_type: str
    confidence: float
    targets: list[dict[str, Any]] = field(default_factory=list)
    prompts: dict[str, Any] = field(default_factory=dict)
    perception: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    post_hints: list[str] = field(default_factory=list)
    model_id: str = ""
    raw: str = ""
    warnings: list[str] = field(default_factory=list)


# Module-level handles for unload
_loaded_model = None
_loaded_processor = None
_loaded_model_id: Optional[str] = None


def planner_model_available() -> bool:
    """True if planner.default_model is bound and marked installed with a resolvable path."""
    settings = get_settings()
    if not getattr(settings, "ai_engine_vlm_enabled", True):
        return False
    try:
        rec = model_manager.resolve_slot(_PLANNER_SLOT)
    except KeyError:
        return False
    if rec.status not in ("installed", "outdated"):
        return False
    path = _resolve_model_path(rec.model_id)
    return path is not None


def _resolve_model_path(model_id: str) -> Optional[str]:
    settings = get_settings()
    override = getattr(settings, "ai_engine_vlm_model_path", None) or ""
    if override.strip():
        return override.strip()
    rec = model_manager.get(model_id)
    if rec is None:
        return None
    # Prefer explicit local_path on record if present
    local = getattr(rec, "local_path", None)
    if local:
        return str(local)
    if rec.filename and ("/" in rec.filename or "\\" in rec.filename or rec.filename.startswith("Qwen")):
        return rec.filename
    # HuggingFace repo id convention for our catalog entries
    if model_id == "vlm.qwen25_vl_7b":
        return "Qwen/Qwen2.5-VL-7B-Instruct"
    if model_id == "vlm.qwen25_vl_3b":
        return "Qwen/Qwen2.5-VL-3B-Instruct"
    return None


def unload_vlm() -> dict[str, Any]:
    """Fully drop VLM weights before generation stage."""
    global _loaded_model, _loaded_processor, _loaded_model_id
    _loaded_model = None
    _loaded_processor = None
    _loaded_model_id = None
    info = vram.release_stage("vlm_unload")
    info["vlm_unloaded"] = True
    return info


def plan_with_vlm(
    req: GenerateRequest,
    rule: RuleResult,
) -> Optional[VlmPlanResult]:
    """
    Run conditional VLM. Returns None if unavailable or inference fails.
    Always attempts unload afterward.
    """
    settings = get_settings()
    if not getattr(settings, "ai_engine_vlm_enabled", True):
        return None

    try:
        rec = model_manager.resolve_slot(_PLANNER_SLOT)
    except KeyError as exc:
        log.info("planner slot unbound: %s", exc)
        return None

    if rec.status == "missing" and not (getattr(settings, "ai_engine_vlm_model_path", None) or ""):
        # Allow path override to force-run even if catalog says missing
        return None

    path = _resolve_model_path(rec.model_id)
    if not path:
        return None

    try:
        raw = _infer_json(path, req, rule, model_id=rec.model_id)
        parsed = _parse_json_plan(raw)
        if not parsed:
            return VlmPlanResult(
                task_type=rule.task_type,
                confidence=max(rule.confidence, 0.55),
                prompts={
                    "user": req.prompt,
                    "positive": req.prompt_english or req.prompt,
                    "negative": req.negative,
                },
                model_id=rec.model_id,
                raw=raw or "",
                warnings=["vlm_parse_failed"],
            )
        return VlmPlanResult(
            task_type=str(parsed.get("task_type") or rule.task_type),
            confidence=float(parsed.get("confidence") or 0.8),
            targets=list(parsed.get("targets") or rule.targets),
            prompts={
                "user": req.prompt,
                "positive": parsed.get("positive") or req.prompt_english or req.prompt,
                "negative": parsed.get("negative") or req.negative,
            },
            perception=list(parsed.get("perception") or rule.perception),
            identity=dict(parsed.get("identity") or rule.identity or {}),
            post_hints=list(parsed.get("post_hints") or rule.post_hints),
            model_id=rec.model_id,
            raw=raw,
        )
    except Exception as exc:
        log.warning("VLM planner failed: %s", exc)
        return None
    finally:
        unload_vlm()


def _infer_json(
    model_path: str,
    req: GenerateRequest,
    rule: RuleResult,
    *,
    model_id: str,
) -> str:
    """Load model if needed and generate JSON plan text."""
    global _loaded_model, _loaded_processor, _loaded_model_id

    # Prefer transformers path; optional dependency.
    try:
        from transformers import AutoProcessor
    except ImportError as exc:
        raise RuntimeError("transformers not installed for VLM planner") from exc

    user_text = (
        f"Rule hint task_type={rule.task_type} confidence={rule.confidence} reason={rule.reason}\n"
        f"User prompt: {req.prompt}\n"
        f"Normalized English: {req.prompt_english}\n"
        f"Mode: {req.mode}\n"
        "Return JSON only."
    )

    # Try Qwen2.5-VL class; fall back to generic causal LM text-only if vision class missing.
    try:
        from transformers import Qwen2_5_VLForConditionalGeneration
        import torch

        if _loaded_model_id != model_id or _loaded_model is None:
            unload_vlm()
            _loaded_processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            _loaded_model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=dtype,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True,
            )
            _loaded_model_id = model_id

        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                ],
            },
        ]
        # If we have image bytes, attach as vision input when processor supports it
        if req.image_bytes:
            try:
                from io import BytesIO
                from PIL import Image

                img = Image.open(BytesIO(req.image_bytes)).convert("RGB")
                messages[1]["content"].insert(0, {"type": "image", "image": img})
            except Exception:
                pass

        text = _loaded_processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = _loaded_processor(text=[text], return_tensors="pt", padding=True)
        if hasattr(_loaded_model, "device"):
            inputs = {k: v.to(_loaded_model.device) if hasattr(v, "to") else v for k, v in inputs.items()}
        out = _loaded_model.generate(**inputs, max_new_tokens=512)
        trimmed = out[:, inputs["input_ids"].shape[1] :]
        return _loaded_processor.batch_decode(trimmed, skip_special_tokens=True)[0]
    except Exception:
        # Text-only fallback via AutoModelForCausalLM
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        if _loaded_model_id != model_id or _loaded_model is None:
            unload_vlm()
            tok = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            _loaded_model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=dtype,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True,
            )
            _loaded_processor = tok
            _loaded_model_id = model_id

        prompt = f"{_SYSTEM}\n\n{user_text}\nJSON:"
        inputs = _loaded_processor(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}
        out = _loaded_model.generate(**inputs, max_new_tokens=512)
        return _loaded_processor.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)


def _parse_json_plan(raw: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    # Fenced code block
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S)
    if m:
        raw = m.group(1)
    else:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            raw = m.group(0)
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
