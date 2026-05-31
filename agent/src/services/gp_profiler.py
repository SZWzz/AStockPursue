"""GP Engine performance profiling.

Records wall-clock timing for each phase of GP evolution:
    - data loading
    - population initialisation
    - per-generation evaluation (mean, p50, p95, p99)
    - selection & evolution

All timings are logged and exposed via ``GPRunResult.profile`` for
frontend display and optimisation tracking.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PhaseTiming:
    phase: str
    elapsed_s: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationTiming:
    generation: int
    eval_total_s: float
    eval_per_individual_ms: float
    eval_p50_ms: float
    eval_p95_ms: float
    eval_p99_ms: float
    evolve_s: float
    total_s: float


@dataclass
class GPProfile:
    job_id: str
    data_loading_s: float = 0.0
    population_init_s: float = 0.0
    total_generations: int = 0
    total_runtime_s: float = 0.0
    generation_timings: list[GenerationTiming] = field(default_factory=list)
    phases: list[PhaseTiming] = field(default_factory=list)
    peak_memory_mb: float | None = None


class GPProfiler:
    """Collects wall-clock timing for GP evolution phases.

    Usage::

        profiler = GPProfiler(job_id)
        with profiler.phase("data_loading"):
            self._load_data()
        with profiler.phase("generation_3_eval"):
            self.evaluate_population()
    """

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id
        self._gen_timings: list[GenerationTiming] = []
        self._phases: list[PhaseTiming] = []
        self._data_loading_s = 0.0
        self._pop_init_s = 0.0
        self._start_time = time.monotonic()
        self._current_phase_start: float | None = None
        self._current_phase_name: str = ""
        self._individual_times: list[float] = []

    def record_phase(self, name: str, elapsed_s: float, **meta: Any) -> None:
        self._phases.append(PhaseTiming(phase=name, elapsed_s=round(elapsed_s, 4), metadata=meta))

    def record_data_loading(self, elapsed_s: float) -> None:
        self._data_loading_s = elapsed_s

    def record_population_init(self, elapsed_s: float) -> None:
        self._pop_init_s = elapsed_s

    def record_generation(
        self,
        generation: int,
        eval_times_s: list[float],  # per-individual evaluation times
        evolve_s: float,
        total_s: float,
    ) -> None:
        """Record timing for one generation."""
        if not eval_times_s:
            self._gen_timings.append(GenerationTiming(
                generation=generation,
                eval_total_s=0.0,
                eval_per_individual_ms=0.0,
                eval_p50_ms=0.0,
                eval_p95_ms=0.0,
                eval_p99_ms=0.0,
                evolve_s=round(evolve_s, 4),
                total_s=round(total_s, 4),
            ))
            return

        arr = np.array(eval_times_s) * 1000  # convert to ms
        per_ind = float(np.mean(arr))
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        p99 = float(np.percentile(arr, 99))

        self._gen_timings.append(GenerationTiming(
            generation=generation,
            eval_total_s=round(float(np.sum(eval_times_s)), 4),
            eval_per_individual_ms=round(per_ind, 2),
            eval_p50_ms=round(p50, 2),
            eval_p95_ms=round(p95, 2),
            eval_p99_ms=round(p99, 2),
            evolve_s=round(evolve_s, 4),
            total_s=round(total_s, 4),
        ))

    def record_peak_memory(self) -> None:
        """Record current process RSS memory (if psutil is available)."""
        try:
            import psutil
            import os
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info().rss / (1024 * 1024)
            self._phases.append(PhaseTiming(
                phase="peak_memory",
                elapsed_s=0.0,
                metadata={"rss_mb": round(mem, 1)},
            ))
        except ImportError:
            pass

    def to_profile(self) -> GPProfile:
        total = time.monotonic() - self._start_time
        return GPProfile(
            job_id=self._job_id,
            data_loading_s=round(self._data_loading_s, 3),
            population_init_s=round(self._pop_init_s, 3),
            total_generations=len(self._gen_timings),
            total_runtime_s=round(total, 3),
            generation_timings=self._gen_timings,
            phases=self._phases,
        )

    def log_summary(self) -> None:
        """Log a human-readable timing summary."""
        profile = self.to_profile()
        logger.info(
            "GP Profile [%s]: data=%.1fs init=%.1fs gens=%d runtime=%.1fs",
            self._job_id,
            profile.data_loading_s,
            profile.population_init_s,
            profile.total_generations,
            profile.total_runtime_s,
        )
        if profile.generation_timings:
            last = profile.generation_timings[-1]
            logger.info(
                "  Last gen %d: eval=%.1fs (p50=%.1fms p95=%.1fms p99=%.1fms) evolve=%.3fs",
                last.generation,
                last.eval_total_s,
                last.eval_p50_ms,
                last.eval_p95_ms,
                last.eval_p99_ms,
                last.evolve_s,
            )
        # Warn if single-generation time exceeds threshold
        if profile.generation_timings:
            max_gen_s = max(g.eval_total_s for g in profile.generation_timings)
            if max_gen_s > 30:
                logger.warning(
                    "⚠ GP generation time > 30s (max=%.1fs). Consider reducing "
                    "population_size or universe size, or enabling polars backend.",
                    max_gen_s,
                )
