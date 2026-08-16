import React from "react";
import type { SimulationMetrics, Intervention } from "../types";

interface Props {
  mode: string;
  metrics: SimulationMetrics;
  interventions: Intervention[];
  isRunning: boolean;
  onModeChange: (mode: string) => void;
}

export const SolutionPanel: React.FC<Props> = ({
  mode,
  metrics,
  interventions,
  isRunning,
  onModeChange,
}) => {
  const manualDelay = metrics.manual_weighted_delay ?? 0;
  const aiDelay = metrics.ai_weighted_delay ?? 0;
  
  const latestIntervention = interventions.length > 0 ? interventions[interventions.length - 1] : null;

  return (
    <div
      className={`flex flex-col h-full bg-[#0d1b2a] border-r-2 text-[#f2ede3] font-rail-sans overflow-hidden transition-all duration-500 ${mode === 'ai' ? 'border-[#2e7d32] shadow-[2px_0_20px_rgba(46,125,50,0.2)]' : 'border-[#5b7c99]'}`}
    >
      {/* Header */}
      <div className="bg-[#1a334d] px-5 py-3 border-b border-[#5b7c99] shrink-0">
        <div className="font-bold text-lg tracking-widest uppercase text-[#f2ede3]">
          Section Logbook
        </div>
      </div>

      {/* Mode Toggle */}
      <div className="p-5 border-b border-[#5b7c99] shrink-0">
        <div className="text-xs text-[#5b7c99] font-bold mb-3 tracking-widest uppercase">
          Dispatch Mode
        </div>
        <div className="grid grid-cols-2 gap-0 border border-[#5b7c99]">
          <button
            onClick={() => onModeChange("manual")}
            className={`py-3 text-sm font-bold uppercase tracking-widest transition-colors ${
              mode === "manual"
                ? "bg-[#c0392b] text-[#f2ede3]"
                : "bg-transparent text-[#5b7c99] hover:bg-[#1a334d]"
            }`}
          >
            Baseline
          </button>
          <button
            onClick={() => onModeChange("ai")}
            className={`py-3 text-sm font-bold uppercase tracking-widest transition-colors border-l border-[#5b7c99] ${
              mode === "ai"
                ? "bg-[#2e7d32] text-[#f2ede3]"
                : "bg-transparent text-[#5b7c99] hover:bg-[#1a334d]"
            }`}
          >
            AI-Assisted
          </button>
        </div>
      </div>

      {/* Comparison Section */}
      <div className="p-5 border-b border-[#5b7c99] shrink-0">
        <div className="text-xs text-[#5b7c99] font-bold mb-3 tracking-widest uppercase">
          Weighted Delay (Σ Priority × Delay)
        </div>
        
        <div className="flex flex-col gap-2">
          {/* Manual row */}
          <div className="flex justify-between items-center py-2 border-b border-[#1a334d]">
            <span className="text-sm font-bold uppercase tracking-wider text-[#c0392b]">
              Baseline (FIFO)
            </span>
            <span className="text-lg font-bold font-rail-mono text-[#f2ede3]">
              {manualDelay.toFixed(1)}
            </span>
          </div>
          
          {/* AI row */}
          <div className="flex justify-between items-center py-2 border-b border-[#1a334d]">
            <span className="text-sm font-bold uppercase tracking-wider text-[#2e7d32]">
              Optimized (CP-SAT)
            </span>
            <span className="text-lg font-bold font-rail-mono text-[#f2ede3]">
              {aiDelay.toFixed(1)}
            </span>
          </div>

          {/* Queued row */}
          <div className="flex justify-between items-center py-2">
            <span className="text-sm font-bold uppercase tracking-wider text-[#e8a33d]">
              Trains Queued
            </span>
            <span className="text-lg font-bold font-rail-mono text-[#f2ede3]">
              {metrics.queued_trains ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Auto-scrolling Section Logbook */}
      <div className="p-5 flex-1 flex flex-col min-h-0 bg-[#0d1b2a]">
        <div className="text-xs text-[#5b7c99] font-bold mb-3 tracking-widest uppercase shrink-0">
          Reasoning & Dispatch Actions
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
          {interventions.length === 0 ? (
            <div className="py-4 text-[#5b7c99] text-sm uppercase tracking-wider">
              {mode === "ai"
                ? isRunning ? "Monitoring section..." : "Awaiting simulation start"
                : "Manual mode active"}
            </div>
          ) : (
            interventions.map((iv, i) => (
              <div key={i} className={`py-2 px-3 border-l-2 flex flex-col ${iv.type === 'prediction' ? 'border-[#e8a33d] bg-[#08111a]/70' : 'border-[#2e7d32] bg-[#08111a]'}`}>
                <div className="flex items-start gap-2">
                  <div className={`font-bold mt-1 shrink-0 px-1 py-0.5 rounded-sm ${mode === 'ai' ? 'text-[10px]' : 'text-[9px]'} ${iv.type === 'prediction' ? 'bg-[#e8a33d]/20 text-[#e8a33d]' : 'bg-[#2e7d32]/20 text-[#2e7d32]'}`}>
                    {iv.type === 'prediction' ? 'ML PRED' : 'CP-SAT'}
                  </div>
                  <div className={`font-rail-mono leading-relaxed tracking-wide ${mode === 'ai' ? 'text-sm' : 'text-xs'} ${iv.type === 'prediction' ? 'text-[#a3b8cc]' : 'text-[#f2ede3]'}`}>
                    {iv.text}
                  </div>
                </div>
                {(iv.delay_saved ?? 0) > 0 && iv.type === 'action' && (
                  <div className={`mt-2 ml-[52px] font-bold uppercase tracking-widest font-rail-mono text-[#2e7d32] ${mode === 'ai' ? 'text-xs' : 'text-[10px]'}`}>
                    - {iv.delay_saved.toFixed(1)} MIN AVOIDED
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
