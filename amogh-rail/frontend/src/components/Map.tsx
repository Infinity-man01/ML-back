import React, { useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Rectangle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L, { LatLngBounds } from 'leaflet';
import type { Train } from '../types';
import { Zap, AlertTriangle, CloudRain, Sun, CloudFog } from 'lucide-react';

// Fix Leaflet marker icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Exact Indian Railways Eastern Railway Howrah–Barddhaman Line Coordinates
export const STATIONS_GEO: Record<string, { pos: [number, number]; name: string; isJunction: boolean }> = {
  HWH: { pos: [22.5839, 88.3425], name: "Howrah (HWH)", isJunction: true },
  BLY: { pos: [22.6500, 88.3400], name: "Bally (BLY)", isJunction: false },
  SHE: { pos: [22.7550, 88.3400], name: "Seoraphuli Jn (SHE)", isJunction: true },
  BDC: { pos: [22.9200, 88.3800], name: "Bandel Jn (BDC)", isJunction: true },
  MMR: { pos: [23.2000, 88.1300], name: "Memari (MMR)", isJunction: false },
  SKG: { pos: [23.2600, 88.0300], name: "Saktigarh (SKG)", isJunction: true },
  BWN: { pos: [23.2500, 87.8600], name: "Barddhaman Jn (BWN)", isJunction: true },
  GUS: { pos: [23.4700, 87.8500], name: "Guskara (GUS)", isJunction: false },
  PAN: { pos: [23.4800, 87.4300], name: "Panagarh (PAN)", isJunction: false },
};

// Track segments in strict topological railway sequence along the Hooghly / NH19 corridor
const SECTIONS = [
  { id: "HWH-BLY", from: "HWH", to: "BLY", type: "Double" },
  { id: "BLY-SHE", from: "BLY", to: "SHE", type: "Double" },
  { id: "SHE-BDC", from: "SHE", to: "BDC", type: "Double" },
  { id: "SHE-SKG", from: "SHE", to: "SKG", type: "Single" },
  { id: "BDC-MMR", from: "BDC", to: "MMR", type: "Single" },
  { id: "MMR-SKG", from: "MMR", to: "SKG", type: "Single" },
  { id: "MMR-BWN", from: "MMR", to: "BWN", type: "Single" },
  { id: "SKG-BWN", from: "SKG", to: "BWN", type: "Single" },
  { id: "BWN-GUS", from: "BWN", to: "GUS", type: "Single" },
  { id: "GUS-PAN", from: "GUS", to: "PAN", type: "Single" },
];

const TRAIN_TYPE_COLOR: Record<string, string> = {
  Express:   '#5b7c99', // Steel blue
  Passenger: '#2e7d32', // Green
  Freight:   '#e8a33d', // Amber
  Suburban:  '#8b5cf6', // Purple
};

const getTrainIcon = (train: Train) => {
  let borderColor = '#0d1b2a'; // Default navy
  let borderWidth = '2px';
  let isDelayed = train.disrupted || train.status === 'DELAYED';
  
  if (isDelayed) {
    borderColor = '#ef4444'; // Bright Red border for the box itself
    borderWidth = '2px';
  } else if (train.status === 'WAITING' && (train.held_min ?? 0) > 0) {
    borderColor = '#e8a33d'; // Amber border
    borderWidth = '3px';
  }

  const typeColor = TRAIN_TYPE_COLOR[train.train_type] ?? '#5b7c99';
  const label = train.train_type ? train.train_type.charAt(0) : 'T';

  const svg = `
    <div style="position:relative; width:26px; height:26px; display:flex; align-items:center; justify-content:center;">
      ${isDelayed ? '<div class="absolute -inset-2 rounded-full border-2 border-red-500 animate-ping opacity-75 bg-red-500/30 z-0"></div><div class="absolute -inset-1 rounded-full border-2 border-red-500 bg-red-500/20 z-0"></div>' : ''}
      <div style="position:relative; z-index:10; width:22px; height:22px; background:${typeColor}; border-radius:4px; border:${borderWidth} solid ${borderColor}; display:flex; align-items:center; justify-content:center; color:#0d1b2a; font-family:monospace; font-weight:bold; font-size:12px; box-shadow: 0 2px 5px rgba(0,0,0,0.5);">
        ${label}
      </div>
    </div>
  `;

  return L.divIcon({
    className: 'custom-train-icon bg-transparent',
    html: svg,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -14],
  });
};

// Helper for square markers
const getSquareBounds = (lat: number, lng: number, size = 0.015): LatLngBounds => {
  return new LatLngBounds(
    [lat - size, lng - size],
    [lat + size, lng + size]
  );
};

interface MapProps {
  trains: Train[];
  onDisruption?: (trainId: string, upstreamDelay: number, weatherFlag: number) => void;
}

export const RailwayMap: React.FC<MapProps> = ({ trains, onDisruption }) => {
  const [injectDelay, setInjectDelay] = useState<number>(20);
  const [injectWeather, setInjectWeather] = useState<number>(1); // Rain
  const [injectingId, setInjectingId] = useState<string | null>(null);

  const occupiedSections = new Set(
    trains
      .filter((t) => t.status !== 'COMPLETED' && t.current_block)
      .map((t) => t.current_block as string)
  );

  const handleInject = (trainId: string) => {
    if (onDisruption) {
      setInjectingId(trainId);
      onDisruption(trainId, injectDelay, injectWeather);
      setTimeout(() => setInjectingId(null), 1200);
    }
  };

  return (
    <div className="w-full h-full relative z-0">
      <MapContainer
        center={[23.05, 87.95]}
        zoom={9}
        style={{ width: '100%', height: '100%' }}
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Render Track Polylines */}
        {SECTIONS.map((sec) => {
          const fromPos = STATIONS_GEO[sec.from]?.pos;
          const toPos = STATIONS_GEO[sec.to]?.pos;
          if (!fromPos || !toPos) return null;

          const isOccupied = occupiedSections.has(sec.id) || occupiedSections.has(`${sec.to}-${sec.from}`);

          return (
            <React.Fragment key={sec.id}>
              {/* Main Track Polyline */}
              <Polyline
                positions={[fromPos, toPos]}
                pathOptions={{
                  color: isOccupied ? '#c0392b' : (sec.type === 'Single' ? '#e8a33d' : '#5b7c99'),
                  weight: isOccupied ? 6 : (sec.type === 'Single' ? 3 : 5),
                  opacity: 0.9,
                  dashArray: sec.type === 'Single' && !isOccupied ? '6, 6' : undefined,
                }}
              />
            </React.Fragment>
          );
        })}

        {/* Station Square Markers */}
        {Object.keys(STATIONS_GEO).map((code, index) => {
          const sta = STATIONS_GEO[code];
          // Check if any train is currently AT this station/section boundary
          const isOccupied = trains.some(t => t.status !== 'COMPLETED' && (t.current_block?.includes(code)));
          
          // Calculate queue: trains waiting exactly at this station's coordinates
          const queueCount = trains.filter(t => 
            t.status === 'WAITING' && 
            Math.abs(t.lat - sta.pos[0]) < 0.001 && 
            Math.abs(t.lng - sta.pos[1]) < 0.001
          ).length;

          let markerColor = '#64748b'; // Default
          if (queueCount >= 4) {
            markerColor = '#c0392b'; // Severe congestion (Red)
          } else if (queueCount > 1) {
            markerColor = '#e8a33d'; // Forming queue (Amber)
          } else if (isOccupied) {
            markerColor = '#5b7c99'; // Just occupied normally
          } else if (trains.length > 0) {
            markerColor = '#2e7d32'; // Clear (Green)
          }

          // Stagger label placement to prevent overlapping (up/down alternating)
          const latOffset = (index % 2 === 0) ? 0.06 : -0.06;

          return (
            <React.Fragment key={code}>
              <Rectangle
                bounds={getSquareBounds(sta.pos[0], sta.pos[1], sta.isJunction ? 0.012 : 0.008)}
                pathOptions={{
                  color: '#0d1b2a',
                  fillColor: markerColor,
                  fillOpacity: 1,
                  weight: 1.5,
                }}
              >
                <Popup>
                  <div className="font-rail-mono text-[#f2ede3] bg-[#0d1b2a] border border-[#5b7c99] p-2">
                    <strong className="uppercase">{sta.name}</strong>
                    {queueCount > 0 && <div className="text-[#e8a33d] text-xs mt-1">{queueCount} trains waiting</div>}
                  </div>
                </Popup>
              </Rectangle>
              
              {/* Queue Badge */}
              {queueCount > 1 && (
                <Marker 
                  position={[sta.pos[0] + latOffset, sta.pos[1]]} 
                  icon={L.divIcon({
                    className: 'bg-transparent',
                    html: `<div style="background-color:#0d1b2a; border:2px solid ${markerColor}; color:#f2ede3; font-family:monospace; font-weight:bold; font-size:14px; padding:4px 10px; border-radius:16px; white-space:nowrap; box-shadow:0 4px 6px rgba(0,0,0,0.5);">${queueCount} WAITING</div>`,
                    iconSize: [100, 30],
                    iconAnchor: [50, 15],
                  })} 
                />
              )}
            </React.Fragment>
          )
        })}

        {/* Train Markers */}
        {trains
          .filter((t) => t.status !== 'COMPLETED')
          .map((train) => (
            <Marker key={train.id} position={[train.lat, train.lng]} icon={getTrainIcon(train)}>
              <Popup minWidth={290}>
                <div className="font-rail-mono text-[#f2ede3] bg-[#0d1b2a] border border-[#5b7c99] min-w-[280px]">
                  {/* Header */}
                  <div className="bg-[#1a334d] p-3 border-b border-[#5b7c99] flex justify-between items-center">
                    <div>
                      <strong className="text-sm font-bold tracking-widest">{train.id}</strong>
                      <span className="ml-2 text-xs text-[#5b7c99]">({train.train_type})</span>
                    </div>
                    <span className="text-[10px] bg-[#08111a] px-2 py-1 uppercase tracking-widest">
                      Priority {train.priority}
                    </span>
                  </div>

                  {/* Status & Location */}
                  <div className="grid grid-cols-2 gap-2 p-3 border-b border-[#1a334d]">
                    <div className="bg-[#08111a] p-2 border border-[#1a334d]">
                      <span className="text-[10px] text-[#5b7c99] uppercase tracking-widest block mb-1">Status</span>
                      <div
                        className="font-bold text-xs uppercase"
                        style={{
                          color:
                            train.status === 'DELAYED'
                              ? '#c0392b'
                              : train.status === 'WAITING'
                              ? '#e8a33d'
                              : '#5b7c99',
                        }}
                      >
                        {train.status}
                        {(train.held_min ?? 0) > 0 && ` (Held ${train.held_min}m)`}
                      </div>
                    </div>

                    <div className="bg-[#08111a] p-2 border border-[#1a334d]">
                      <span className="text-[10px] text-[#5b7c99] uppercase tracking-widest block mb-1">Section</span>
                      <div className="font-bold text-xs uppercase text-[#f2ede3]">
                        {train.current_block ?? 'Waiting'}
                      </div>
                    </div>
                  </div>

                  {/* ML Delay Prediction */}
                  <div className="p-3 border-b border-[#1a334d] bg-[#08111a]">
                    <div className="font-bold text-xs mb-2 flex justify-between uppercase">
                      <span className="text-[#5b7c99]">ML Prediction</span>
                      <span style={{ color: train.is_delayed_prediction ? '#c0392b' : '#2e7d32' }}>
                        {train.predicted_delay_min.toFixed(1)}m delay
                      </span>
                    </div>

                    <div className="flex justify-between text-[10px] mb-2 uppercase">
                      <span className="text-[#5b7c99]">Confidence</span>
                      <strong style={{ color: train.delay_probability_pct > 60 ? '#c0392b' : '#2e7d32' }}>
                        {train.delay_probability_pct.toFixed(1)}%
                      </strong>
                    </div>

                    {train.reasoning && train.reasoning.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-[#1a334d]">
                        {train.reasoning.map((r, idx) => (
                          <div key={idx} className="text-[#5b7c99] text-[9px] uppercase leading-relaxed">
                            - {r}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Disruption Injection Tool */}
                  <div className="p-3 bg-[#0d1b2a]">
                    <div className="font-bold text-[10px] text-[#e8a33d] mb-2 uppercase tracking-widest">
                      Inject Disruption
                    </div>

                    <div className="mb-3">
                      <div className="flex justify-between text-[10px] text-[#5b7c99] mb-1 uppercase">
                        <span>Delay Offset:</span>
                        <strong className="text-[#e8a33d]">+{injectDelay}m</strong>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="45"
                        step="5"
                        value={injectDelay}
                        onChange={(e) => setInjectDelay(Number(e.target.value))}
                        className="w-full"
                      />
                    </div>

                    <div className="flex gap-2 mb-3">
                      {[
                        { flag: 0, label: 'CLR' },
                        { flag: 1, label: 'RAN' },
                        { flag: 2, label: 'FOG' },
                      ].map((w) => (
                        <button
                          key={w.flag}
                          onClick={() => setInjectWeather(w.flag)}
                          className={`flex-1 py-1 border text-[9px] font-bold uppercase tracking-widest ${
                            injectWeather === w.flag 
                              ? 'border-[#e8a33d] bg-[#1a334d] text-[#e8a33d]' 
                              : 'border-[#5b7c99] bg-transparent text-[#5b7c99]'
                          }`}
                        >
                          {w.label}
                        </button>
                      ))}
                    </div>

                    <button
                      onClick={() => handleInject(train.id)}
                      disabled={injectingId === train.id}
                      className="w-full py-2 bg-[#e8a33d] text-[#0d1b2a] font-bold text-[10px] uppercase tracking-widest hover:bg-[#f2ede3] transition-colors"
                    >
                      {injectingId === train.id ? 'Processing...' : 'Apply Disruption'}
                    </button>
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
      </MapContainer>
    </div>
  );
};
