import { useEffect, useRef, useState } from "react";
import type { Generation } from "../types";

const SPEEDS = [0.5, 1, 2];
const BASE_MS = 1900; // slower, deliberate cadence — one unseen block at a time

export default function TimelineScrubber({ generations, value, onChange, playing, setPlaying }:
  {
    generations: Generation[]; value: number; onChange: (g: number) => void;
    playing: boolean; setPlaying: (p: boolean) => void;
  }) {
  const [speed, setSpeed] = useState(1);
  const timer = useRef<number | null>(null);
  const valRef = useRef(value);
  valRef.current = value;

  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => {
      const next = valRef.current + 1;
      if (next > generations.length - 1) { setPlaying(false); return; }
      onChange(next);
    }, BASE_MS / speed) as unknown as number;
    return () => { if (timer.current) clearInterval(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed]);

  const gen = generations[value];
  const last = generations.length - 1;
  const progress = last > 0 ? (value / last) * 100 : 0;

  return (
    <div className="card p-3 flex items-center gap-4">
      <button
        onClick={() => {
          if (value >= last) onChange(0);
          setPlaying(!playing);
        }}
        className="shrink-0 w-11 h-11 rounded-full bg-cyan/15 text-cyan grid place-items-center
                   hover:bg-cyan/25 transition glow-cyan">
        {playing ? (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12" rx="1" /><rect x="9" y="2" width="4" height="12" rx="1" /></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>
        )}
      </button>

      <div className="flex-1">
        <div className="flex justify-between text-xs text-muted mb-1">
          <span>
            Generation <span className="text-ink font-semibold">{value}</span> / {last}
            {playing && (
              <span className="text-cyan ml-2 inline-flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan animate-pulse" /> simulating
              </span>
            )}
          </span>
          <span className="text-cyan font-mono">{gen?.date}</span>
        </div>
        <div className="relative">
          <div className="absolute inset-y-1/2 left-0 h-[3px] -translate-y-1/2 rounded-full bg-cyan/40 pointer-events-none transition-[width] duration-300"
            style={{ width: `${progress}%` }} />
          <input
            type="range" min={0} max={last} value={value}
            onChange={(e) => { setPlaying(false); onChange(Number(e.target.value)); }}
            className="relative w-full accent-cyan cursor-pointer" />
        </div>
      </div>

      <div className="shrink-0 flex items-center gap-1 bg-surface2 rounded-lg p-1">
        {SPEEDS.map((s) => (
          <button key={s} onClick={() => setSpeed(s)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
              speed === s ? "bg-cyan/15 text-cyan" : "text-muted hover:text-ink"}`}>
            {s}×
          </button>
        ))}
      </div>
    </div>
  );
}
