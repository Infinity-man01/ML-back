# ============================================================
# CP-SAT OPTIMIZER — Train Sequencing on a Single-Track Section
# ============================================================
# WHAT THIS SCRIPT DOES:
# Given a few trains that all want to pass through the SAME
# single-track section, this finds the entry/exit time for each
# train that:
#   - never lets two trains occupy the section at the same time
#   - respects minimum safe gaps between trains (headway)
#   - minimizes total weighted delay (higher priority = weighted more)
#
# This is the exact 3-train example we walked through earlier:
# Express (high priority), Freight (low priority), Passenger (mid),
# all converging on one single-track section.
#
# NOTE: predicted_delay_min values below would normally come from
# your predict_delay() function — here they're plugged in directly
# so you can see the optimizer work on its own first.
# ============================================================

from ortools.sat.python import cp_model

# ------------------------------------------------------------
# STEP 1: Define the trains and what we know about them
# ------------------------------------------------------------
# "desired_entry" = when the train WANTS to enter the section
#                   (its scheduled/timetable-driven time, in minutes
#                   from some reference point, e.g. 08:00 = minute 0)
# "predicted_delay" = extra minutes late it's already running,
#                      from your ML model's predict_delay() output
# "duration" = how long the train takes to cross the section
# "priority" = 1 (highest, e.g. Express) to 3 (lowest, e.g. Freight)

trains = [
    {"id": "12045_Express",  "desired_entry": 0,  "predicted_delay": 2,  "duration": 6, "priority": 1},
    {"id": "14205_Passenger","desired_entry": 3,  "predicted_delay": 1,  "duration": 5, "priority": 2},
    {"id": "FR221_Freight",  "desired_entry": 2,  "predicted_delay": 9,  "duration": 8, "priority": 3},
]

MIN_HEADWAY = 2          # minimum safety gap (minutes) between one train leaving and the next entering
HORIZON = 60              # how far into the future (minutes) we're planning — just needs to be "big enough"

# ------------------------------------------------------------
# STEP 2: Create the CP-SAT model
# ------------------------------------------------------------
# Think of "model" as an empty rulebook we're about to fill in
# with variables (unknowns) and constraints (rules they must obey).

model = cp_model.CpModel()

# ------------------------------------------------------------
# STEP 3: Create variables — one entry time & exit time per train
# ------------------------------------------------------------
# These are the UNKNOWNS the solver will figure out for us.
# NewIntVar(min, max, name) means "a whole number between min and max"

entry_vars = {}
exit_vars = {}
interval_vars = {}

for t in trains:
    # A train can't enter before it's realistically ready
    # (desired time + any predicted delay already accumulated)
    earliest_possible = t["desired_entry"] + t["predicted_delay"]

    entry = model.NewIntVar(earliest_possible, HORIZON, f"entry_{t['id']}")
    exit_ = model.NewIntVar(earliest_possible, HORIZON, f"exit_{t['id']}")

    # exit must be exactly "duration" minutes after entry
    model.Add(exit_ == entry + t["duration"])

    # An "interval variable" bundles start/end together — CP-SAT
    # uses these directly in the no-overlap rule in Step 4
    interval = model.NewIntervalVar(entry, t["duration"], exit_, f"interval_{t['id']}")

    entry_vars[t["id"]] = entry
    exit_vars[t["id"]] = exit_
    interval_vars[t["id"]] = interval

# ------------------------------------------------------------
# STEP 4: THE CORE SAFETY CONSTRAINT — no two trains overlap
# ------------------------------------------------------------
# Since it's a SINGLE track, only one train can be "in" the
# section at any moment. NoOverlap() is a built-in CP-SAT rule
# that guarantees none of these intervals ever overlap in time.

model.AddNoOverlap(list(interval_vars.values()))

# ------------------------------------------------------------
# STEP 5: Minimum headway between trains (extra safety buffer)
# ------------------------------------------------------------
# NoOverlap alone allows one train to enter the INSTANT the
# previous one exits. In reality we want a small safety gap.
# We add this by treating each train's "true" occupied window
# as duration + headway, then only using the real duration for
# reporting. Simplest way: pad the interval itself.

# (Re-doing intervals with headway padding baked in)
interval_vars_padded = {}
for t in trains:
    entry = entry_vars[t["id"]]
    padded_duration = t["duration"] + MIN_HEADWAY
    padded_interval = model.NewIntervalVar(entry, padded_duration, entry + padded_duration, f"padded_{t['id']}")
    interval_vars_padded[t["id"]] = padded_interval

model.AddNoOverlap(list(interval_vars_padded.values()))

# ------------------------------------------------------------
# STEP 6: Objective — minimize total weighted delay
# ------------------------------------------------------------
# "Delay" for each train = how much later than its desired_entry
# it actually ends up entering. We weight this by priority, so
# delaying an Express train "costs" more than delaying Freight.
# priority 1 (Express) -> weight 3 (costs the most to delay)
# priority 3 (Freight) -> weight 1 (cheapest to delay)

priority_weight = {1: 3, 2: 2, 3: 1}

delay_terms = []
for t in trains:
    actual_entry = entry_vars[t["id"]]
    delay = model.NewIntVar(0, HORIZON, f"delay_{t['id']}")
    model.Add(delay == actual_entry - t["desired_entry"])
    weight = priority_weight[t["priority"]]
    delay_terms.append(delay * weight)

model.Minimize(sum(delay_terms))

# ------------------------------------------------------------
# STEP 7: Solve it
# ------------------------------------------------------------
solver = cp_model.CpSolver()
status = solver.Solve(model)

# ------------------------------------------------------------
# STEP 8: Print the results in a readable way
# ------------------------------------------------------------
if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    print(f"Solution status: {'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'}\n")
    print(f"{'Train':<18}{'Wanted':<10}{'Entry':<10}{'Exit':<10}{'Delay':<10}")
    results = []
    for t in trains:
        entry_val = solver.Value(entry_vars[t["id"]])
        exit_val = solver.Value(exit_vars[t["id"]])
        delay_val = entry_val - t["desired_entry"]
        results.append((t["id"], t["desired_entry"], entry_val, exit_val, delay_val))
        print(f"{t['id']:<18}{t['desired_entry']:<10}{entry_val:<10}{exit_val:<10}{delay_val:<10}")

    total_weighted_delay = solver.ObjectiveValue()
    print(f"\nTotal weighted delay (the objective): {total_weighted_delay}")

    # Sort by entry time to show the actual PASSING ORDER decided by the solver
    order = sorted(results, key=lambda r: r[2])
    print("\nOptimal passing order:")
    for i, r in enumerate(order, start=1):
        print(f"  {i}. {r[0]} (enters at minute {r[2]})")
else:
    print("No feasible solution found — check constraints (headway/horizon may be too tight).")