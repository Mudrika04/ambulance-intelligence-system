"""Experiment runner.

Compares two controllers on the SAME scripted arrival set:

  BASELINE  - fixed-time signal control (no emergency priority)
  PROPOSED  - AI-adaptive emergency priority driven by the real FSM timings

Everything produced here is a DISCRETE-EVENT SIMULATION built from the
configured timings. It is not a field measurement and is labelled as such in
every result payload.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from ..core.config import Config, get_config
from ..core.logging_conf import get_logger

log = get_logger(__name__)

SIM_NOTE = ("Discrete-event simulation using configured signal timings. "
            "Not a field measurement.")


@dataclass
class Arrival:
    index: int
    approach: str
    detect_time: float          # when the ambulance becomes visible to the camera
    stopline_time: float        # when it reaches the stop line


class ExperimentRunner:
    def __init__(self, cfg: Optional[Config] = None, repo=None):
        self.cfg = cfg or get_config()
        self.repo = repo

    # ------------------------------------------------------------------
    def _arrivals(self, n: int, seed: int) -> List[Arrival]:
        rng = random.Random(seed)
        arrivals, t = [], 0.0
        approaches = list((self.cfg.get("roi.approaches") or
                           {"NORTH": None, "SOUTH": None, "EAST": None, "WEST": None}).keys())
        for i in range(n):
            t += rng.uniform(45.0, 95.0)
            lead = rng.uniform(8.0, 16.0)      # seconds of camera visibility before stop line
            arrivals.append(Arrival(i, rng.choice(approaches), t, t + lead))
        return arrivals

    # ------------------------------------------------------------------
    def _fixed_time_green(self, approach: str, t: float) -> float:
        """Next time `approach` receives green under fixed-time control."""
        phase = float(self.cfg.get("signal.normal_phase_duration", 12))
        yellow = float(self.cfg.get("signal.yellow_duration", 3))
        cycle = 2 * (phase + yellow)
        ns = approach in ("NORTH", "SOUTH")
        start = 0.0 if ns else phase + yellow
        base = t - (t % cycle)
        for k in (0, 1):
            g = base + k * cycle + start
            if g >= t:
                return g
            if g <= t < g + phase:
                return t          # already green
        return base + cycle + start

    def _baseline(self, arrivals: List[Arrival]) -> Dict:
        phase = float(self.cfg.get("signal.normal_phase_duration", 12))
        waits, clearances = [], []
        for a in arrivals:
            green = self._fixed_time_green(a.approach, a.stopline_time)
            wait = max(0.0, green - a.stopline_time)
            waits.append(wait)
            clearances.append(wait + 4.0)   # 4 s to traverse the intersection
        return {
            "arm": "BASELINE_FIXED_TIME",
            "arrivals": len(arrivals),
            "mean_wait_s": round(sum(waits) / len(waits), 2),
            "max_wait_s": round(max(waits), 2),
            "mean_clearance_s": round(sum(clearances) / len(clearances), 2),
            "priority_activations": 0,
            "unnecessary_activations": 0,
            "mean_activation_latency_s": None,
            "waits": [round(w, 2) for w in waits],
        }

    def _proposed(self, arrivals: List[Arrival]) -> Dict:
        required = int(self.cfg.get("validation.required_frames", 5))
        fps = float(self.cfg.get("video.target_fps", 15) or 15)
        prepare = float(self.cfg.get("signal.prepare_duration", 3))
        all_red = float(self.cfg.get("signal.all_red_duration", 2))
        validation_s = required / max(1.0, fps)
        activation_latency = validation_s + prepare + all_red
        waits, clearances, latencies = [], [], []
        for a in arrivals:
            green = a.detect_time + activation_latency
            wait = max(0.0, green - a.stopline_time)
            waits.append(wait)
            clearances.append(wait + 4.0)
            latencies.append(activation_latency)
        return {
            "arm": "PROPOSED_AI_ADAPTIVE",
            "arrivals": len(arrivals),
            "mean_wait_s": round(sum(waits) / len(waits), 2),
            "max_wait_s": round(max(waits), 2),
            "mean_clearance_s": round(sum(clearances) / len(clearances), 2),
            "priority_activations": len(arrivals),
            "unnecessary_activations": 0,
            "mean_activation_latency_s": round(sum(latencies) / len(latencies), 2),
            "validation_delay_s": round(validation_s, 3),
            "waits": [round(w, 2) for w in waits],
        }

    # ------------------------------------------------------------------
    def run(self, scenario: str = "default", arrivals: int = 20,
            seed: int = 42) -> Dict:
        arrival_list = self._arrivals(arrivals, seed)
        baseline = self._baseline(arrival_list)
        proposed = self._proposed(arrival_list)
        b, p = baseline["mean_wait_s"], proposed["mean_wait_s"]
        reduction = None if b <= 0 else round((b - p) / b * 100.0, 1)
        exp_id = f"EXP-{uuid.uuid4().hex[:8].upper()}"
        results = {
            "experiment_id": exp_id,
            "scenario": scenario,
            "simulation": True,
            "note": SIM_NOTE,
            "arrivals": [asdict(a) for a in arrival_list],
            "baseline": baseline,
            "proposed": proposed,
            "comparison": {
                "mean_wait_reduction_pct": reduction,
                "mean_wait_baseline_s": b,
                "mean_wait_proposed_s": p,
            },
            "created_at": time.time(),
        }
        if self.repo is not None:
            self.repo.save_experiment(
                experiment_id=exp_id, scenario=scenario,
                mode="simulation",
                configuration={"signal": self.cfg.get("signal"),
                               "validation": self.cfg.get("validation"),
                               "arrivals": arrivals, "seed": seed},
                results=results, notes=SIM_NOTE)
            self.repo.save_metric("mean_wait_baseline_s", b, "s", exp_id)
            self.repo.save_metric("mean_wait_proposed_s", p, "s", exp_id)
            if reduction is not None:
                self.repo.save_metric("mean_wait_reduction_pct", reduction, "%", exp_id)
        log.info("experiment complete", extra={"event": "EXPERIMENT_COMPLETE"})
        return results
