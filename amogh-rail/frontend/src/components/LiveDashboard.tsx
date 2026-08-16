import React from 'react';
import type { SimulationMetrics } from '../types';
import { Activity, AlertTriangle, Clock, Layers, ShieldAlert } from 'lucide-react';

interface DashboardProps {
  metrics: SimulationMetrics;
  time: number;
}

export const LiveDashboard: React.FC<DashboardProps> = ({ metrics, time }) => {
  const formatTime = (simMinutes: number) => {
    const totalSeconds = Math.floor(simMinutes * 60);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = Math.floor(totalSeconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col h-full bg-[#0d1b2a] border-l-2 border-[#5b7c99] font-rail-sans">
      <div className="bg-[#1a334d] px-4 py-3 border-b-2 border-[#5b7c99] flex flex-col gap-2 shrink-0">
        <div className="flex justify-between items-center">
          <h2 className="font-bold text-[#f2ede3] tracking-widest text-xs flex items-center gap-2 uppercase">
            <div className="w-2 h-2 rounded-full bg-[#2e7d32] animate-pulse"></div>
            Live Traffic
          </h2>
          <span className="text-xs font-rail-mono bg-[#08111a] px-2 py-0.5 text-[#5b7c99] border border-[#1a334d]">
            {formatTime(time)}
          </span>
        </div>
        
        {/* Scenario Progress */}
        <div className="w-full h-1 bg-[#08111a] relative overflow-hidden">
          <div 
            className="absolute top-0 left-0 h-full bg-[#2e7d32] transition-all duration-300"
            style={{ width: `${Math.min(Math.max((time - 480) / 45, 0) * 100, 100)}%` }}
          />
        </div>
      </div>

      <div className="p-3 grid grid-cols-2 gap-2 bg-[#0d1b2a]">
        {/* Active Trains */}
        <div className="bg-[#08111a] p-2 border border-[#1a334d] flex flex-col">
          <span className="text-[9px] text-[#5b7c99] font-bold mb-1 flex items-center gap-1 uppercase tracking-wider">
            <Activity size={10} className="text-[#5b7c99]" /> Active
          </span>
          <span className="text-lg font-bold font-rail-mono text-[#f2ede3]">{metrics.active_trains}</span>
          <span className="text-[8px] text-[#5b7c99] uppercase tracking-wider">Traversing</span>
        </div>

        {/* Currently Delayed */}
        <div className="bg-[#08111a] p-2 border border-[#1a334d] flex flex-col">
          <span className="text-[9px] text-[#5b7c99] font-bold mb-1 flex items-center gap-1 uppercase tracking-wider">
            <AlertTriangle size={10} className={metrics.delayed_trains > 0 ? "text-[#c0392b]" : "text-[#5b7c99]"} /> Delayed
          </span>
          <span className={`text-lg font-bold font-rail-mono ${metrics.delayed_trains > 0 ? 'text-[#c0392b]' : 'text-[#f2ede3]'}`}>
            {metrics.delayed_trains}
          </span>
          <span className="text-[8px] text-[#5b7c99] uppercase tracking-wider">Held Trains</span>
        </div>

        {/* Avg Delay */}
        <div className="bg-[#08111a] p-2 border border-[#1a334d] flex flex-col">
          <span className="text-[9px] text-[#5b7c99] font-bold mb-1 flex items-center gap-1 uppercase tracking-wider">
            <Clock size={10} className="text-[#e8a33d]" /> Avg Delay
          </span>
          <span className="text-lg font-bold font-rail-mono text-[#e8a33d]">
            {metrics.avg_delay_sec > 0 ? `${(metrics.avg_delay_sec / 60).toFixed(1)}m` : "0.0m"}
          </span>
          <span className="text-[8px] text-[#5b7c99] uppercase tracking-wider">Mean Queue</span>
        </div>

        {/* Occupied Blocks */}
        <div className="bg-[#08111a] p-2 border border-[#1a334d] flex flex-col">
          <span className="text-[9px] text-[#5b7c99] font-bold mb-1 flex items-center gap-1 uppercase tracking-wider">
            <Layers size={10} className="text-[#5b7c99]" /> Blocks
          </span>
          <span className="text-lg font-bold font-rail-mono text-[#f2ede3]">{metrics.occupied_blocks} <span className="text-xs font-normal text-[#5b7c99]">/ 8</span></span>
          <span className="text-[8px] text-[#5b7c99] uppercase tracking-wider">Occupied</span>
        </div>

        {/* ML Flagged */}
        <div className="bg-[#08111a] p-2 border border-[#1a334d] col-span-2 flex items-center justify-between">
          <div>
            <span className="text-[9px] text-[#5b7c99] font-bold flex items-center gap-1 uppercase tracking-wider">
              <ShieldAlert size={10} className="text-[#c0392b]" /> ML Flagged Risk
            </span>
            <span className="text-[8px] text-[#5b7c99] mt-0.5 block uppercase tracking-wider">Delay prob ≥ 50%</span>
          </div>
          <span className={`text-xl font-bold font-rail-mono ${metrics.ml_flagged_trains > 0 ? 'text-[#c0392b]' : 'text-[#f2ede3]'}`}>
            {metrics.ml_flagged_trains}
          </span>
        </div>
      </div>
    </div>
  );
};
