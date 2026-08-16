import pandas as pd
import joblib

_reg_pipeline = None
_clf_pipeline = None
_delay_threshold = None

def _load_models():
    """
    Lazy loader for models. Ensures files are only read from disk
    the first time a prediction is made, preventing crashes on import.
    """
    global _reg_pipeline, _clf_pipeline, _delay_threshold

    if _reg_pipeline is None:
        _reg_pipeline = joblib.load("delay_model_pipeline.pkl")
    if _clf_pipeline is None:
        _clf_pipeline = joblib.load("delay_classifier_pipeline.pkl")
    if _delay_threshold is None:
        _delay_threshold = joblib.load("delay_threshold.pkl")


def predict_delay(*, train_type, priority, section_id, day_of_week, is_weekend,
                   time_of_day_bucket, season, upstream_delay_min,
                   section_congestion_level, weather_flag, track_type):
    """
    Takes live train info and returns a prediction.
    The '*' in the signature forces all arguments to be passed as keywords.
    """

    _load_models()

    input_row = pd.DataFrame([{
        "train_type": train_type,
        "priority": priority,
        "section_id": section_id,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "time_of_day_bucket": time_of_day_bucket,
        "season": season,
        "upstream_delay_min": upstream_delay_min,
        "section_congestion_level": section_congestion_level,
        "weather_flag": weather_flag,
        "track_type": track_type,
    }])

    predicted_minutes = round(float(_reg_pipeline.predict(input_row)[0]), 1)
    prob_delayed = float(_clf_pipeline.predict_proba(input_row)[0][1])

    # Generate explainable reasoning for the demonstration
    reasoning = []
    
    if weather_flag == 1:
        reasoning.append("Monsoon rain impacts track friction (+ delay)")
    elif weather_flag == 2:
        reasoning.append("Fog/Winter visibility reduces safe speed limit (+ delay)")
        
    if section_congestion_level > 0.6:
        reasoning.append(f"High network congestion ({int(section_congestion_level*100)}% capacity) on {section_id}")
    elif section_congestion_level > 0.4:
        reasoning.append(f"Moderate congestion on {section_id}")
        
    if upstream_delay_min > 5:
        reasoning.append(f"Cascading upstream delay ({upstream_delay_min} min)")
        
    if priority == 3:
        reasoning.append("Freight priority (subject to passenger train overtaking)")
        
    if not reasoning:
        reasoning.append("Optimal conditions, normal operations expected.")

    return {
        "predicted_delay_min": predicted_minutes,
        "is_delayed": prob_delayed >= 0.5,
        "delay_probability_pct": round(prob_delayed * 100, 1),
        "threshold_used_min": _delay_threshold,
        "reasoning": reasoning
    }


if __name__ == "__main__":
    print("=== TEST 1: Freight train, foggy winter night, already delayed ===")
    print(predict_delay(
        train_type="Freight", priority=3, section_id="SHE-SKG",
        day_of_week=3, is_weekend=0, time_of_day_bucket="Night",
        season="Winter", upstream_delay_min=14.0,
        section_congestion_level=0.75, weather_flag=2, track_type="Single"
    ))

    print("\n=== TEST 2: Express train, clear day, on schedule so far ===")
    print(predict_delay(
        train_type="Express", priority=1, section_id="HWH-BLY",
        day_of_week=2, is_weekend=0, time_of_day_bucket="Off-peak",
        season="Summer", upstream_delay_min=1.0,
        section_congestion_level=0.2, weather_flag=0, track_type="Double"
    ))

    print("\n=== TEST 3: Suburban local, peak hour, monsoon rain ===")
    print(predict_delay(
        train_type="Suburban", priority=2, section_id="BLY-BDC",
        day_of_week=5, is_weekend=0, time_of_day_bucket="Peak",
        season="Monsoon", upstream_delay_min=5.0,
        section_congestion_level=0.6, weather_flag=1, track_type="Double"
    ))

    print("\n=== TEST 4: Unknown/new section_id (robustness check) ===")
    print(predict_delay(
        train_type="Express", priority=1, section_id="PAN-DBG",
        day_of_week=4, is_weekend=0, time_of_day_bucket="Peak",
        season="Winter", upstream_delay_min=3.0,
        section_congestion_level=0.4, weather_flag=2, track_type="Single"
    ))