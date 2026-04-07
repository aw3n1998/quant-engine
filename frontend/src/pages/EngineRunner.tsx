// frontend/src/pages/EngineRunner.tsx

import { useState, useEffect } from "react";
import type { EngineInfo } from "../types";
import { fetchEngines } from "../services/api";

export default function EngineRunner() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);

  useEffect(() => {
    fetchEngines().then(setEngines).catch(console.error);
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold text-surface-100">Engine Runner</h2>
        <p className="mt-1 text-sm text-surface-400">
          Available optimization engines for strategy parameter tuning
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {engines.map((eng, idx) => (
          <div
            key={eng.id}
            className="relative overflow-hidden rounded-2xl border border-surface-700/30 bg-surface-900/50 p-6 backdrop-blur-sm animate-slide-up"
            style={{ animationDelay: `${idx * 80}ms` }}
          >
            {/* Gradient accent */}
            <div className="absolute top-0 left-0 h-1 w-full bg-gradient-to-r from-accent-cyan via-accent-violet to-accent-emerald" />

            <div className="mt-2">
              <div className="mb-2 flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-cyan/20 to-accent-violet/20">
                  {eng.id === "drl" ? (
                    <svg className="h-5 w-5 text-accent-cyan" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5 text-accent-violet" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  )}
                </span>
                <div>
                  <h3 className="font-semibold text-surface-100">{eng.name}</h3>
                  <span className="font-mono text-xs text-surface-500">{eng.id}</span>
                </div>
              </div>

              <p className="mt-3 text-sm leading-relaxed text-surface-400">
                {eng.description}
              </p>

              <div className="mt-4 rounded-xl bg-surface-800/40 p-4">
                <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-surface-500">
                  Key Features
                </h4>
                {eng.id === "drl" ? (
                  <ul className="flex flex-col gap-1.5 text-xs text-surface-400">
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-cyan" />
                      PPO algorithm with custom Gymnasium environment
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-cyan" />
                      Gaussian noise injection for anti-overfitting
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-cyan" />
                      L1 friction penalty on position changes
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-cyan" />
                      Simple interest settlement to reduce compounding bias
                    </li>
                  </ul>
                ) : (
                  <ul className="flex flex-col gap-1.5 text-xs text-surface-400">
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-violet" />
                      TPE sampler for efficient Bayesian optimization
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-violet" />
                      Walk-Forward Validation preserving time order
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-violet" />
                      Calmar Ratio as multi-fold optimization target
                    </li>
                    <li className="flex items-center gap-2">
                      <span className="h-1 w-1 rounded-full bg-accent-violet" />
                      Expanding window for robust parameter selection
                    </li>
                  </ul>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
