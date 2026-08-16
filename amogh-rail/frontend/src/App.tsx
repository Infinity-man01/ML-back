import React, { useEffect, useState, useRef } from "react";
import { RailwayMap, STATIONS_GEO } from "./components/Map";
import { ControlPanel } from "./components/ControlPanel";
import { LiveDashboard } from "./components/LiveDashboard";
import { SolutionPanel } from "./components/SolutionPanel";
import { SplitFlapDisplay } from "./components/SplitFlap";
import type { SimulationState } from "./types";
import { Info, ShieldCheck, X } from "lucide-react";

function App() {
  const [state, setState] = useState<SimulationState>({
    time: 0,
    trains: [],
    mode: "manual",
    interventions: [],
    metrics: {
      active_trains: 0,
      delayed_trains: 0,
      ml_flagged_trains: 0,
      avg_delay_sec: 0,
      occupied_blocks: 0,
      ai_weighted_delay: 0,
      manual_weighted_delay: 0,
      delay_saved_min: 0,
      interventions_count: 0,
    },
    is_running: false,
    speed: 1.0,
  });

  const [toast, setToast] = useState<string | null>(null);
  const [infoOpen, setInfoOpen] = useState(false);
  const ws = useRef<WebSocket | null>(null);

  // Demo sequence state
  const [demoState, setDemoState] = useState<"idle" | "running" | "summary">("idle");
  const [demoPhase, setDemoPhase] = useState<number>(0);
  const demoTimer = useRef<NodeJS.Timeout | null>(null);
  const disruptionTarget = useRef({ trainId: "FR301", delay: 25, weather: 2 });
  const [caption, setCaption] = useState<string | null>(null);
  const [hasShownCongestion, setHasShownCongestion] = useState(false);
  const lastInterventionRef = useRef<number>(0);

  const post = (path: string, body?: object) =>
    fetch(`http://localhost:8000${path}`, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }).catch(console.error);

  useEffect(() => {
    const connectWs = () => {
      ws.current = new WebSocket("ws://localhost:8000/ws/state");
      ws.current.onmessage = (event) => {
        try {
          const data: SimulationState = JSON.parse(event.data);
          setState(data);
        } catch (e) {
          console.error("Failed to parse websocket message", e);
        }
      };
      ws.current.onclose = () => {
        setTimeout(connectWs, 2000);
      };
    };
    connectWs();
    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  const saved = state.metrics.delay_saved_min ?? 0;
  const manualDelay = state.metrics.manual_weighted_delay ?? 0;

  const [displaySaved, setDisplaySaved] = useState<number>(0);
  
  useEffect(() => {
    if (saved === 0) {
      setDisplaySaved(0);
      return;
    }
    
    // Animate the split flap by taking steps every 120ms
    const stepSize = Math.max(1.0, saved / 10);
    const interval = setInterval(() => {
      setDisplaySaved(prev => {
        const next = prev + stepSize;
        if (next >= saved) {
          clearInterval(interval);
          return saved;
        }
        return next;
      });
    }, 120);

    return () => clearInterval(interval);
  }, [saved]);

  const handleStart = () => post("/simulation/start");
  const handlePause = () => post("/simulation/pause");
  const handleReset = () => post("/simulation/reset");
  const handleSpeedChange = (s: number) => post("/simulation/speed", { speed: s });
  const handleModeChange = (mode: string) => post("/simulation/mode", { mode });

  const handleDisruption = async (trainId: string, upstreamDelay: number, weatherFlag: number) => {
    const weatherName = weatherFlag === 2 ? "fog" : weatherFlag === 1 ? "rain" : "clear";
    setToast(`${trainId} +${upstreamDelay}m delay (${weatherName}) — resequenced`);
    try {
      await post("/disruption", { train_id: trainId, upstream_delay_min: upstreamDelay, weather_flag: weatherFlag });
      setTimeout(() => setToast(null), 4000);
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    if (demoState !== "running") return;

    const t = state.time;

    if (demoPhase === 1 && t >= 495) {
      setDemoPhase(2);
      const { trainId, delay, weather } = disruptionTarget.current;
      handleDisruption(trainId, delay, weather);
    } 
    else if (demoPhase === 2 && t >= 515) {
      setDemoPhase(3);
      post("/simulation/pause");
      setToast("RE-RUNNING IDENTICAL SCENARIO WITH AI-ASSISTED CP-SAT...");
      
      const searchParams = new URLSearchParams(window.location.search);
      const seedParam = searchParams.get("seed");
      const reqBody = seedParam ? { seed: parseInt(seedParam) } : {};

      demoTimer.current = setTimeout(async () => {
        await post("/simulation/reset", reqBody);
        await post("/simulation/mode", { mode: "ai" });
        await post("/simulation/speed", { speed: 1.5 });
        await post("/simulation/start");
        setDemoPhase(4);
      }, 4000);
    }
    else if (demoPhase === 4 && t >= 495) {
      setDemoPhase(5);
      const { trainId, delay, weather } = disruptionTarget.current;
      handleDisruption(trainId, delay, weather);
    }
    else if (demoPhase === 5 && t >= 515) {
      setDemoPhase(6);
      post("/simulation/pause");
      // Summary overlay triggers after caption 6 finishes
    }

  }, [state.time, demoState, demoPhase]);

  // Narrative Captions Logic
  useEffect(() => {
    if (demoPhase === 1) {
      setCaption("PHASE 1: MANUAL DISPATCH (FIFO) — No delay prediction, no resequencing");
      setTimeout(() => setCaption(null), 4000);
      setHasShownCongestion(false);
    } else if (demoPhase === 3) {
      setCaption(`BASELINE RESULT: ${manualDelay.toFixed(1)} min-wt total delay — congestion went unmanaged`);
      setTimeout(() => setCaption(null), 4000);
    } else if (demoPhase === 4) {
      setCaption("PHASE 2: AI-ASSISTED (CP-SAT + ML) — Same trains, same disruptions, now optimized");
      setTimeout(() => setCaption(null), 4000);
      lastInterventionRef.current = 0;
    } else if (demoPhase === 6) {
      const saved = state.metrics.delay_saved_min ?? 0;
      const improvement = manualDelay > 0 ? (saved / manualDelay) * 100 : 0;
      setCaption(`AI RESULT: ${state.metrics.ai_weighted_delay?.toFixed(1)} min-wt total delay — ${improvement.toFixed(1)}% less than baseline`);
      setTimeout(() => {
        setCaption(null);
        setDemoState("summary");
      }, 4000);
    }
  }, [demoPhase]);

  // Congestion forming detection (Phase 1)
  useEffect(() => {
    if (demoPhase === 1 && demoState === 'running' && !hasShownCongestion) {
      const stationCounts: Record<string, { count: number, name: string }> = {};
      state.trains.filter(t => t.status === 'WAITING').forEach(t => {
        // Find nearest station
        let nearestStation = "Unknown";
        for (const [code, sta] of Object.entries(STATIONS_GEO)) {
          if (Math.abs(t.lat - sta.pos[0]) < 0.01 && Math.abs(t.lng - sta.pos[1]) < 0.01) {
            nearestStation = sta.name.split(' ')[0]; // e.g. "Barddhaman"
            break;
          }
        }
        stationCounts[nearestStation] = {
          count: (stationCounts[nearestStation]?.count || 0) + 1,
          name: nearestStation
        };
      });
      
      const congested = Object.values(stationCounts).find(c => c.count >= 2);
      if (congested) {
        setCaption(`CONGESTION FORMING at ${congested.name} — ${congested.count} trains queued, no intervention`);
        setHasShownCongestion(true);
        setTimeout(() => setCaption(null), 4000);
      }
    }
  }, [state.trains, demoPhase, demoState, hasShownCongestion]);

  // AI Resequencing detection (Phase 4/5)
  useEffect(() => {
    if ((demoPhase === 4 || demoPhase === 5) && demoState === 'running') {
      if (state.interventions.length > lastInterventionRef.current) {
        const iv = state.interventions[state.interventions.length - 1];
        if (iv.type === 'action' && (iv.delay_saved ?? 0) > 0) {
          setCaption(`AI RESEQUENCING: ${iv.text}`);
          setTimeout(() => setCaption(null), 4000);
        }
        lastInterventionRef.current = state.interventions.length;
      }
    }
  }, [state.interventions, demoPhase, demoState]);

  const runDemoSequence = async () => {
    if (demoTimer.current) clearTimeout(demoTimer.current);
    setDemoState("running");
    setDemoPhase(1);
    
    const searchParams = new URLSearchParams(window.location.search);
    const seedParam = searchParams.get("seed");
    const reqBody = seedParam ? { seed: parseInt(seedParam) } : {};

    const trainList = ["FR301", "FR302", "12042", "34011", "12044", "FR220"];
    const randomTrain = trainList[Math.floor(Math.random() * trainList.length)];
    const randomDelay = Math.floor(Math.random() * 30) + 15;
    const randomWeather = Math.floor(Math.random() * 3);
    disruptionTarget.current = { trainId: randomTrain, delay: randomDelay, weather: randomWeather };
    
    // Step 1: Reset and start in Manual Mode
    await post("/simulation/reset", reqBody);
    await post("/simulation/mode", { mode: "manual" });
    await post("/simulation/speed", { speed: 1.5 });
    await post("/simulation/start");
  };

  const improvement = manualDelay > 0 ? (saved / manualDelay) * 100 : 0;

  return (
    <div className="w-full h-screen flex flex-col overflow-hidden font-rail-sans bg-[#0d1b2a]">
      
      {/* ── MAIN CONTENT AREA (fills all but bottom bar) ── */}
      <div className="flex flex-1 min-h-0">

        {/* ── LEFT PANEL: Section Logbook ── */}
        <div className="w-[260px] shrink-0 flex flex-col overflow-hidden">
          <SolutionPanel
            mode={state.mode}
            metrics={state.metrics}
            interventions={state.interventions}
            isRunning={state.is_running}
            onModeChange={handleModeChange}
          />
        </div>

        {/* ── CENTER: Map + all overlays ── */}
        <div className="flex-1 relative min-w-0 overflow-hidden">
          {/* Map always fullscreen in this column */}
          <RailwayMap trains={state.trains} onDisruption={handleDisruption} />

          {/* Split-flap hero metric: top-center, only in AI mode */}
          <div className={`absolute top-4 left-1/2 -translate-x-1/2 z-[500] transition-all duration-500 ${state.mode === 'ai' ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-2 pointer-events-none'}`}>
            <SplitFlapDisplay value={displaySaved.toFixed(1)} label="DELAY SAVED" />
          </div>

          {/* Narrative captions: below the hero metric or top-center if no hero */}
          {caption && (
            <div className="absolute top-20 left-1/2 -translate-x-1/2 z-[600] w-[90%] max-w-[720px]">
              <div className="bg-[#0d1b2a]/95 border border-[#2e7d32] shadow-[0_8px_24px_rgba(0,0,0,0.6)] px-6 py-3 text-center">
                <p className="text-base font-black text-[#f2ede3] tracking-wide uppercase font-rail-sans leading-snug">
                  {caption}
                </p>
              </div>
            </div>
          )}

          {/* Disruption Toast */}
          {toast && (
            <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-[600] pointer-events-none">
              <div className="bg-[#e8a33d] text-[#0d1b2a] font-bold px-5 py-2.5 border border-[#0d1b2a] text-base shadow-xl uppercase tracking-wider font-rail-mono whitespace-nowrap">
                {toast}
              </div>
            </div>
          )}

          {/* Info button: top-right of center */}
          <div className="absolute top-4 right-4 z-[700]">
            <button 
              onClick={() => setInfoOpen(!infoOpen)}
              className="w-9 h-9 rounded-sm bg-[#0d1b2a]/80 hover:bg-[#1a334d] text-[#f2ede3] border border-[#5b7c99] flex items-center justify-center transition-colors"
            >
              {infoOpen ? <X size={18} /> : <Info size={18} />}
            </button>
          </div>

          {infoOpen && (
            <div className="absolute top-14 right-4 z-[700] w-[300px] bg-[#0d1b2a] border border-[#5b7c99] p-4 text-[#f2ede3] shadow-xl">
              <h3 className="text-sm font-bold flex items-center gap-2 mb-3 border-b border-[#5b7c99] pb-2 uppercase tracking-wider">
                <ShieldCheck size={14} className="text-[#2e7d32]" /> Verified Metrics
              </h3>
              <div className="grid grid-cols-3 gap-2 mb-4 font-rail-mono">
                <div className="bg-[#08111a] border border-[#1a334d] p-2 text-center">
                  <div className="text-[9px] text-[#5b7c99] font-bold mb-1 font-rail-sans tracking-widest">R² SCORE</div>
                  <div className="text-base font-bold text-[#f2ede3]">0.878</div>
                </div>
                <div className="bg-[#08111a] border border-[#1a334d] p-2 text-center">
                  <div className="text-[9px] text-[#5b7c99] font-bold mb-1 font-rail-sans tracking-widest">MAE</div>
                  <div className="text-base font-bold text-[#f2ede3]">1.58m</div>
                </div>
                <div className="bg-[#08111a] border border-[#1a334d] p-2 text-center">
                  <div className="text-[9px] text-[#5b7c99] font-bold mb-1 font-rail-sans tracking-widest">ACCURACY</div>
                  <div className="text-base font-bold text-[#f2ede3]">87.2%</div>
                </div>
              </div>
              <h3 className="text-xs font-bold mb-2 uppercase tracking-wider">Track Legend</h3>
              <div className="space-y-2 text-xs font-medium">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-1 bg-[#5b7c99]"></div>
                  <span>Double Track (HWH–BDC)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-5 h-1 border-t-2 border-dashed border-[#e8a33d]"></div>
                  <span>Single Track Bottleneck</span>
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <div className="w-3 h-3 bg-[#c0392b]"></div>
                  <span>Block Occupied</span>
                </div>
              </div>
            </div>
          )}

          {/* Demo Complete summary: centered in the map area, compact */}
          {demoState === "summary" && (
            <div className="absolute inset-0 z-[800] flex items-end justify-center pb-6 pointer-events-none">
              <div className="pointer-events-auto bg-[#0d1b2a]/96 border-2 border-[#5b7c99] px-8 py-5 shadow-[0_20px_50px_rgba(0,0,0,0.8)] flex items-center gap-8">
                <div>
                  <h2 className="text-base font-black text-[#f2ede3] uppercase tracking-widest border-b border-[#5b7c99] pb-2 mb-3">Demo Complete</h2>
                  <button 
                    onClick={() => { setDemoState("idle"); post("/simulation/reset"); }}
                    className="px-5 py-2 bg-[#f2ede3] text-[#0d1b2a] font-bold text-xs uppercase tracking-widest hover:bg-[#e8a33d] transition-colors"
                  >
                    Reset Console
                  </button>
                </div>
                <div className="flex gap-5 font-rail-mono">
                  <div className="text-center">
                    <div className="text-[#c0392b] font-bold mb-0.5 text-[10px] font-rail-sans uppercase tracking-widest">Baseline</div>
                    <div className="text-2xl font-bold text-[#f2ede3]">{manualDelay.toFixed(1)}</div>
                  </div>
                  <div className="w-px bg-[#5b7c99]"></div>
                  <div className="text-center">
                    <div className="text-[#2e7d32] font-bold mb-0.5 text-[10px] font-rail-sans uppercase tracking-widest">AI Result</div>
                    <div className="text-2xl font-bold text-[#f2ede3]">{state.metrics.ai_weighted_delay.toFixed(1)}</div>
                  </div>
                </div>
                <div className="pl-6 border-l border-[#5b7c99] text-left">
                  <div className="text-3xl font-black text-[#2e7d32] font-rail-mono">{saved.toFixed(1)} MIN</div>
                  <p className="text-xs text-[#f2ede3] font-medium tracking-wide mt-1">
                    SAVED — <strong className="text-[#2e7d32]">{improvement.toFixed(1)}%</strong> reduction
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT PANEL: Live Traffic ── */}
        <div className="w-[220px] shrink-0 flex flex-col overflow-hidden">
          <LiveDashboard metrics={state.metrics} time={state.time} />
        </div>
      </div>

      {/* ── BOTTOM BAR: Controls ── */}
      <div className="shrink-0 border-t-2 border-[#5b7c99] bg-[#0d1b2a]">
        <ControlPanel
          isRunning={state.is_running}
          speed={state.speed}
          onStart={handleStart}
          onPause={handlePause}
          onReset={handleReset}
          onSpeedChange={handleSpeedChange}
          onRunDemo={runDemoSequence}
          demoRunning={demoState === "running"}
        />
      </div>
    </div>
  );
}

export default App;
