"""
main.py  —  Amogh Rail FastAPI backend
"""
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys, io
from rich.console import Console
from simulation import RailwaySimulation
from schedule_engine import compute_schedule
from Predictor import predict_delay

console = Console(file=io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdout, 'buffer') else sys.stdout)
console.print("[bold green]AMOGH RAIL — FastAPI backend starting…[/bold green]")

app = FastAPI(title="Amogh Rail", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

sim = RailwaySimulation()


# ── Pydantic models ────────────────────────────────────────────────────────────

class SpeedUpdate(BaseModel):
    speed: float

class ModeUpdate(BaseModel):
    mode: str

class DisruptionRequest(BaseModel):
    train_id: str
    upstream_delay_min: float = 15.0
    weather_flag: int = 1           # 0=Clear,1=Rain,2=Fog

class ScheduleRequest(BaseModel):
    trains: list
    mode: str = "cpsat"

class ResetRequest(BaseModel):
    seed: Optional[int] = None


# ── Simulation control endpoints ───────────────────────────────────────────────

@app.post("/simulation/start")
def start_simulation():
    sim.start()
    return {"status": "started"}

@app.post("/simulation/pause")
def pause_simulation():
    sim.pause()
    return {"status": "paused"}

@app.post("/simulation/reset")
def reset_simulation(req: ResetRequest = ResetRequest()):
    sim.reset(seed=req.seed)
    return {"status": "reset"}

@app.post("/simulation/speed")
def set_speed(update: SpeedUpdate):
    sim.simulation_speed = update.speed
    return {"status": "speed_updated", "speed": sim.simulation_speed}

@app.post("/simulation/mode")
def set_mode(update: ModeUpdate):
    if update.mode in ("manual", "ai"):
        sim.mode = update.mode
        return {"status": "mode_updated", "mode": sim.mode}
    return {"status": "error", "message": "mode must be 'manual' or 'ai'"}


# ── Schedule endpoint ──────────────────────────────────────────────────────────

@app.post("/schedule")
def schedule(req: ScheduleRequest):
    """
    Run ML predictions + scheduling for an arbitrary list of train feature dicts.
    Returns per-train entry/exit times and the total weighted-delay objective.
    """
    enriched = []
    for t in req.trains:
        try:
            pred = predict_delay(
                train_type               = t.get("train_type", "Passenger"),
                priority                 = t.get("priority", 2),
                section_id               = t.get("section_id", "HWH-BLY"),
                day_of_week              = t.get("day_of_week", 1),
                is_weekend               = t.get("is_weekend", 0),
                time_of_day_bucket       = t.get("time_of_day_bucket", "Peak"),
                season                   = t.get("season", "Summer"),
                upstream_delay_min       = float(t.get("upstream_delay_min", 0)),
                section_congestion_level = float(t.get("section_congestion_level", 0.5)),
                weather_flag             = int(t.get("weather_flag", 0)),
                track_type               = t.get("track_type", "Single"),
            )
            t["predicted_delay_min"] = pred["predicted_delay_min"]
        except Exception:
            t["predicted_delay_min"] = 0.0
        enriched.append(t)

    result = compute_schedule(enriched, mode=req.mode)
    return {
        "mode":          result.mode,
        "objective":     result.objective,
        "interventions": result.interventions,
        "slots": [
            {
                "train_id":           s.train_id,
                "section_id":         s.section_id,
                "entry_time":         s.entry_time,
                "exit_time":          s.exit_time,
                "predicted_delay_min": s.predicted_delay_min,
                "fifo_entry_time":    s.fifo_entry_time,
                "held_min":           s.held_min,
            }
            for s in result.slots
        ],
    }


# ── Disruption injection ───────────────────────────────────────────────────────

@app.post("/disruption")
def inject_disruption(req: DisruptionRequest):
    """
    Update a running train's conditions and re-solve the schedule live.
    """
    sim.apply_disruption(
        train_id           = req.train_id,
        upstream_delay_min = req.upstream_delay_min,
        weather_flag       = req.weather_flag,
    )
    console.print(
        f"[bold yellow]⚡ Disruption injected:[/bold yellow] "
        f"{req.train_id} delay={req.upstream_delay_min}m "
        f"weather={req.weather_flag}"
    )
    return {
        "status":                "rescheduled",
        "train_id":              req.train_id,
        "fifo_objective":        round(sim._fifo_objective, 2),
        "ai_objective":          round(sim._ai_objective, 2),
        "delay_saved":           round(sim._fifo_objective - sim._ai_objective, 2),
        "new_interventions":     sim.interventions[:5],
    }


# ── Simulation loop ────────────────────────────────────────────────────────────

async def simulation_loop():
    while True:
        if sim.is_running:
            # Advance by (speed * 0.1) sim-minutes per 100ms tick
            sim.step(sim.simulation_speed * 0.1)
        await asyncio.sleep(0.1)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation_loop())
    console.print("[bold green]✓ Simulation loop started. Backend ready.[/bold green]")


# ── WebSocket state stream ─────────────────────────────────────────────────────

@app.websocket("/ws/state")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            state = sim.get_state()
            await websocket.send_json(state)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        console.print("[dim]WebSocket client disconnected.[/dim]")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
