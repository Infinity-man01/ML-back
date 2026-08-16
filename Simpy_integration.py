# ============================================================
# SimPy simulation + VISUAL Gantt chart output
# ============================================================
# WHAT THIS ADDS vs the earlier console-only version:
# Instead of just printing "[t=17] FR221 ENTERS section" to the
# terminal, this version RECORDS every entry/exit event, then
# draws a proper Gantt chart at the end using matplotlib — the
# same visual style as your dashboard mockup, but generated from
# a REAL simulation run instead of hand-drawn CSS bars.
#
# This is what you'd screenshot (or show live) to prove the
# simulator + optimizer are actually working together, not just
# printing plausible-looking text.
# ============================================================

import simpy
from ortools.sat.python import cp_model
import matplotlib.pyplot as plt

MIN_HEADWAY = 2
HORIZON = 200
priority_weight = {1: 3, 2: 2, 3: 1}

# This list collects every train's actual entry/exit time as the
# simulation runs — it's what we'll plot at the end.
simulation_log = []


# ------------------------------------------------------------
# PART 1: The optimizer (same as before, unchanged logic)
# ------------------------------------------------------------
def compute_optimal_schedule(trains, current_time):
    model = cp_model.CpModel()
    entry_vars, exit_vars, padded_intervals = {}, {}, {}

    for t in trains:
        earliest = max(current_time, t["desired_entry"] + t["predicted_delay"])
        entry = model.NewIntVar(earliest, HORIZON, f"entry_{t['id']}")
        exit_ = model.NewIntVar(earliest, HORIZON, f"exit_{t['id']}")
        model.Add(exit_ == entry + t["duration"])
        padded = model.NewIntervalVar(
            entry, t["duration"] + MIN_HEADWAY, entry + t["duration"] + MIN_HEADWAY,
            f"padded_{t['id']}"
        )
        entry_vars[t["id"]] = entry
        exit_vars[t["id"]] = exit_
        padded_intervals[t["id"]] = padded

    model.AddNoOverlap(list(padded_intervals.values()))

    delay_terms = []
    for t in trains:
        delay = model.NewIntVar(0, HORIZON, f"delay_{t['id']}")
        model.Add(delay == entry_vars[t["id"]] - t["desired_entry"])
        delay_terms.append(delay * priority_weight[t["priority"]])
    model.Minimize(sum(delay_terms))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    return {
        t["id"]: {"entry": solver.Value(entry_vars[t["id"]]), "exit": solver.Value(exit_vars[t["id"]])}
        for t in trains
    }


# ------------------------------------------------------------
# PART 2: SimPy processes (same structure, now with logging)
# ------------------------------------------------------------
def train_generator(env, pending_trains):
    schedule_of_trains = [
        (0, {"id": "12045_Express", "type": "Express", "desired_entry": 0, "predicted_delay": 2, "duration": 6, "priority": 1}),
        (1, {"id": "FR221_Freight", "type": "Freight", "desired_entry": 2, "predicted_delay": 9, "duration": 8, "priority": 3}),
        (2, {"id": "14205_Passenger", "type": "Passenger", "desired_entry": 3, "predicted_delay": 1, "duration": 5, "priority": 2}),
    ]
    for arrival_time, train in schedule_of_trains:
        yield env.timeout(arrival_time - env.now if arrival_time > env.now else 0)
        print(f"[t={env.now}] New train arrives needing scheduling: {train['id']}")
        pending_trains.append(train)


def section_controller(env, pending_trains, section_resource):
    scheduled_ids = set()
    while True:
        yield env.timeout(1)
        unscheduled = [t for t in pending_trains if t["id"] not in scheduled_ids]
        if not unscheduled:
            continue

        print(f"\n[t={env.now}] Calling CP-SAT optimizer for {len(unscheduled)} train(s)...")
        schedule = compute_optimal_schedule(unscheduled, current_time=env.now)
        if schedule is None:
            print(f"[t={env.now}] No feasible schedule found.")
            continue

        for train in unscheduled:
            scheduled_ids.add(train["id"])
            env.process(run_train(env, train, schedule[train["id"]], section_resource))


def run_train(env, train, plan, section_resource):
    wait_time = max(0, plan["entry"] - env.now)
    yield env.timeout(wait_time)

    with section_resource.request() as req:
        yield req
        print(f"[t={env.now}] {train['id']} ENTERS section (planned entry: {plan['entry']})")
        yield env.timeout(plan["exit"] - plan["entry"])
        print(f"[t={env.now}] {train['id']} EXITS section (planned exit: {plan['exit']})")

        # THIS is the new part — log the actual event for plotting later
        simulation_log.append({
            "id": train["id"],
            "type": train["type"],
            "entry": plan["entry"],
            "exit": plan["exit"],
        })


# ------------------------------------------------------------
# PART 3: Run the simulation
# ------------------------------------------------------------
env = simpy.Environment()
section_resource = simpy.Resource(env, capacity=1)
pending_trains = []

env.process(train_generator(env, pending_trains))
env.process(section_controller(env, pending_trains, section_resource))
env.run(until=40)


# ------------------------------------------------------------
# PART 4: Draw the Gantt chart from the recorded log
# ------------------------------------------------------------
color_map = {
    "Express": "#4fa8ff",
    "Passenger": "#3ddc84",
    "Freight": "#f5a623",
    "Suburban": "#c77dff",
}

# Sort by entry time so the chart reads top-to-bottom in passing order
simulation_log.sort(key=lambda e: e["entry"])

fig, ax = plt.subplots(figsize=(10, 4))
fig.patch.set_facecolor("#0a0e14")
ax.set_facecolor("#0a0e14")

for i, e in enumerate(simulation_log):
    ax.barh(
        i, e["exit"] - e["entry"], left=e["entry"], height=0.5,
        color=color_map.get(e["type"], "#999999"), edgecolor="white", linewidth=0.5
    )
    ax.text(e["entry"] - 0.3, i, e["id"], va="center", ha="right",
            fontsize=9, color="white")

ax.set_yticks([])
ax.set_xlabel("Simulated time (minutes)", color="white")
ax.set_title("Section Occupancy — Live Simulation Result", color="white", fontsize=13)
ax.tick_params(colors="white")
for spine in ax.spines.values():
    spine.set_color("#444444")

# Legend
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in color_map.values()]
ax.legend(handles, color_map.keys(), loc="upper right", facecolor="#10151f",
          labelcolor="white", edgecolor="#444444")

plt.tight_layout()
plt.savefig("section_gantt_output.png", dpi=150, facecolor=fig.get_facecolor())
print("\nSaved visual output as section_gantt_output.png — open it to see the result!")
plt.show()