"""Factor Mining REST API — GP evolution, LLM extraction, hybrid mining.

All endpoints are per-user isolated.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.common import safe_error, validate_path_param
from src.auth.dependencies import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/factor-mining", tags=["factor-mining"])

# ---------------------------------------------------------------------------
# In-memory job store (lives for process lifetime)
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}
_candidates_store: dict[str, list[dict[str, Any]]] = {}  # user_id -> candidates


def _get_user_id(auth: dict) -> int:
    return int(auth["user_id"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class GPSetupRequest(BaseModel):
    population_size: int = Field(default=100, ge=10, le=500)
    generations: int = Field(default=50, ge=5, le=200)
    tournament_size: int = Field(default=7, ge=2, le=20)
    crossover_prob: float = Field(default=0.7, ge=0.0, le=1.0)
    mutation_prob: float = Field(default=0.2, ge=0.0, le=1.0)
    fitness_metric: str = Field(default="ic_mean")
    complexity_penalty: str = Field(default="bic")
    train_start: str = Field(default="2023-01-01")
    train_end: str = Field(default="2024-12-31")
    test_start: str = Field(default="2025-01-01")
    test_end: str = Field(default="2025-12-31")
    universe: list[str] = Field(default_factory=list)
    walk_forward_windows: int = Field(default=3, ge=1, le=10)
    oos_stability_weight: float = Field(default=0.5, ge=0.0, le=2.0)


class HybridSetupRequest(BaseModel):
    max_cycles: int = Field(default=5, ge=1, le=20)
    gp_config: GPSetupRequest = Field(default_factory=GPSetupRequest)


class PromoteRequest(BaseModel):
    name: str = ""
    theme: str = "momentum"
    universe: str = "equity_cn"
    description: str = ""


class DebateRequest(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_candidates_to_db(user_id: int, candidates: list[dict[str, Any]], run_id: str = "") -> None:
    """Persist candidates to PostgreSQL."""
    try:
        from src.db.pool import init_pool
        from src.db.pool import get_connection as pg_get_connection
        import psycopg2

        init_pool()
        with pg_get_connection() as conn:
            with conn.cursor() as cur:
                for c in candidates:
                    cur.execute(
                        """INSERT INTO vt_factor_mining_candidates
                           (run_id, user_id, name, formula, expression_json, train_ic, test_ic, test_ir, complexity)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            run_id or None,
                            user_id,
                            c.get("name", ""),
                            c.get("formula", ""),
                            json.dumps(c.get("expression_json") or {}),
                            c.get("train_fitness", 0) or c.get("train_ic", 0),
                            c.get("test_ic", 0),
                            c.get("test_ir", 0),
                            c.get("complexity", 0),
                        ),
                    )
    except Exception as e:
        logger.warning("Failed to persist candidates to DB: %s", e)


def _load_candidates_from_db(user_id: int) -> list[dict[str, Any]]:
    """Load candidates from PostgreSQL."""
    try:
        from src.db.pool import init_pool
        from src.db.pool import get_connection as pg_get_connection

        init_pool()
        with pg_get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, run_id, name, formula, expression_json, train_ic, test_ic, test_ir, complexity, is_promoted, promoted_zoo_id, created_at
                       FROM vt_factor_mining_candidates
                       WHERE user_id = %s ORDER BY created_at DESC""",
                    (user_id,),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "run_id": str(r[1]) if r[1] else "",
                        "name": r[2] or "",
                        "formula": r[3] or "",
                        "expression_json": r[4] if isinstance(r[4], dict) else {},
                        "train_ic": float(r[5] or 0),
                        "test_ic": float(r[6] or 0),
                        "test_ir": float(r[7] or 0),
                        "complexity": int(r[8] or 0),
                        "is_promoted": bool(r[9]),
                        "promoted_zoo_id": r[10] or "",
                        "created_at": r[11].isoformat() if hasattr(r[11], "isoformat") else str(r[11]),
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.debug("Could not load candidates from DB: %s", e)
        return []


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def _sse_from_queue(q: queue.Queue[dict[str, Any]], request: Request):
    """Yield SSE frames from a Python queue (bridge from sync threads)."""
    loop = asyncio.get_event_loop()
    while True:
        if await request.is_disconnected():
            break
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: q.get(timeout=2)),
                timeout=2.5,
            )
            yield f"event: {data.get('type', 'message')}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
        except (queue.Empty, asyncio.TimeoutError):
            # Send heartbeat
            yield f"event: heartbeat\ndata: {{\"ts\": \"{_now_iso()}\"}}\n\n"


# ===================================================================
# GP Evolution endpoints
# ===================================================================

@router.post("/gp/start")
async def start_gp_evolution(req: GPSetupRequest, auth: dict = Depends(require_auth)):
    """Start a new GP evolution run. Returns job_id for SSE streaming."""
    user_id = _get_user_id(auth)

    from src.factors.mining.gp_engine import GPEvolution, GPEvolutionConfig

    config = GPEvolutionConfig(
        population_size=req.population_size,
        generations=req.generations,
        tournament_size=req.tournament_size,
        crossover_prob=req.crossover_prob,
        mutation_prob=req.mutation_prob,
        fitness_metric=req.fitness_metric,  # type: ignore[arg-type]
        complexity_penalty=req.complexity_penalty,  # type: ignore[arg-type]
        train_start=req.train_start,
        train_end=req.train_end,
        test_start=req.test_start,
        test_end=req.test_end,
        universe=req.universe,
        walk_forward_windows=req.walk_forward_windows,
        oos_stability_weight=req.oos_stability_weight,
    )

    gp = GPEvolution(config=config)
    job_id = uuid.uuid4().hex[:12]

    _jobs[job_id] = {
        "id": job_id,
        "type": "gp",
        "status": "running",
        "user_id": user_id,
        "config": config.model_dump(),
        "progress_queue": gp.get_progress_queue(),
        "gp_instance": gp,
        "created_at": _now_iso(),
    }

    # Run GP in background thread
    import threading

    def _run():
        try:
            result = gp.run()
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = {
                "best_individuals": [ind.to_dict() for ind in result.best_individuals],
                "generation_history": [
                    {
                        "generation": g.generation,
                        "best_fitness": g.best_fitness,
                        "mean_fitness": g.mean_fitness,
                        "std_fitness": g.std_fitness,
                        "best_ic": g.best_ic,
                        "diversity": g.diversity,
                    }
                    for g in result.generation_history
                ],
                "best_test_ic": result.best_test_ic,
                "runtime_seconds": result.runtime_seconds,
            }
            # Save candidates
            if result.best_individuals:
                candidates = [ind.to_dict() for ind in result.best_individuals]
                _save_candidates_to_db(user_id, candidates, job_id)
                _jobs[job_id]["candidates"] = candidates
            _jobs[job_id]["candidates_count"] = len(result.best_individuals)
        except Exception as e:
            logger.exception("GP run failed")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {"job_id": job_id, "status": "running"}


@router.get("/gp/{job_id}/stream")
async def gp_evolution_stream(job_id: str, request: Request):
    """SSE stream for GP evolution progress."""
    validate_path_param(job_id, "job_id")
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    q = job.get("progress_queue")
    if q is None:
        raise HTTPException(status_code=404, detail="No progress queue for this job")

    async def event_stream():
        async for frame in _sse_from_queue(q, request):
            yield frame
        # Check final status
        final_status = _jobs.get(job_id, {}).get("status", "unknown")
        yield f"event: done\ndata: {{\"status\": \"{final_status}\"}}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/gp/{job_id}/result")
async def get_gp_result(job_id: str):
    """Get the final result of a GP evolution run."""
    validate_path_param(job_id, "job_id")
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job["id"],
        "status": job.get("status", "unknown"),
        "result": job.get("result", {}),
        "candidates": job.get("candidates", []),
        "candidates_count": job.get("candidates_count", 0),
        "config": job.get("config", {}),
        "error": job.get("error", ""),
    }


@router.get("/gp/{job_id}/generations")
async def get_gp_generations(job_id: str):
    """Get generation-by-generation history for evolution chart."""
    validate_path_param(job_id, "job_id")
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.get("result", {})
    return result.get("generation_history", [])


@router.post("/gp/{job_id}/cancel")
async def cancel_gp_run(job_id: str):
    """Cancel a running GP evolution."""
    validate_path_param(job_id, "job_id")
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    gp = job.get("gp_instance")
    if gp is not None:
        gp.cancel()
        job["status"] = "cancelled"
        return {"status": "cancelled"}
    raise HTTPException(status_code=400, detail="Job cannot be cancelled")


# ===================================================================
# LLM extraction endpoints
# ===================================================================

@router.post("/llm/extract")
async def llm_extract_from_text(request: Request, auth: dict = Depends(require_auth)):
    """Extract factor formulas from research text using LLM."""
    try:
        body = await request.json()
        text = body.get("text", "")
        if not text:
            raise HTTPException(status_code=400, detail="text required")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    from src.factors.mining.llm_miner import LLMFactorMiner

    miner = LLMFactorMiner()
    candidates = miner.extract_from_text(text)

    user_id = _get_user_id(auth)
    cand_dicts = [c.model_dump() for c in candidates]
    _save_candidates_to_db(user_id, cand_dicts)

    return {"candidates": cand_dicts, "count": len(candidates)}


@router.post("/llm/extract-pdf")
async def llm_extract_from_pdf(file: UploadFile, auth: dict = Depends(require_auth)):
    """Upload a PDF research paper and extract factor formulas."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF file required")

    import tempfile

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF too large (max 20MB)")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from src.factors.mining.llm_miner import LLMFactorMiner

        miner = LLMFactorMiner()
        candidates = miner.extract_from_pdf(tmp_path)

        user_id = _get_user_id(auth)
        cand_dicts = [c.model_dump() for c in candidates]
        _save_candidates_to_db(user_id, cand_dicts)

        return {"candidates": cand_dicts, "count": len(candidates)}
    finally:
        try:
            import os
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/llm/debate")
async def llm_debate_candidates(req: DebateRequest, auth: dict = Depends(require_auth)):
    """Multi-LLM debate to filter and score factor candidates."""
    user_id = _get_user_id(auth)

    # Load candidates
    stored = _load_candidates_from_db(user_id)
    if req.candidate_ids:
        stored = [c for c in stored if c["id"] in req.candidate_ids]

    if not stored:
        raise HTTPException(status_code=400, detail="No candidates to debate")

    from src.factors.mining.llm_miner import FactorCandidate, LLMFactorMiner

    candidates = [FactorCandidate(
        name=c.get("name", ""),
        formula=c.get("formula", ""),
        description=c.get("description", ""),
        source="llm",
        confidence=c.get("test_ic", 0.5),
    ) for c in stored]

    miner = LLMFactorMiner()
    filtered = miner.debate_filter(candidates)

    return {"filtered": [f.model_dump() for f in filtered], "original_count": len(candidates), "filtered_count": len(filtered)}


# ===================================================================
# Hybrid mining endpoints
# ===================================================================

@router.post("/hybrid/start")
async def start_hybrid_mining(req: HybridSetupRequest, auth: dict = Depends(require_auth)):
    """Start a hybrid GP+LLM co-evolution run."""
    user_id = _get_user_id(auth)
    job_id = uuid.uuid4().hex[:12]

    from src.factors.mining.gp_engine import GPEvolutionConfig
    from src.factors.mining.hybrid_miner import HybridConfig, HybridMiner

    gp_config = GPEvolutionConfig(
        population_size=req.gp_config.population_size,
        generations=req.gp_config.generations,
        tournament_size=req.gp_config.tournament_size,
        crossover_prob=req.gp_config.crossover_prob,
        mutation_prob=req.gp_config.mutation_prob,
        fitness_metric=req.gp_config.fitness_metric,  # type: ignore[arg-type]
        complexity_penalty=req.gp_config.complexity_penalty,  # type: ignore[arg-type]
        train_start=req.gp_config.train_start,
        train_end=req.gp_config.train_end,
        test_start=req.gp_config.test_start,
        test_end=req.gp_config.test_end,
        universe=req.gp_config.universe,
        walk_forward_windows=getattr(req.gp_config, 'walk_forward_windows', 3),
        oos_stability_weight=getattr(req.gp_config, 'oos_stability_weight', 0.5),
    )

    config = HybridConfig(max_cycles=req.max_cycles, gp_config=gp_config)
    miner = HybridMiner(config=config)

    _jobs[job_id] = {
        "id": job_id,
        "type": "hybrid",
        "status": "running",
        "user_id": user_id,
        "config": config.model_dump(),
        "created_at": _now_iso(),
    }

    import threading

    def _run():
        try:
            result = miner.run()
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["result"] = result.model_dump()
        except Exception as e:
            logger.exception("Hybrid run failed")
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {"job_id": job_id, "status": "running"}


@router.get("/hybrid/{job_id}/stream")
async def hybrid_stream(job_id: str, request: Request):
    """Polling-based SSE for hybrid run (status check every 2s)."""
    validate_path_param(job_id, "job_id")

    async def event_stream():
        while True:
            if await request.is_disconnected():
                break
            job = _jobs.get(job_id)
            if job is None:
                yield f"event: error\ndata: {{\"message\": \"Job not found\"}}\n\n"
                break
            status = job.get("status", "unknown")
            result = job.get("result", {})
            yield f"event: progress\ndata: {json.dumps({'status': status, 'cycles': result.get('cycles_completed', 0), 'best_factors': len(result.get('best_factors', []))})}\n\n"
            if status in ("completed", "failed", "cancelled"):
                yield f"event: done\ndata: {{\"status\": \"{status}\"}}\n\n"
                break
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ===================================================================
# Candidates management
# ===================================================================

@router.get("/candidates")
async def list_candidates(auth: dict = Depends(require_auth)):
    """List all discovered factor candidates for the current user."""
    user_id = _get_user_id(auth)
    candidates = _load_candidates_from_db(user_id)
    return {"candidates": candidates, "total": len(candidates)}


@router.post("/candidates/{candidate_id}/validate")
async def validate_candidate(candidate_id: str, auth: dict = Depends(require_auth)):
    """Run full validation on a candidate factor."""
    validate_path_param(candidate_id, "candidate_id")
    user_id = _get_user_id(auth)
    candidates = _load_candidates_from_db(user_id)
    match = next((c for c in candidates if c["id"] == candidate_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    from src.factors.mining.expression_tree import ExpressionTree
    from src.factors.mining.factor_validator import FactorValidator

    try:
        expr_json = match.get("expression_json", {})
        tree = ExpressionTree.from_dict(expr_json) if expr_json else ExpressionTree.random()
        validator = FactorValidator()
        result = validator.full_validation(tree)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e, "Validation failed"))


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: str, req: PromoteRequest, auth: dict = Depends(require_auth)):
    """Promote a validated candidate factor into Alpha Zoo."""
    validate_path_param(candidate_id, "candidate_id")
    user_id = _get_user_id(auth)
    candidates = _load_candidates_from_db(user_id)
    match = next((c for c in candidates if c["id"] == candidate_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    from src.factors.mining.factor_promoter import FactorPromoter

    try:
        promoter = FactorPromoter()
        alpha_id = promoter.promote_from_candidate(
            formula=match["formula"],
            name=req.name or match.get("name", ""),
            theme=req.theme,
            universe=req.universe,
            description=req.description,
            source="gp_engine",
            test_ic=match.get("test_ic", 0),
            test_ir=match.get("test_ir", 0),
            complexity=match.get("complexity", 0),
        )
        # Update DB
        try:
            from src.db.pool import init_pool
            from src.db.pool import get_connection as pg_get_connection

            init_pool()
            with pg_get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE vt_factor_mining_candidates SET is_promoted=true, promoted_zoo_id=%s WHERE id=%s",
                        (alpha_id, candidate_id),
                    )
        except Exception as e:
            logger.warning("Failed to update promotion status in DB: %s", e)

        return {"ok": True, "alpha_id": alpha_id, "message": f"Factor promoted as {alpha_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e, "Promotion failed"))


@router.delete("/candidates/{candidate_id}")
async def delete_candidate(candidate_id: str, auth: dict = Depends(require_auth)):
    """Delete a candidate factor."""
    validate_path_param(candidate_id, "candidate_id")
    user_id = _get_user_id(auth)
    try:
        from src.db.pool import init_pool
        from src.db.pool import get_connection as pg_get_connection

        init_pool()
        with pg_get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM vt_factor_mining_candidates WHERE id=%s AND user_id=%s",
                    (candidate_id, user_id),
                )
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=safe_error(e))


# ===================================================================
# History
# ===================================================================

@router.get("/history")
async def get_mining_history(auth: dict = Depends(require_auth)):
    """List all mining runs for the current user."""
    user_id = _get_user_id(auth)
    # Return both in-memory jobs and DB records
    user_jobs = [
        {
            "id": j["id"],
            "type": j.get("type", "gp"),
            "status": j.get("status", "unknown"),
            "config": j.get("config", {}),
            "candidates_count": j.get("candidates_count", 0),
            "created_at": j.get("created_at", ""),
        }
        for j in _jobs.values()
        if j.get("user_id") == user_id
    ]
    user_jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return {"runs": user_jobs, "total": len(user_jobs)}
