"""
simulation.py  —  Amogh Rail · SIH 2026 demo
=============================================
Drives the live simulation clock. On every step() call it advances a
logical sim-time counter (minutes), computes which trains are currently
between their scheduled entry and exit times, and builds a state snapshot
that is streamed to the frontend via WebSocket.
"""

from __future__ import annotations

import math
import time
import sys, io
from typing import Dict, List, Optional
import pandas as pd

from Predictor import predict_delay
from schedule_engine import (
    compute_schedule, ScheduleResult, TrainSlot,
    PRIORITY_WEIGHT, STATION_FULL,
)
from rich.console import Console
from rich.table import Table

console = Console(file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout)

# ── Exact Indian Railways ER Howrah–Barddhaman Main Line Geography ──────────

STATIONS: Dict[str, tuple] = {
    "HWH": (22.5839, 88.3425),  # Howrah Terminal
    "BLY": (22.6500, 88.3400),  # Bally
    "SHE": (22.7550, 88.3400),  # Seoraphuli Jn
    "BDC": (22.9200, 88.3800),  # Bandel Jn
    "MMR": (23.2000, 88.1300),  # Memari
    "SKG": (23.2600, 88.0300),  # Saktigarh Jn
    "BWN": (23.2500, 87.8600),  # Barddhaman Jn
    "GUS": (23.4700, 87.8500),  # Guskara
    "PAN": (23.4800, 87.4300),  # Panagarh
}

ROUTE_ORDER = ["HWH", "BLY", "SHE", "BDC", "MMR", "SKG", "BWN", "GUS", "PAN"]

TRACK_TYPE: Dict[str, str] = {
    "HWH-BLY": "Double", "BLY-HWH": "Double",
    "BLY-SHE": "Double", "SHE-BLY": "Double",
    "SHE-BDC": "Double", "BDC-SHE": "Double",
    "SHE-SKG": "Single", "SKG-SHE": "Single",
    "BDC-MMR": "Single", "MMR-BDC": "Single",
    "MMR-SKG": "Single", "SKG-MMR": "Single",
    "SKG-BWN": "Single", "BWN-SKG": "Single",
    "MMR-BWN": "Single", "BWN-MMR": "Single",
    "BWN-GUS": "Single", "GUS-BWN": "Single",
    "GUS-PAN": "Single", "PAN-GUS": "Single",
}

# ── Pre-configured Realistic Morning Peak Demo Scenario (08:00 to 09:15) ────

DEMO_SCENARIO_SEEDS = [
    # Bottleneck 1: SHE-SKG (Single Track)
    # Freight arrives 08:08 (delayed from 08:00), Express arrives 08:12, Suburban local arrives 08:18
    {
        "train_id": "FR221", "train_type": "Freight", "priority": 3,
        "section_id": "SHE-SKG", "desired_entry": 480, "duration": 18,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 12.0, "section_congestion_level": 0.75,
        "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 14.0
    },
    {
        "train_id": "12042", "train_type": "Express", "priority": 1,
        "section_id": "SHE-SKG", "desired_entry": 490, "duration": 12,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.50,
        "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0
    },
    {
        "train_id": "34005", "train_type": "Suburban", "priority": 2,
        "section_id": "SHE-SKG", "desired_entry": 495, "duration": 14,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.60,
        "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 3.0
    },

    # Bottleneck 2: MMR-BWN (Single Track)
    # Freight arrives 08:26 (desired 08:10 + 16m delay), Vande Bharat Express arrives 08:31, Passenger arrives 08:34
    {
        "train_id": "FR222", "train_type": "Freight", "priority": 3,
        "section_id": "MMR-BWN", "desired_entry": 490, "duration": 18,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 16.0, "section_congestion_level": 0.80,
        "weather_flag": 2, "track_type": "Single", "dataset_delay_min": 18.0
    },
    {
        "train_id": "12044", "train_type": "Express", "priority": 1,
        "section_id": "MMR-BWN", "desired_entry": 510, "duration": 12,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.45,
        "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.5
    },
    {
        "train_id": "14202", "train_type": "Passenger", "priority": 2,
        "section_id": "MMR-BWN", "desired_entry": 514, "duration": 15,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.55,
        "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 3.0
    },

    # Bottleneck 3: BWN-GUS (Single Track)
    # Heavy Freight arrives 08:44 (desired 08:30 + 14m delay), Rajdhani Express arrives 08:51
    {
        "train_id": "FR225", "train_type": "Freight", "priority": 3,
        "section_id": "BWN-GUS", "desired_entry": 510, "duration": 18,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 14.0, "section_congestion_level": 0.70,
        "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 16.0
    },
    {
        "train_id": "12040", "train_type": "Express", "priority": 1,
        "section_id": "BWN-GUS", "desired_entry": 530, "duration": 12,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.40,
        "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.5
    },

    # Feeder Double Track Sections (Smooth flow with suburban frequency)
    {
        "train_id": "34001", "train_type": "Suburban", "priority": 2,
        "section_id": "HWH-BLY", "desired_entry": 480, "duration": 10,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.35,
        "weather_flag": 0, "track_type": "Double", "dataset_delay_min": 1.0
    },
    {
        "train_id": "12046", "train_type": "Express", "priority": 1,
        "section_id": "BLY-SHE", "desired_entry": 485, "duration": 10,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 0.5, "section_congestion_level": 0.30,
        "weather_flag": 0, "track_type": "Double", "dataset_delay_min": 1.0
    },
    {
        "train_id": "FR220", "train_type": "Freight", "priority": 3,
        "section_id": "SHE-BDC", "desired_entry": 492, "duration": 14,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 8.0, "section_congestion_level": 0.50,
        "weather_flag": 1, "track_type": "Double", "dataset_delay_min": 9.0
    },
    {
        "train_id": "14200", "train_type": "Passenger", "priority": 2,
        "section_id": "GUS-PAN", "desired_entry": 540, "duration": 14,
        "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak",
        "season": "Monsoon", "upstream_delay_min": 4.0, "section_congestion_level": 0.40,
        "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 5.0
    },
]


RUSH_HOUR_SCENARIO = [
    # Bottleneck 1: SHE-SKG (Single Track)
    { "train_id": "FR301", "train_type": "Freight", "priority": 3, "section_id": "SHE-SKG", "desired_entry": 480, "duration": 18, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 15.0, "section_congestion_level": 0.8, "weather_flag": 2, "track_type": "Single", "dataset_delay_min": 15.0 },
    { "train_id": "12042", "train_type": "Express", "priority": 1, "section_id": "SHE-SKG", "desired_entry": 485, "duration": 12, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.8, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0 },
    { "train_id": "34011", "train_type": "Suburban", "priority": 2, "section_id": "SHE-SKG", "desired_entry": 488, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.8, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },
    { "train_id": "34013", "train_type": "Suburban", "priority": 2, "section_id": "SHE-SKG", "desired_entry": 491, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.8, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },
    { "train_id": "34015", "train_type": "Suburban", "priority": 2, "section_id": "SHE-SKG", "desired_entry": 494, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.8, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },
    { "train_id": "34017", "train_type": "Suburban", "priority": 2, "section_id": "SHE-SKG", "desired_entry": 497, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.8, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },

    # Bottleneck 2: MMR-BWN (Single Track)
    { "train_id": "FR302", "train_type": "Freight", "priority": 3, "section_id": "MMR-BWN", "desired_entry": 490, "duration": 18, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 10.0, "section_congestion_level": 0.85, "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 12.0 },
    { "train_id": "12044", "train_type": "Express", "priority": 1, "section_id": "MMR-BWN", "desired_entry": 496, "duration": 12, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.85, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.0 },
    { "train_id": "14202", "train_type": "Passenger", "priority": 2, "section_id": "MMR-BWN", "desired_entry": 499, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.85, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },
    { "train_id": "34021", "train_type": "Suburban", "priority": 2, "section_id": "MMR-BWN", "desired_entry": 502, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.85, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0 },
    { "train_id": "34023", "train_type": "Suburban", "priority": 2, "section_id": "MMR-BWN", "desired_entry": 505, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.85, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0 },
    { "train_id": "34025", "train_type": "Suburban", "priority": 2, "section_id": "MMR-BWN", "desired_entry": 508, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.85, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0 },

    # Bottleneck 3: BWN-GUS
    { "train_id": "FR305", "train_type": "Freight", "priority": 3, "section_id": "BWN-GUS", "desired_entry": 505, "duration": 18, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 8.0, "section_congestion_level": 0.75, "weather_flag": 1, "track_type": "Single", "dataset_delay_min": 10.0 },
    { "train_id": "12040", "train_type": "Express", "priority": 1, "section_id": "BWN-GUS", "desired_entry": 512, "duration": 12, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.75, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.5 },
    { "train_id": "34031", "train_type": "Suburban", "priority": 2, "section_id": "BWN-GUS", "desired_entry": 515, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.75, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.0 },
    { "train_id": "34033", "train_type": "Suburban", "priority": 2, "section_id": "BWN-GUS", "desired_entry": 518, "duration": 15, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.75, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 1.0 },

    # Feeder Double Track Sections
    { "train_id": "34001", "train_type": "Suburban", "priority": 2, "section_id": "HWH-BLY", "desired_entry": 482, "duration": 10, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.5, "weather_flag": 0, "track_type": "Double", "dataset_delay_min": 0.0 },
    { "train_id": "34003", "train_type": "Suburban", "priority": 2, "section_id": "HWH-BLY", "desired_entry": 486, "duration": 10, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.5, "weather_flag": 0, "track_type": "Double", "dataset_delay_min": 0.0 },
    { "train_id": "12046", "train_type": "Express", "priority": 1, "section_id": "BLY-SHE", "desired_entry": 483, "duration": 10, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 0.0, "section_congestion_level": 0.5, "weather_flag": 0, "track_type": "Double", "dataset_delay_min": 0.0 },
    { "train_id": "FR220", "train_type": "Freight", "priority": 3, "section_id": "SHE-BDC", "desired_entry": 486, "duration": 14, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 5.0, "section_congestion_level": 0.5, "weather_flag": 1, "track_type": "Double", "dataset_delay_min": 6.0 },
    { "train_id": "14200", "train_type": "Passenger", "priority": 2, "section_id": "GUS-PAN", "desired_entry": 525, "duration": 14, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 2.0, "section_congestion_level": 0.5, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 3.0 },
    { "train_id": "14204", "train_type": "Passenger", "priority": 2, "section_id": "GUS-PAN", "desired_entry": 528, "duration": 14, "day_of_week": 3, "is_weekend": 0, "time_of_day_bucket": "Peak", "season": "Monsoon", "upstream_delay_min": 1.0, "section_congestion_level": 0.5, "weather_flag": 0, "track_type": "Single", "dataset_delay_min": 2.0 },
]

import random

def generate_scenario_from_dataset(num_trains: int = 22, seed: int = None) -> list[dict]:
    """Returns a high-density rush hour scenario. Randomizes variations unless a specific seed is provided."""
    if seed is not None:
        random.seed(seed)
    else:
        random.seed()
        
    seeds = [dict(s) for s in RUSH_HOUR_SCENARIO] # deep copy dicts
    
    for s in seeds:
        # vary desired_entry by +/- 5 mins
        s["desired_entry"] += random.randint(-5, 5)
        # Randomize initial upstream delay slightly, particularly for freight
        if s["train_type"] == "Freight":
            s["upstream_delay_min"] = max(0.0, s["upstream_delay_min"] + random.uniform(-10.0, 15.0))
            s["weather_flag"] = random.choice([0, 1, 2])
        else:
            s["upstream_delay_min"] = max(0.0, s["upstream_delay_min"] + random.uniform(-3.0, 5.0))
            s["weather_flag"] = random.choice([0, 0, 0, 1])

        s["dataset_delay_min"] = s["upstream_delay_min"] * 1.2
            
    seeds.sort(key=lambda x: x["desired_entry"])
    return seeds


class RailwaySimulation:
    """Main simulation controller for Amogh Rail SIH demo."""

    def __init__(self):
        self.mode             = "manual"   # "manual" | "ai"
        self.is_running       = False
        self.simulation_speed = 1.0        # sim-minutes per real second
        self.sim_time: float  = 480.0      # start at 08:00 AM (480 min)
        self._min_dep: int    = 480

        self._fifo_result:  Optional[ScheduleResult] = None
        self._ai_result:    Optional[ScheduleResult] = None
        self._train_features: List[dict] = []
        self.trains_state:  Dict[str, dict] = {}
        self.interventions: List[dict] = []

        self._fifo_objective: float = 0.0
        self._ai_objective:   float = 0.0

        console.print("[bold green]AMOGH RAIL — SIH 2026 Real Corridor Demo initialising…[/bold green]")
        self._load_and_solve()

    def _load_and_solve(self, seed: int = None):
        """Run ML predictions on each train seed, then compute FIFO & CP-SAT schedules."""
        train_inputs: List[dict] = []
        feature_rows: List[dict] = []

        scenario_seeds = generate_scenario_from_dataset(15, seed=seed)
        
        # Ensure our simulation starts near the first train's departure if needed
        if scenario_seeds and self.sim_time == 480.0:
            first_train_entry = min(s["desired_entry"] for s in scenario_seeds)
            if first_train_entry > 500 or first_train_entry < 460:
                self.sim_time = float(first_train_entry)
                self._min_dep = int(first_train_entry)

        console.print(f"[cyan]Running ML Delay Predictions for {len(scenario_seeds)} corridor trains…[/cyan]")
        for row in scenario_seeds:
            try:
                pred = predict_delay(
                    train_type               = row["train_type"],
                    priority                 = row["priority"],
                    section_id               = row["section_id"],
                    day_of_week              = row["day_of_week"],
                    is_weekend               = row["is_weekend"],
                    time_of_day_bucket       = row["time_of_day_bucket"],
                    season                   = row["season"],
                    upstream_delay_min       = row["upstream_delay_min"],
                    section_congestion_level = row["section_congestion_level"],
                    weather_flag             = row["weather_flag"],
                    track_type               = row["track_type"],
                )
            except Exception as exc:
                console.print(f"[red][ML Error] {row['train_id']}: {exc}[/red]")
                pred = {
                    "predicted_delay_min": row.get("dataset_delay_min", 5.0),
                    "is_delayed": True,
                    "delay_probability_pct": 85.0,
                    "threshold_used_min": 10,
                    "reasoning": ["Upstream congestion"],
                }

            entry = row.copy()
            entry["predicted_delay_min"]   = pred["predicted_delay_min"]
            entry["is_delayed"]            = pred["is_delayed"]
            entry["delay_probability_pct"] = pred["delay_probability_pct"]
            entry["reasoning"]             = pred.get("reasoning", [])

            train_inputs.append(entry)
            feature_rows.append(entry.copy())

        self._train_features = feature_rows

        # Compute Schedules
        self._fifo_result  = compute_schedule(train_inputs, mode="fifo")
        self._ai_result    = compute_schedule(train_inputs, mode="cpsat")

        self._fifo_objective = self._fifo_result.objective
        self._ai_objective   = self._ai_result.objective
        saved = max(self._fifo_objective - self._ai_objective, 0.0)
        pct   = (saved / self._fifo_objective * 100) if self._fifo_objective > 0 else 0

        # Print detailed table to console
        table = Table(title="SIH 2026 Corridor Schedules (Manual FIFO vs AI CP-SAT)")
        table.add_column("Train ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Priority", justify="center")
        table.add_column("Section", style="yellow")
        table.add_column("ML Pred Delay", justify="right", style="green")
        table.add_column("FIFO Entry", justify="right", style="yellow")
        table.add_column("AI Entry", justify="right", style="bold green")
        table.add_column("Held (Loop)", justify="right", style="red")

        ai_map = { (s.train_id, s.section_id): s for s in self._ai_result.slots }
        for s in self._fifo_result.slots:
            ai_s = ai_map.get((s.train_id, s.section_id))
            ai_entry = ai_s.entry_time if ai_s else s.entry_time
            held = ai_s.held_min if ai_s else 0
            table.add_row(
                s.train_id, s.train_type, str(s.priority), s.section_id,
                f"{s.predicted_delay_min:.1f}m", f"{s.entry_time}", f"{ai_entry}",
                f"{held}m" if held > 0 else "—"
            )

        console.print(table)
        console.print(
            f"[bold green]✓ Schedulers Solved:[/bold green] "
            f"Manual (FIFO) = [yellow]{self._fifo_objective:.1f} min·wt[/yellow] | "
            f"AI (CP-SAT) = [green]{self._ai_objective:.1f} min·wt[/green] | "
            f"Delay Saved = [bold green]{saved:.1f} min ({pct:.1f}% throughput boost!)[/bold green]"
        )

        for iv in self._ai_result.interventions:
            console.print(f"  [bold cyan]⚡ AI Decision:[/bold cyan] {iv}")

        self._build_trains_state(train_inputs)
        self._build_interventions()

    def _build_trains_state(self, train_inputs: List[dict]):
        self.trains_state = {}
        for t in train_inputs:
            tid = t["train_id"]
            first_sid  = t["section_id"]
            start_code = first_sid.split("-")[0]
            lat, lng   = STATIONS.get(start_code, STATIONS["HWH"])

            self.trains_state[tid] = {
                "id":                    tid,
                "train_type":            t["train_type"],
                "priority":              t["priority"],
                "current_block":         None,
                "status":                "WAITING",
                "actual_delay_sec":      0,
                "predicted_delay_min":   t["predicted_delay_min"],
                "is_delayed_prediction": t["is_delayed"],
                "delay_probability_pct": t["delay_probability_pct"],
                "prediction_error_min":  round(abs(t["predicted_delay_min"] - t["dataset_delay_min"]), 2),
                "reasoning":             t["reasoning"],
                "dataset_delay_min":     t["dataset_delay_min"],
                "progress":              0.0,
                "lat":                   lat,
                "lng":                   lng,
                "track_type":            t["track_type"],
                "weather_flag":          t["weather_flag"],
                "upstream_delay_min":    t["upstream_delay_min"],
                "held_min":              0,
                "entry_time":            t["desired_entry"],
                "exit_time":             t["desired_entry"] + t["duration"],
                "fifo_entry_time":       t["desired_entry"],
                "disrupted":             False,
            }

    def _build_interventions(self):
        self.interventions = []
        
        # 1. Prediction Lines (from ML)
        for t in self._train_features:
            weather_str = "FOG" if t["weather_flag"] == 2 else "RAIN" if t["weather_flag"] == 1 else "CLEAR"
            reasoning = " | ".join(t.get("reasoning", []))
            pred_text = f"Pred: {t['train_id']} | Upstream +{t['upstream_delay_min']}m | {weather_str} | Delay Prob: {t['delay_probability_pct']:.0f}% -> +{t['predicted_delay_min']}m ({reasoning})"
            self.interventions.append({
                "type": "prediction",
                "text": pred_text,
                "sim_time": self._min_dep,
                "delay_saved": 0.0,
                "train_id": t["train_id"]
            })

        # 2. Action Lines (from CP-SAT)
        saved = max(self._fifo_objective - self._ai_objective, 0.0)
        per_iv = round(saved / max(len(self._ai_result.interventions), 1), 1) if self._ai_result else 0
        for iv_text in (self._ai_result.interventions if self._ai_result else []):
            self.interventions.append({
                "type": "action",
                "text":       iv_text,
                "sim_time":   self._min_dep,
                "delay_saved": per_iv,
            })

    def step(self, dt: float):
        if not self.is_running:
            return
        self.sim_time += dt
        self._update_trains()

    def _active_schedule(self) -> ScheduleResult | None:
        return self._ai_result if self.mode == "ai" else self._fifo_result

    def _update_trains(self):
        sched = self._active_schedule()
        if sched is None:
            return

        t_now = self.sim_time
        train_slots: dict[str, list[TrainSlot]] = {}
        for s in sched.slots:
            train_slots.setdefault(s.train_id, []).append(s)

        for tid, state in self.trains_state.items():
            slots = sorted(train_slots.get(tid, []), key=lambda x: x.entry_time)
            if not slots:
                continue

            last_slot = slots[-1]

            active: TrainSlot | None = None
            for s in slots:
                if s.entry_time <= t_now < s.exit_time:
                    active = s
                    break

            if t_now >= last_slot.exit_time:
                state["status"]        = "COMPLETED"
                state["current_block"] = None
                end_code = last_slot.section_id.split("-")[-1]
                state["lat"], state["lng"] = STATIONS.get(end_code, (state["lat"], state["lng"]))
                state["progress"]      = 1.0
                continue

            next_slot: TrainSlot | None = None
            for s in slots:
                if s.entry_time > t_now:
                    next_slot = s
                    break

            if active is not None:
                sid        = active.section_id
                parts      = sid.split("-")
                start_code = parts[0]
                end_code   = parts[1] if len(parts) > 1 else parts[0]
                lat0, lng0 = STATIONS.get(start_code, STATIONS["HWH"])
                lat1, lng1 = STATIONS.get(end_code,   STATIONS["HWH"])

                dur = max(active.exit_time - active.entry_time, 1)
                p   = min((t_now - active.entry_time) / dur, 1.0)

                delay_sec = max(int((t_now - state.get("fifo_entry_time", active.entry_time)) * 60), 0)
                state.update({
                    "status":        "DELAYED" if active.held_min > 0 else "ON TIME",
                    "current_block": sid,
                    "track_type":    TRACK_TYPE.get(sid, "Single"),
                    "lat":           lat0 + (lat1 - lat0) * p,
                    "lng":           lng0 + (lng1 - lng0) * p,
                    "progress":      p,
                    "held_min":      active.held_min,
                    "entry_time":    active.entry_time,
                    "exit_time":     active.exit_time,
                    "fifo_entry_time": active.fifo_entry_time,
                    "actual_delay_sec": active.held_min * 60,
                })

            elif next_slot is not None:
                sid        = next_slot.section_id
                start_code = sid.split("-")[0]
                lat0, lng0 = STATIONS.get(start_code, STATIONS["HWH"])
                held = max(next_slot.entry_time - next_slot.fifo_entry_time, 0)
                state.update({
                    "status":        "WAITING",
                    "current_block": sid,
                    "track_type":    TRACK_TYPE.get(sid, "Single"),
                    "lat":           lat0,
                    "lng":           lng0,
                    "progress":      0.0,
                    "held_min":      held,
                    "entry_time":    next_slot.entry_time,
                    "exit_time":     next_slot.exit_time,
                    "fifo_entry_time": next_slot.fifo_entry_time,
                    "actual_delay_sec": held * 60,
                })
            else:
                first_slot  = slots[0]
                start_code  = first_slot.section_id.split("-")[0]
                lat0, lng0  = STATIONS.get(start_code, STATIONS["HWH"])
                state.update({
                    "status": "WAITING",
                    "current_block": None,
                    "lat":  lat0,
                    "lng":  lng0,
                    "progress": 0.0,
                })

    def apply_disruption(self, train_id: str, upstream_delay_min: float, weather_flag: int):
        updated: list[dict] = []
        for row in self._train_features:
            if row["train_id"] == train_id:
                row = row.copy()
                row["upstream_delay_min"] = upstream_delay_min
                row["weather_flag"]       = weather_flag
                try:
                    pred = predict_delay(
                        train_type               = row["train_type"],
                        priority                 = row["priority"],
                        section_id               = row["section_id"],
                        day_of_week              = 3,
                        is_weekend               = 0,
                        time_of_day_bucket       = "Peak",
                        season                   = "Monsoon" if weather_flag == 1 else "Summer",
                        upstream_delay_min       = upstream_delay_min,
                        section_congestion_level = row["section_congestion_level"],
                        weather_flag             = weather_flag,
                        track_type               = row["track_type"],
                    )
                    row["predicted_delay_min"]   = pred["predicted_delay_min"]
                    row["is_delayed"]            = pred["is_delayed"]
                    row["delay_probability_pct"] = pred["delay_probability_pct"]
                    row["reasoning"]             = pred.get("reasoning", [])
                except Exception:
                    pass

                if train_id in self.trains_state:
                    self.trains_state[train_id]["predicted_delay_min"]   = row["predicted_delay_min"]
                    self.trains_state[train_id]["is_delayed_prediction"] = row["is_delayed"]
                    self.trains_state[train_id]["delay_probability_pct"] = row["delay_probability_pct"]
                    self.trains_state[train_id]["reasoning"]             = row["reasoning"]
                    self.trains_state[train_id]["upstream_delay_min"]    = upstream_delay_min
                    self.trains_state[train_id]["weather_flag"]          = weather_flag
                    self.trains_state[train_id]["disrupted"]             = True
            updated.append(row)

        self._train_features = updated

        console.print(f"[bold yellow]⚡ LIVE DISRUPTION ON {train_id} — Re-solving schedule…[/bold yellow]")
        self._fifo_result   = compute_schedule(updated, mode="fifo")
        self._ai_result     = compute_schedule(updated, mode="cpsat")
        self._fifo_objective = self._fifo_result.objective
        self._ai_objective   = self._ai_result.objective

        saved = max(self._fifo_objective - self._ai_objective, 0.0)

        weather_str = "FOG" if weather_flag == 2 else "RAIN" if weather_flag == 1 else "CLEAR"
        
        # Insert action lines (at the beginning, so they show up at the top if sorting is descending, but wait, list is ordered. Let's just append)
        # Actually, self.interventions is returned in order, frontend displays it.
        # Let's insert at index 0 so it's at the top.
        
        # Insert actions first (so they are below predictions if prepended)
        for iv_text in self._ai_result.interventions:
            self.interventions.insert(0, {
                "type":       "action",
                "text":       iv_text,
                "sim_time":   self.sim_time,
                "delay_saved": round(saved / max(len(self._ai_result.interventions), 1), 1),
            })
            
        # Insert the prediction line
        for row in updated:
            if row["train_id"] == train_id:
                reasoning = " | ".join(row.get("reasoning", []))
                pred_text = f"Pred: {train_id} | Upstream +{upstream_delay_min}m | {weather_str} | Delay Prob: {row['delay_probability_pct']:.0f}% -> +{row['predicted_delay_min']}m ({reasoning})"
                self.interventions.insert(0, {
                    "type": "prediction",
                    "text": pred_text,
                    "sim_time": self.sim_time,
                    "delay_saved": 0.0,
                    "train_id": train_id
                })
                break
                
        self.interventions.insert(0, {
            "type": "action",
            "text": f"⚡ DISRUPTION: {train_id} +{upstream_delay_min:.0f}m upstream delay ({weather_str.title()}). CP-SAT resequenced bottlenecks.",
            "sim_time": self.sim_time,
            "delay_saved": round(saved, 1),
        })

        if len(self.interventions) > 20:
            self.interventions = self.interventions[:20]

    def get_state(self) -> dict:
        all_trains = list(self.trains_state.values())

        # Bug 2 Fix: Active trains are strictly trains currently in transit
        t_now = self.sim_time
        active = [
            t for t in all_trains
            if t["entry_time"] <= t_now < t["exit_time"] and t["status"] != "COMPLETED"
        ]

        # Bug 3 Fix: Distinct metric definitions
        delayed = [t for t in active if t["status"] == "DELAYED" or t.get("actual_delay_sec", 0) > 0]
        ml_flagged = [t for t in all_trains if t.get("is_delayed_prediction", False)]
        avg_delay = (
            sum(t["actual_delay_sec"] for t in active) / len(active)
            if active else 0
        )

        sched = self._active_schedule()
        occ_blocks = 0
        if sched:
            for s in sched.slots:
                if s.entry_time <= t_now < s.exit_time:
                    occ_blocks += 1

        saved = max(self._fifo_objective - self._ai_objective, 0.0)

        queued_trains = len([t for t in all_trains if t["status"] == "WAITING" and not t.get("current_block")])
        # Wait, if current_block is set to next_slot.section_id when WAITING, let's just count all WAITING trains.
        queued_trains = len([t for t in all_trains if t["status"] == "WAITING"])

        return {
            "time":         self.sim_time,
            "mode":         self.mode,
            "is_running":   self.is_running,
            "speed":        self.simulation_speed,
            "trains":       all_trains,
            "route_order":  ROUTE_ORDER,
            "track_types":  TRACK_TYPE,
            "stations":     {k: list(v) for k, v in STATIONS.items()},
            "interventions": self.interventions[:15],
            "metrics": {
                "active_trains":         len(active),
                "delayed_trains":        len(delayed),
                "queued_trains":         queued_trains,
                "ml_flagged_trains":     len(ml_flagged),
                "avg_delay_sec":         round(avg_delay, 1),
                "occupied_blocks":       occ_blocks,
                "manual_weighted_delay": round(self._fifo_objective, 1),
                "ai_weighted_delay":     round(self._ai_objective, 1),
                "delay_saved_min":       round(saved, 1),
                "interventions_count":   len(self.interventions),
            },
        }

    def reset(self, seed: int = None):
        self.is_running       = False
        self.sim_time         = 480.0
        self._min_dep         = 480
        self.interventions    = []
        self.trains_state     = {}
        self._fifo_result     = None
        self._ai_result       = None
        self._train_features  = []
        self._load_and_solve(seed=seed)

    def start(self):
        self.is_running = True

    def pause(self):
        self.is_running = False
