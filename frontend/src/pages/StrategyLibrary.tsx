// frontend/src/pages/StrategyLibrary.tsx

import { useState, useEffect } from "react";
import type { StrategyInfo } from "../types";
import { fetchStrategies } from "../services/api";

export default function StrategyLibrary() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchStrategies().then(setStrategies).catch(console.error);
  }, []);

  const filtered = strategies.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.description.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-surface-100">Strategy Library</h2>
          <p className="mt-1 text-sm text-surface-400">
            {strategies.length} strategies registered in the system
          </p>
        </div>
        <input
          type="text"
          placeholder="Search strategies..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-xl border border-surface-700/50 bg-surface-800/40 px-4 py-2.5 text-sm text-surface-200 outline-none placeholder:text-surface-600 focus:border-accent-cyan/50 sm:w-64"
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((s, idx) => (
          <div
            key={s.id}
            className="group relative overflow-hidden rounded-2xl border border-surface-700/30 bg-surface-900/50 p-5 backdrop-blur-sm transition-all duration-300 hover:border-surface-600/60 hover:bg-surface-800/50 animate-slide-up"
            style={{ animationDelay: `${idx * 40}ms` }}
          >
            {/* Decorative gradient */}
            <div className="absolute -right-6 -top-6 h-24 w-24 rounded-full bg-gradient-to-br from-accent-violet/8 to-accent-cyan/8 blur-2xl transition-opacity duration-300 group-hover:opacity-100 opacity-50" />

            <div className="relative">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="font-semibold text-surface-100">{s.name}</h3>
                <span className="rounded-full bg-surface-800 px-2.5 py-0.5 text-[10px] font-mono text-surface-500">
                  {s.id}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-surface-400">
                {s.description}
              </p>
            </div>
          </div>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="py-12 text-center text-sm text-surface-500">
          No strategies match your search.
        </p>
      )}
    </div>
  );
}
