from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StressSignals:
    blink_per_min: float | None = None
    jaw_openness: float | None = None
    brow_tension: float | None = None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_stress_index(signals: StressSignals) -> tuple[float | None, str | None]:
    """Improved heuristic (non-medical). Returns (stressIndex 0-100, level)."""
    parts: list[float] = []
    weights: list[float] = []

    if signals.blink_per_min is not None:
        # Improved blink analysis: research shows relaxed = 12-20 bpm, stress = <8 or >30
        bpm = signals.blink_per_min
        if bpm < 6:
            # Very low (fatigue/disengagement)
            blink_score = _clamp((6 - bpm) / 6, 0, 1) * 0.9
        elif bpm < 10:
            # Low-normal
            blink_score = _clamp((10 - bpm) / 4, 0, 1) * 0.4
        elif bpm <= 22:
            # Optimal range
            blink_score = 0.0
        elif bpm <= 30:
            # Elevated (mild stress)
            blink_score = _clamp((bpm - 22) / 8, 0, 1) * 0.5
        else:
            # High (significant stress)
            blink_score = _clamp(0.5 + (bpm - 30) / 25, 0, 1)
        parts.append(blink_score)
        weights.append(1.2)  # Higher weight for blink rate

    if signals.jaw_openness is not None:
        # Jaw tension: moderate openness can indicate stress/talking; extreme = yawning/fatigue
        jaw = signals.jaw_openness
        if jaw < 0.15:
            # Clenched/tense
            jaw_score = 0.3
        elif jaw < 0.35:
            # Relaxed range
            jaw_score = 0.0
        elif jaw < 0.6:
            # Moderate tension/talking
            jaw_score = _clamp((jaw - 0.35) / 0.25, 0, 1) * 0.5
        else:
            # Wide open (yawning/fatigue)
            jaw_score = _clamp((jaw - 0.6) / 0.4, 0, 1) * 0.4
        parts.append(jaw_score)
        weights.append(0.8)

    if signals.brow_tension is not None:
        # Brow tension is a strong stress indicator
        brow = _clamp(signals.brow_tension, 0, 1)
        parts.append(brow)
        weights.append(1.5)  # Highest weight - most reliable

    if not parts:
        return None, None

    # Weighted average for better accuracy
    score01 = sum(p * w for p, w in zip(parts, weights)) / sum(weights)
    stress_index = _clamp(score01 * 100.0, 0, 100)

    # Adjusted thresholds based on weighted scoring
    if stress_index < 30:
        level = "rendah"
    elif stress_index < 60:
        level = "sedang"
    else:
        level = "tinggi"

    return stress_index, level
