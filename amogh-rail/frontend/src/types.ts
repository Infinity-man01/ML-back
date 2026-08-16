export interface Train {
  id: string;
  train_type: string;
  route?: string[];
  priority: number;
  current_block: string | null;
  status: "ON TIME" | "WAITING" | "DELAYED" | "COMPLETED";
  actual_delay_sec: number;
  dataset_delay_min: number;
  predicted_delay_min: number;
  is_delayed_prediction: boolean;
  delay_probability_pct: number;
  prediction_error_min: number;
  reasoning: string[];
  progress: number;
  lat: number;
  lng: number;
  track_type?: string;
  weather_flag?: number;
  upstream_delay_min?: number;
  held_min?: number;
  entry_time?: number;
  exit_time?: number;
  fifo_entry_time?: number;
  disrupted?: boolean;
}

export interface Intervention {
  type?: "action" | "prediction";
  text?: string;
  sim_time?: number;
  time?: number;
  block?: string;
  ai_train?: string;
  ai_type?: string;
  ai_pred_delay?: number;
  manual_train?: string;
  manual_type?: string;
  delay_saved: number;
  reasoning?: string[];
  train_id?: string;
}

export interface SimulationMetrics {
  active_trains: number;
  delayed_trains: number;
  queued_trains?: number;
  ml_flagged_trains: number;
  avg_delay_sec: number;
  occupied_blocks: number;
  ai_weighted_delay: number;
  manual_weighted_delay: number;
  delay_saved_min: number;
  interventions_count: number;
}

export interface SimulationState {
  time: number;
  trains: Train[];
  metrics: SimulationMetrics;
  mode: string;
  interventions: Intervention[];
  is_running: boolean;
  speed: number;
  route_order?: string[];
  track_types?: Record<string, string>;
  stations?: Record<string, [number, number]>;
}
