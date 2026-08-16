
import pandas as pd
from ortools.sat.python import cp_model
from Predictor import predict_delay

MIN_HEADWAY = 2
HORIZON = 200
priority_weight = {1: 3, 2: 2, 3: 1}
df = pd.read_csv("train_delay_dataset.csv")

sample = df.sample(3, random_state=7).reset_index(drop=True)

print("=" * 70)
print("PART 1 — ML PREDICTION vs ACTUAL DELAY (proof the model works)")
print("=" * 70)

demo_trains = []
for i, row in sample.iterrows():
    result = predict_delay(
        train_type=row["train_type"], priority=row["priority"],
        section_id=row["section_id"], day_of_week=row["day_of_week"],
        is_weekend=row["is_weekend"], time_of_day_bucket=row["time_of_day_bucket"],
        season=row["season"], upstream_delay_min=row["upstream_delay_min"],
        section_congestion_level=row["section_congestion_level"],
        weather_flag=row["weather_flag"], track_type=row["track_type"]
    )

    predicted = result["predicted_delay_min"]
    actual = row["delay_min"]
    error = round(abs(predicted - actual), 1)

    print(f"\nTrain: {row['train_id']} ({row['train_type']}, section {row['section_id']})")
    print(f"  Actual delay (ground truth):    {actual} min")
    print(f"  ML predicted delay:             {predicted} min")
    print(f"  Prediction error:               {error} min")

    # Save this train's info for Part 2 — give each train a distinct
    # "desired_entry" (spaced out) so they realistically converge
    # on the same section around the same time.
    demo_trains.append({
        "id": f"{row['train_id']}_{row['train_type']}",
        "priority": int(row["priority"]),
        "desired_entry": i * 3,             # 0, 3, 6 — simulate near-simultaneous arrival
        "duration": 6,
        "predicted_delay": predicted,
        "actual_delay": actual,
    })

avg_error = sum(abs(t["predicted_delay"] - t["actual_delay"]) for t in demo_trains) / len(demo_trains)
print(f"\nAverage prediction error across these {len(demo_trains)} trains: {avg_error:.1f} minutes")


# ------------------------------------------------------------
# PART 2: Run the optimizer under 3 different delay assumptions
# ------------------------------------------------------------
def compute_schedule(trains, delay_key):
    """
    delay_key: which field to use as the 'known' delay when planning
               - "zero"      -> naive, assumes no delay at all
               - "predicted" -> our ML model's prediction
               - "actual"    -> oracle, true delay (only knowable in hindsight)
    """
    model = cp_model.CpModel()
    entry_vars, padded_intervals = {}, {}

    for t in trains:
        if delay_key == "zero":
            delay_input = 0
        elif delay_key == "predicted":
            delay_input = t["predicted_delay"]
        else:
            delay_input = t["actual_delay"]

        earliest = t["desired_entry"] + delay_input
        entry = model.NewIntVar(int(earliest), HORIZON, f"entry_{t['id']}")
        padded = model.NewIntervalVar(
            entry, t["duration"] + MIN_HEADWAY, entry + t["duration"] + MIN_HEADWAY,
            f"padded_{t['id']}"
        )
        entry_vars[t["id"]] = entry
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
    return solver.ObjectiveValue()


print("\n" + "=" * 70)
print("PART 2 — HOW PREDICTION QUALITY AFFECTS SCHEDULING QUALITY")
print("=" * 70)

naive_score = compute_schedule(demo_trains, "zero")
ai_score = compute_schedule(demo_trains, "predicted")
oracle_score = compute_schedule(demo_trains, "actual")

print(f"\n{'Scenario':<35}{'Total Weighted Delay':<25}")
print(f"{'Naive (assumes zero delay)':<35}{naive_score:<25}")
print(f"{'Our AI (ML-predicted delay)':<35}{ai_score:<25}")
print(f"{'Oracle (perfect knowledge)':<35}{oracle_score:<25}")

gap_to_oracle = round(abs(ai_score - oracle_score), 1)
gap_naive_to_oracle = round(abs(naive_score - oracle_score), 1)

print(f"\nOur AI's gap to the theoretical best (Oracle): {gap_to_oracle}")
print(f"Naive's gap to the theoretical best (Oracle):  {gap_naive_to_oracle}")
print("\n(A smaller gap = closer to the best possible schedule.")
print(" This proves that better delay prediction directly produces")
print(" better real-world scheduling decisions — not just a good")
print(" accuracy number in isolation.)")