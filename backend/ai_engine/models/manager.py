"""Model Manager — inventory, slots, preferred/compatible/minimum bind, health."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from backend.ai_engine.registry.workflows import WorkflowRecord, registry
from backend.ai_engine.schema import ModelBindResult


@dataclass
class ModelRecord:
    model_id: str
    version: str = "unknown"
    filename: Optional[str] = None
    local_path: Optional[str] = None
    download_source: Optional[str] = None
    vram_mb: int = 0
    disk_mb: int = 0
    license: str = "unknown"
    compatible_workflows: list[str] = field(default_factory=list)
    replacement_candidates: list[str] = field(default_factory=list)
    benchmark_score: int = 0
    benchmark_estimated: bool = True  # False only after fixture measurement
    role: str = "misc"
    quantization: str = "unknown"
    status: Literal["installed", "missing", "outdated", "disabled"] = "missing"


class ModelManager:
    def __init__(self) -> None:
        self._models: dict[str, ModelRecord] = {}
        self._slots: dict[str, str] = {}

    def register_model(self, record: ModelRecord) -> None:
        self._models[record.model_id] = record

    def set_slot(self, slot: str, model_id: str) -> None:
        self._slots[slot] = model_id

    def get_slot_target(self, slot: str) -> Optional[str]:
        return self._slots.get(slot)

    def resolve_slot(self, slot: str) -> ModelRecord:
        model_id = self._slots.get(slot)
        if not model_id:
            raise KeyError(f"SLOT_UNBOUND: {slot}")
        rec = self._models.get(model_id)
        if rec is None:
            raise KeyError(f"MODEL_MISSING: slot {slot} -> {model_id}")
        return rec

    def get(self, model_id: str) -> Optional[ModelRecord]:
        return self._models.get(model_id)

    def all_models(self) -> list[ModelRecord]:
        return list(self._models.values())

    def is_available(self, model_id: str) -> bool:
        rec = self._models.get(model_id)
        return rec is not None and rec.status in ("installed", "outdated")

    def mark_missing(self, model_id: str) -> None:
        rec = self._models.get(model_id)
        if rec:
            rec.status = "missing"

    def actionable_missing(self, model_id: str) -> dict[str, Any]:
        rec = self._models.get(model_id)
        if rec is None:
            return {
                "model_id": model_id,
                "status": "unknown",
                "download_source": None,
                "hint": f"Register {model_id} in the model catalog",
            }
        return {
            "model_id": model_id,
            "status": rec.status,
            "filename": rec.filename,
            "download_source": rec.download_source,
            "vram_mb": rec.vram_mb,
            "disk_mb": rec.disk_mb,
            "license": rec.license,
            "replacement_candidates": list(rec.replacement_candidates),
            "hint": (
                f"Download {rec.download_source or rec.filename or model_id}"
                if rec.status == "missing"
                else None
            ),
        }

    def bind_backbone(self, workflow: WorkflowRecord) -> ModelBindResult:
        """preferred → compatible → minimum (+ replacement candidates)."""
        for tier, ids in (
            ("preferred", workflow.preferred_models),
            ("compatible", workflow.compatible_models),
            ("minimum", workflow.minimum_models),
        ):
            for mid in ids:
                if self.is_available(mid):
                    rec = self._models[mid]
                    return ModelBindResult(
                        model_id=mid,
                        tier=tier,  # type: ignore[arg-type]
                        filename=rec.filename,
                    )
                rec = self._models.get(mid)
                if rec:
                    for alt in rec.replacement_candidates:
                        if self.is_available(alt):
                            alt_rec = self._models[alt]
                            return ModelBindResult(
                                model_id=alt,
                                tier=tier,  # type: ignore[arg-type]
                                filename=alt_rec.filename,
                            )

        if not workflow.preferred_models and not workflow.compatible_models and not workflow.minimum_models:
            return ModelBindResult(model_id="legacy.unmanaged", tier="none")

        listed = (
            workflow.preferred_models
            + workflow.compatible_models
            + workflow.minimum_models
        )
        if listed and all(not self._models.get(mid) for mid in listed):
            mid = listed[0]
            return ModelBindResult(
                model_id=mid,
                tier="preferred" if workflow.preferred_models else "minimum",
            )

        missing_hints = [self.actionable_missing(m) for m in listed[:5]]
        raise KeyError(
            "MODEL_UNAVAILABLE: "
            f"workflow={workflow.workflow_ref} missing={missing_hints}"
        )

    def ensure(self, model_ids: list[str]) -> list[ModelRecord]:
        out: list[ModelRecord] = []
        missing: list[dict[str, Any]] = []
        for mid in model_ids:
            rec = self._models.get(mid)
            if rec is None or not self.is_available(mid):
                missing.append(self.actionable_missing(mid))
                continue
            out.append(rec)
        if missing:
            raise KeyError(f"MODEL_MISSING: {missing}")
        return out

    def health(
        self,
        *,
        channel: str = "stable",
        allow_beta: bool = False,
        allow_experimental: bool = False,
    ) -> dict[str, Any]:
        """Report slots + missing models for enabled workflows."""
        slots = {}
        for slot, mid in self._slots.items():
            rec = self._models.get(mid)
            slots[slot] = {
                "target_model_id": mid,
                "status": rec.status if rec else "unknown",
                "download_source": rec.download_source if rec else None,
            }

        workflows_report: list[dict[str, Any]] = []
        for wf in registry.all():
            if not wf.enabled:
                continue
            if wf.experimental and not allow_experimental and channel != "experimental":
                continue
            if wf.beta and not allow_beta and channel not in ("beta", "experimental"):
                continue
            required = list(
                dict.fromkeys(
                    wf.preferred_models + wf.compatible_models + wf.minimum_models
                )
            )
            optional_missing = [
                self.actionable_missing(m)
                for m in wf.optional_models
                if not self.is_available(m)
            ]
            # Runnable if at least one of preferred/compatible/minimum is available,
            # or tiers are empty (legacy unmanaged).
            try:
                bind = self.bind_backbone(wf)
                runnable = True
                backbone = {"model_id": bind.model_id, "tier": bind.tier}
                missing_required: list[dict[str, Any]] = []
            except KeyError:
                runnable = False
                backbone = None
                missing_required = [
                    self.actionable_missing(m)
                    for m in required
                    if not self.is_available(m)
                ]

            workflows_report.append(
                {
                    "workflow_ref": wf.workflow_ref,
                    "task_types": wf.task_types,
                    "runnable": runnable,
                    "backbone": backbone,
                    "missing_required": missing_required,
                    "missing_optional": optional_missing,
                    "benchmark_score": wf.benchmark_score,
                    "benchmark_estimated": wf.benchmark_estimated,
                }
            )

        return {
            "slots": slots,
            "models_total": len(self._models),
            "models_installed": sum(
                1 for m in self._models.values() if m.status in ("installed", "outdated")
            ),
            "models_missing": sum(
                1 for m in self._models.values() if m.status == "missing"
            ),
            "workflows": workflows_report,
        }


manager = ModelManager()
