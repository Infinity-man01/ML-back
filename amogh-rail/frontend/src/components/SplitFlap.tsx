import React, { useEffect, useState } from 'react';

interface SplitFlapProps {
  value: string; // The text to display (e.g. "  38.0")
  label?: string;
}

const SplitFlapChar = ({ char }: { char: string }) => {
  const [current, setCurrent] = useState(char);
  const [next, setNext] = useState<string | null>(null);
  const [isFlipping, setIsFlipping] = useState(false);

  useEffect(() => {
    if (char !== current) {
      setNext(char);
      setIsFlipping(true);
      
      const timer = setTimeout(() => {
        setCurrent(char);
        setIsFlipping(false);
        setNext(null);
      }, 100); // Must match CSS animation duration
      
      return () => clearTimeout(timer);
    }
  }, [char, current]);

  return (
    <div className="relative w-12 h-16 bg-[#0d1b2a] border border-[#5b7c99] mx-0.5 rounded-sm flex items-center justify-center font-rail-mono text-4xl font-bold text-[#f2ede3] shadow-inner split-flap-container overflow-hidden">
      {/* Background/Base Character */}
      <div className="absolute inset-0 flex items-center justify-center">
        {next || current}
      </div>
      
      {/* Center hinge line */}
      <div className="absolute top-1/2 left-0 right-0 h-0.5 bg-[#08111a] -translate-y-1/2 z-10 opacity-80" />

      {/* Top Half Flap (Flipping Down) */}
      {isFlipping && (
        <div className="absolute top-0 left-0 right-0 h-8 bg-[#0d1b2a] border-b border-[#5b7c99] overflow-hidden origin-bottom z-20 anim-flip-top">
          <div className="absolute top-0 left-0 right-0 h-16 flex items-center justify-center leading-none">
            {current}
          </div>
        </div>
      )}

      {/* Bottom Half Flap (Flipping Down from middle) */}
      {isFlipping && (
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-[#0d1b2a] border-t border-[#5b7c99] overflow-hidden origin-top z-20 anim-flip-bottom flap-bottom" style={{ transform: 'rotateX(90deg)' }}>
          <div className="absolute bottom-0 left-0 right-0 h-16 flex items-center justify-center leading-none">
            {next}
          </div>
        </div>
      )}
      
      {/* Static Top */}
      {!isFlipping && (
        <div className="absolute top-0 left-0 right-0 h-8 bg-[#0d1b2a] overflow-hidden z-0">
          <div className="absolute top-0 left-0 right-0 h-16 flex items-center justify-center leading-none">
            {current}
          </div>
        </div>
      )}
      
      {/* Static Bottom */}
      {!isFlipping && (
        <div className="absolute bottom-0 left-0 right-0 h-8 bg-[#0d1b2a] overflow-hidden z-0">
          <div className="absolute bottom-0 left-0 right-0 h-16 flex items-center justify-center leading-none">
            {current}
          </div>
        </div>
      )}
    </div>
  );
};

export const SplitFlapDisplay: React.FC<SplitFlapProps> = ({ value, label }) => {
  // Pad the value to always be 5 chars, e.g. " 38.0" or "125.5"
  const paddedValue = value.padStart(5, ' ');
  const chars = paddedValue.split('');

  return (
    <div className="flex flex-col items-center bg-[#08111a] p-5 border-4 border-[#5b7c99] shadow-[0_15px_40px_rgba(0,0,0,0.9)]">
      {label && (
        <div className="text-[#e8a33d] font-rail-sans uppercase tracking-widest text-2xl font-bold mb-4 border-b-2 border-[#5b7c99] w-full text-center pb-2">
          {label}
        </div>
      )}
      <div className="flex items-end">
        {chars.map((c, i) => (
          <SplitFlapChar key={i} char={c} />
        ))}
        <div className="ml-3 pb-1">
          <span className="text-[#5b7c99] font-rail-sans font-bold text-2xl uppercase tracking-widest">MIN</span>
        </div>
      </div>
    </div>
  );
};
