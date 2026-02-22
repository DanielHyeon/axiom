from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SelfVerificationOutcome:
    sampled: bool
    risk_level: str
    confidence: float
    passed: bool
    decision: str
    reason: str
    routed_queue: str | None
    checked_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sampled": self.sampled,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "passed": self.passed,
            "decision": self.decision,
            "reason": self.reason,
            "routed_queue": self.routed_queue,
            "checked_at": self.checked_at,
        }


class SelfVerificationHarness:
    def __init__(self) -> None:
        self.metrics = {"checked": 0, "passed": 0, "failed": 0, "routed_hitl": 0}

    @staticmethod
    def _is_sampled(workitem_id: str, payload: dict[str, Any], ratio: float = 0.2) -> bool:
        fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(f"{workitem_id}:{fingerprint}".encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        return bucket < ratio

    def evaluate(self, workitem_id: str, payload: dict[str, Any], agent_mode: str | None = None) -> SelfVerificationOutcome:
        sv_cfg = payload.get("self_verification") if isinstance(payload.get("self_verification"), dict) else {}
        enabled = bool(sv_cfg.get("enabled", False) or (agent_mode or "").upper() == "SELF_VERIFY")
        if not enabled:
            return SelfVerificationOutcome(
                sampled=False,
                risk_level="none",
                confidence=1.0,
                passed=True,
                decision="SKIP",
                reason="self-verification disabled",
                routed_queue=None,
                checked_at=_now(),
            )

        risk_level = str(sv_cfg.get("risk_level", "medium")).lower()
        confidence = float(sv_cfg.get("confidence", 0.95))
        sampled = True if risk_level == "high" else self._is_sampled(workitem_id, payload)
        if not sampled:
            return SelfVerificationOutcome(
                sampled=False,
                risk_level=risk_level,
                confidence=confidence,
                passed=True,
                decision="SKIP",
                reason="sampling skipped",
                routed_queue=None,
                checked_at=_now(),
            )

        self.metrics["checked"] += 1
        force_fail = bool(sv_cfg.get("force_fail", False))
        passed = (confidence >= 0.8) and not force_fail
        if passed:
            self.metrics["passed"] += 1
            return SelfVerificationOutcome(
                sampled=True,
                risk_level=risk_level,
                confidence=confidence,
                passed=True,
                decision="PASS",
                reason="validator pass",
                routed_queue=None,
                checked_at=_now(),
            )

        self.metrics["failed"] += 1
        self.metrics["routed_hitl"] += 1
        return SelfVerificationOutcome(
            sampled=True,
            risk_level=risk_level,
            confidence=confidence,
            passed=False,
            decision="FAIL_ROUTE",
            reason="low confidence or forced fail",
            routed_queue="HITL_QUEUE",
            checked_at=_now(),
        )


self_verification_harness = SelfVerificationHarness()
