"""
schedule_engine.py
------------------
Standalone scheduling module for Amogh Rail (SIH 2026).

Computes:
  - FIFO Baseline: Naive first-come first-served dispatching in order of arrival
    without priority re-sequencing.
  - CP-SAT Optimizer: Google OR-Tools CP-SAT re-sequences trains on single-track
    bottlenecks to minimize sum(priority_weight * total_delay).

Exposes:
  compute_schedule(trains, mode) -> ScheduleResult
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import List

try:
    from ortools.sat.python import cp_model as _cp_model
    _CPSAT_OK = True
except ImportError:
    _CPSAT_OK = False

# Priority weights (Express=3, Suburban/Passenger=2, Freight=1)
PRIORITY_WEIGHT: dict[int, int] = {1: 3, 2: 2, 3: 1}
MIN_HEADWAY: int = 2          # minutes between consecutive trains on a block
HORIZON: int = 2880           # 48 hours in minutes


@dataclass
class TrainSlot:
    train_id: str
    section_id: str
    entry_time: int          # minutes
    exit_time: int           # minutes
    predicted_delay_min: float
    priority: int
    train_type: str
    fifo_entry_time: int
    held_min: int


@dataclass
class ScheduleResult:
    mode: str
    slots: List[TrainSlot]
    objective: float          # total priority-weighted delay (minutes)
    interventions: List[str]  # human-readable descriptions of hold-back decisions
    manual_objective: float = 0.0


STATION_FULL: dict[str, str] = {
    "HWH": "Howrah",
    "BLY": "Bally",
    "SHE": "Seoraphuli Jn",
    "BDC": "Bandel Jn",
    "MMR": "Memari",
    "SKG": "Saktigarh",
    "BWN": "Barddhaman Jn",
    "GUS": "Guskara",
    "PAN": "Panagarh",
}

LOOP_STATION: dict[str, str] = {
    "SHE-SKG": "Seoraphuli loop",
    "SKG-MMR": "Saktigarh loop",
    "MMR-BWN": "Memari loop",
    "BWN-GUS": "Barddhaman loop",
    "GUS-PAN": "Guskara loop",
    "BDC-MMR": "Bandel loop",
    "SKG-BWN": "Saktigarh loop",
}


# ── FIFO Baseline ─────────────────────────────────────────────────────────────

def _fifo_schedule(trains: list[dict]) -> ScheduleResult:
    """
    FIFO: Trains dispatched in order of their ready arrival time (desired + pred).
    No priority reordering.
    """
    section_latest: dict[str, int] = {}
    slots: list[TrainSlot] = []
    objective = 0.0

    # Sort strictly by arrival time at the section (desired + predicted delay)
    sorted_trains = sorted(
        trains,
        key=lambda t: t.get("desired_entry", 0) + int(math.ceil(max(float(t.get("predicted_delay_min", 0.0)), 0.0)))
    )

    for t in sorted_trains:
        sid      = t["section_id"]
        desired  = int(t.get("desired_entry", 0))
        pred     = max(float(t.get("predicted_delay_min", 0.0)), 0.0)
        ready    = desired + int(math.ceil(pred))
        dur      = max(int(t.get("duration", 14)), 5)
        priority = int(t.get("priority", 2))
        tid      = str(t["train_id"])
        ttype    = str(t.get("train_type", "Passenger"))

        earliest = max(ready, section_latest.get(sid, 0) + MIN_HEADWAY)
        entry    = earliest
        ex       = entry + dur

        section_latest[sid] = ex

        total_delay = max(entry - desired, 0)
        wt_delay = total_delay * PRIORITY_WEIGHT.get(priority, 1)
        objective += wt_delay

        slots.append(TrainSlot(
            train_id=tid,
            section_id=sid,
            entry_time=entry,
            exit_time=ex,
            predicted_delay_min=pred,
            priority=priority,
            train_type=ttype,
            fifo_entry_time=entry,
            held_min=0,
        ))

    return ScheduleResult(
        mode="fifo",
        slots=slots,
        objective=round(objective, 1),
        interventions=[],
        manual_objective=round(objective, 1),
    )


# ── CP-SAT Optimizer ─────────────────────────────────────────────────────────

def _cpsat_schedule(trains: list[dict]) -> ScheduleResult:
    """
    CP-SAT Optimizer: Optimizes train passing sequence to minimize
    total priority-weighted delay while respecting no-overlap on each section.
    """
    fifo_result = _fifo_schedule(trains)
    if not _CPSAT_OK:
        return fifo_result

    fifo_map: dict[tuple[str, str], int] = {
        (s.train_id, s.section_id): s.entry_time for s in fifo_result.slots
    }

    model   = _cp_model.CpModel()
    solver  = _cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0

    by_section: dict[str, list[dict]] = {}
    for t in trains:
        by_section.setdefault(t["section_id"], []).append(t)

    entry_vars: dict[tuple[str, str], _cp_model.IntVar] = {}
    interval_vars: dict[tuple[str, str], _cp_model.IntervalVar] = {}

    for sid, sec_trains in by_section.items():
        for t in sec_trains:
            tid      = str(t["train_id"])
            desired  = int(t.get("desired_entry", 0))
            pred     = int(math.ceil(max(float(t.get("predicted_delay_min", 0.0)), 0.0)))
            ready    = desired + pred
            dur      = max(int(t.get("duration", 14)), 5) + MIN_HEADWAY

            e_var = model.NewIntVar(ready, HORIZON, f"e_{tid}_{sid}")
            iv    = model.NewIntervalVar(e_var, dur, e_var + dur, f"iv_{tid}_{sid}")
            entry_vars[(tid, sid)] = e_var
            interval_vars[(tid, sid)] = iv

        # No-overlap constraint per section
        model.AddNoOverlap([interval_vars[(str(t["train_id"]), sid)] for t in sec_trains])

    # Objective: Minimize sum( priority_weight * (entry - desired) )
    terms = []
    for t in trains:
        tid     = str(t["train_id"])
        sid     = str(t["section_id"])
        desired = int(t.get("desired_entry", 0))
        wt      = PRIORITY_WEIGHT.get(int(t.get("priority", 2)), 1)
        d_var   = model.NewIntVar(0, HORIZON, f"d_{tid}_{sid}")
        model.Add(d_var == entry_vars[(tid, sid)] - desired)
        terms.append(d_var * wt)

    model.Minimize(sum(terms))
    status = solver.Solve(model)

    if status not in (_cp_model.OPTIMAL, _cp_model.FEASIBLE):
        return fifo_result

    slots: list[TrainSlot] = []
    objective = float(solver.ObjectiveValue())
    interventions: list[str] = []

    for t in trains:
        tid      = str(t["train_id"])
        sid      = str(t["section_id"])
        desired  = int(t.get("desired_entry", 0))
        dur      = max(int(t.get("duration", 14)), 5)
        priority = int(t.get("priority", 2))
        ttype    = str(t.get("train_type", "Passenger"))
        pred     = max(float(t.get("predicted_delay_min", 0.0)), 0.0)

        entry      = solver.Value(entry_vars[(tid, sid)])
        ex         = entry + dur
        fifo_entry = fifo_map.get((tid, sid), desired)
        held_min   = max(entry - fifo_entry, 0)

        slots.append(TrainSlot(
            train_id=tid,
            section_id=sid,
            entry_time=entry,
            exit_time=ex,
            predicted_delay_min=pred,
            priority=priority,
            train_type=ttype,
            fifo_entry_time=fifo_entry,
            held_min=held_min,
        ))

    # Generate human-readable intervention descriptions
    by_section_ai: dict[str, list[TrainSlot]] = {}
    for s in slots:
        by_section_ai.setdefault(s.section_id, []).append(s)

    by_section_fifo: dict[str, list[TrainSlot]] = {}
    for s in fifo_result.slots:
        by_section_fifo.setdefault(s.section_id, []).append(s)

    for sid, ai_sec in by_section_ai.items():
        fifo_sec = by_section_fifo.get(sid, [])
        if not fifo_sec or len(ai_sec) < 2:
            continue

        ai_sorted   = sorted(ai_sec, key=lambda x: x.entry_time)
        fifo_sorted = sorted(fifo_sec, key=lambda x: x.entry_time)

        ai_ids   = [s.train_id for s in ai_sorted]
        fifo_ids = [s.train_id for s in fifo_sorted]

        # Check for priority re-sequencing
        for i, tid_ai in enumerate(ai_ids):
            if tid_ai in fifo_ids:
                old_idx = fifo_ids.index(tid_ai)
                if old_idx > i:
                    promoted = next(s for s in ai_sec if s.train_id == tid_ai)
                    displaced_id = fifo_ids[i]
                    displaced = next((s for s in ai_sec if s.train_id == displaced_id), None)
                    if displaced and displaced.held_min > 0 and promoted.priority < displaced.priority:
                        loop = LOOP_STATION.get(sid, f"{STATION_FULL.get(sid.split('-')[0], sid.split('-')[0])} loop")
                        
                        # Explicitly tie the ML prediction to the Optimizer's decision for the demo narrative
                        pred_str = f"ML predicted {displaced.predicted_delay_min:.0f}m delay on {displaced.train_id}"
                        if displaced.predicted_delay_min < 5:
                            pred_str = f"{displaced.train_id} was slightly delayed"
                            
                        interventions.append(
                            f"{displaced.train_id} held {displaced.held_min:.0f}m at {loop} — priority to {promoted.train_id} ({promoted.train_type})"
                        )

    return ScheduleResult(
        mode="cpsat",
        slots=slots,
        objective=round(objective, 1),
        interventions=interventions,
        manual_objective=fifo_result.objective,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def compute_schedule(trains: list[dict], mode: str = "cpsat") -> ScheduleResult:
    if not trains:
        return ScheduleResult(mode=mode, slots=[], objective=0.0, interventions=[])
    if mode == "fifo":
        return _fifo_schedule(trains)
    return _cpsat_schedule(trains)
