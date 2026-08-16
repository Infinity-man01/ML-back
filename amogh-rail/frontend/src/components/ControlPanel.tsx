import React from 'react';
import { Play, Pause, RotateCcw, FastForward, Presentation } from 'lucide-react';

interface ControlPanelProps {
  isRunning: boolean;
  speed: number;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  onSpeedChange: (speed: number) => void;
  onRunDemo?: () => void;
  demoRunning?: boolean;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  isRunning, speed, onStart, onPause, onReset, onSpeedChange, onRunDemo, demoRunning
}) => {
  return (
    <div className="flex items-center justify-center gap-4 px-4 py-2.5 font-rail-sans">
      {onRunDemo && (
        <div className="flex items-center border-r-2 border-[#5b7c99] pr-4">
          <button
            onClick={onRunDemo}
            disabled={demoRunning}
            className={`flex items-center gap-2 px-5 py-2.5 font-bold transition-colors uppercase tracking-widest ${
              demoRunning 
              ? "bg-[#1a334d] text-[#5b7c99] cursor-not-allowed"
              : "bg-[#5b7c99] hover:bg-[#f2ede3] text-[#0d1b2a]"
            }`}
          >
            <Presentation size={20} />
            {demoRunning ? "Demo Running..." : "Run Demo Sequence"}
          </button>
        </div>
      )}

      <div className="flex items-center gap-2 border-r-2 border-[#5b7c99] pr-4">
        {!isRunning ? (
          <button 
            onClick={onStart}
            className="flex items-center gap-2 bg-[#2e7d32] hover:bg-[#1a5c20] text-[#f2ede3] px-4 py-2.5 transition-colors font-bold uppercase tracking-wider"
          >
            <Play size={18} fill="currentColor" /> Start
          </button>
        ) : (
          <button 
            onClick={onPause}
            className="flex items-center gap-2 bg-[#e8a33d] hover:bg-[#c98628] text-[#0d1b2a] px-4 py-2.5 transition-colors font-bold uppercase tracking-wider"
          >
            <Pause size={18} fill="currentColor" /> Pause
          </button>
        )}
        
        <button 
          onClick={onReset}
          className="flex items-center gap-2 bg-[#1a334d] hover:bg-[#c0392b] text-[#f2ede3] hover:text-[#f2ede3] px-4 py-2.5 transition-colors font-bold uppercase tracking-wider"
          title="Reset Simulation"
        >
          <RotateCcw size={18} /> Reset
        </button>
      </div>

      <div className="flex items-center gap-2 pl-2">
        <FastForward size={16} className="text-[#5b7c99]" />
        {[1, 2, 5].map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            className={`px-3 py-2 font-bold transition-colors text-sm uppercase tracking-wider ${
              speed === s 
                ? 'bg-[#5b7c99] text-[#0d1b2a]' 
                : 'bg-transparent text-[#5b7c99] hover:text-[#f2ede3] hover:bg-[#1a334d]'
            }`}
          >
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
};
