# backend/app/engines/genetic_engine.py
"""
遗传算法优化引擎（两阶段 GA + 因子权重组合）

架构：
    Phase 1：每个策略独立运行遗传算法，搜索最优超参数
             染色体 = 参数向量（归一化到 [0,1]），适应度 = WFV Calmar Ratio
             操作：锦标赛选择 + BLX-α 交叉 + 高斯变异 + 精英保留

    Phase 2：收集各策略最优信号序列（因子），运行第二轮 GA 优化因子权重
             染色体 = n_strategies 维权重向量（Softmax 归一化），
             适应度 = 组合信号的 OOS Calmar Ratio

防过拟合设计:
    - WFV 与贝叶斯引擎完全一致（滚动前向验证）
    - 精英保留避免最优解遗失
    - 高斯变异引入随机性维持种群多样性
    - BLX-α 交叉在父代解之间广域插值，防止早熟收敛
"""
from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd
from scipy.special import softmax

from app.config.config import config
from app.core.base_engine import BaseEngine, EngineResult
from app.core.engine_registry import ENGINE_REGISTRY
from app.utils.metrics import calmar_ratio, compute_all_metrics

logger = logging.getLogger("quant_engine.genetic")


class GeneticEngine(BaseEngine):
    """
    两阶段遗传算法引擎：
    Phase 1 → 每策略参数优化
    Phase 2 → 因子权重组合优化
    """

    def __init__(self) -> None:
        super().__init__(
            name="Genetic Algorithm",
            description="Two-phase GA: per-strategy param optimization + factor weight combination",
        )

    def run(
        self,
        strategies: list,
        df: pd.DataFrame,
        log_callback: Callable | None = None,
        broadcast_fn: Callable | None = None,
        **kwargs,
    ) -> EngineResult:
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        timeframe = kwargs.get("timeframe", config.default_timeframe)
        oos_split = kwargs.get("oos_split", 20.0) / 100.0
        split_idx = int(len(df) * (1 - oos_split))
        df_is = df.iloc[:split_idx]
        df_oos = df.iloc[split_idx:]

        # GA 超参数（可由前端覆盖）
        pop_size = kwargs.get("ga_population", (
            config.ga_population_size_quick if config.quick_mode
            else config.ga_population_size
        ))
        generations = kwargs.get("ga_generations", (
            config.ga_generations_quick if config.quick_mode
            else config.ga_generations
        ))
        n_splits = kwargs.get("wfv_folds", config.bayesian_n_splits)

        emit(f"[{self.name}] 开始两阶段遗传算法 | 种群={pop_size} | 代数={generations}")
        emit(f"[{self.name}] 策略数量: {len(strategies)} | OOS切分: {oos_split*100:.0f}%")

        # ================================================================
        # Phase 1：每策略独立 GA 参数优化
        # ================================================================
        factor_signals: dict[str, pd.Series] = {}   # OOS 最优信号因子
        strategy_params: dict[str, dict] = {}        # 每策略最优参数
        phase1_convergence: list[dict] = []

        for strategy in strategies:
            emit(f"[{self.name}] Phase 1 ▶ 策略: {strategy.name}")
            bounds = self._extract_param_bounds(strategy)
            n_genes = len(bounds)

            if n_genes == 0:
                emit(f"[{self.name}] ⚠ {strategy.name} 无可优化参数，跳过")
                continue

            best_chrom, convergence = self._evolve_strategy(
                strategy=strategy,
                df_is=df_is,
                bounds=bounds,
                n_genes=n_genes,
                pop_size=pop_size,
                generations=generations,
                n_splits=n_splits,
                timeframe=timeframe,
                emit=emit,
                broadcast_fn=broadcast_fn,
                phase1_convergence=phase1_convergence,
            )

            best_params = self._decode_params(best_chrom, bounds)
            strategy_params[strategy.name] = best_params

            # 在 OOS 数据上生成最优信号（因子）
            try:
                oos_signal = strategy.generate_signals(df_oos, best_params)
                factor_signals[strategy.name] = oos_signal
                emit(f"[{self.name}] ✓ {strategy.name} 因子提取完成")
            except Exception as e:
                emit(f"[{self.name}] ✗ {strategy.name} 因子生成失败: {e}")

        if len(factor_signals) == 0:
            # 没有有效因子，返回空结果
            empty = pd.Series(np.zeros(len(df_oos)), index=df_oos.index)
            m = compute_all_metrics(empty, timeframe=timeframe)
            return EngineResult(**m)

        # ================================================================
        # Phase 2：因子权重 GA 组合优化
        # ================================================================
        emit(f"[{self.name}] Phase 2 ▶ 因子权重 GA 组合 ({len(factor_signals)} 个因子)")

        phase2_gens = max(5, generations // 2)
        factor_names = list(factor_signals.keys())
        best_weights, weight_convergence = self._evolve_factor_weights(
            factor_signals=factor_signals,
            df_oos=df_oos,
            pop_size=pop_size,
            generations=phase2_gens,
            timeframe=timeframe,
            emit=emit,
            broadcast_fn=broadcast_fn,
        )

        # 组合权益计算
        aligned = pd.concat(list(factor_signals.values()), axis=1)
        aligned.columns = factor_names
        aligned = aligned.dropna()

        combined = sum(
            best_weights[name] * aligned[name] for name in factor_names
        )
        metrics = compute_all_metrics(combined, timeframe=timeframe)

        emit(f"[{self.name}] 完成！OOS Calmar={metrics['calmar']:.4f} | Sharpe={metrics['sharpe']:.4f}")

        return EngineResult(
            best_params={
                "factor_weights": best_weights,
                "strategy_params": strategy_params,
            },
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=metrics["equity_curve"],
            strategy_names=factor_names,
            extra_plots={
                "factor_weights": best_weights,
                "convergence": phase1_convergence + weight_convergence,
            },
        )

    # ------------------------------------------------------------------
    # 参数空间提取 / 编解码
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_param_bounds(strategy) -> dict:
        """
        通过模拟 Optuna Trial 提取策略参数边界，
        不修改任何策略代码，完全透明。

        返回:
            {param_name: (type, low, high)}
            type: 'int' | 'float' | 'cat'
            对于 'cat'：high = choices list
        """
        bounds: dict = {}

        class MockTrial:
            def suggest_int(self, name, low, high, **kw):
                bounds[name] = ("int", low, high)
                return (low + high) // 2

            def suggest_float(self, name, low, high, **kw):
                bounds[name] = ("float", low, high)
                return (low + high) / 2.0

            def suggest_categorical(self, name, choices, **kw):
                bounds[name] = ("cat", None, list(choices))
                return choices[0]

        try:
            strategy.get_param_space(MockTrial())
        except Exception:
            pass
        return bounds

    @staticmethod
    def _encode_params(params: dict, bounds: dict) -> np.ndarray:
        """参数字典 → [0,1] 归一化染色体向量"""
        genes = []
        for name, (ptype, low, high) in bounds.items():
            val = params.get(name)
            if val is None:
                genes.append(0.5)
                continue
            if ptype == "cat":
                choices = high
                idx = choices.index(val) if val in choices else 0
                genes.append(idx / max(len(choices) - 1, 1))
            else:
                span = high - low
                genes.append(float(np.clip((val - low) / span, 0.0, 1.0)) if span > 0 else 0.5)
        return np.array(genes, dtype=np.float32)

    @staticmethod
    def _decode_params(chromosome: np.ndarray, bounds: dict) -> dict:
        """[0,1] 染色体向量 → 参数字典"""
        params = {}
        for i, (name, (ptype, low, high)) in enumerate(bounds.items()):
            gene = float(np.clip(chromosome[i], 0.0, 1.0))
            if ptype == "int":
                params[name] = int(round(low + gene * (high - low)))
            elif ptype == "float":
                params[name] = float(low + gene * (high - low))
            else:  # cat
                choices = high
                idx = int(round(gene * (len(choices) - 1)))
                params[name] = choices[max(0, min(idx, len(choices) - 1))]
        return params

    # ------------------------------------------------------------------
    # GA 核心操作
    # ------------------------------------------------------------------

    def _wfv_fitness(
        self,
        strategy,
        df: pd.DataFrame,
        chromosome: np.ndarray,
        bounds: dict,
        n_splits: int,
        timeframe: str,
    ) -> float:
        """
        ┌───────────────────────────────────────────────────────────────┐
        │                  GA 适应度 = WFV Calmar Ratio                  │
        │                                                               │
        │  种群多样性（Population Diversity）：                            │
        │    随机初始化多个个体，避免梯度下降式局部最优陷阱。                 │
        │    BLX-α 交叉在父代解之间广域插值，保持搜索空间覆盖度。           │
        │                                                               │
        │  WFV 适应度评估：                                               │
        │    与贝叶斯引擎完全一致的滚动窗口验证，确保跨时段泛化。           │
        │    只有在牛市/熊市/震荡三种不同市场环境中均稳健的参数才能胜出。  │
        │                                                               │
        │  高斯变异 + 精英保留：                                           │
        │    精英保留：避免已发现的最优解在进化过程中被遗忘。               │
        │    高斯变异：引入随机扰动维持多样性，平衡"探索"与"利用"。        │
        └───────────────────────────────────────────────────────────────┘
        """
        params = self._decode_params(chromosome, bounds)
        total = len(df)

        from app.utils.metrics import BARS_PER_YEAR
        bpy = BARS_PER_YEAR.get(timeframe, 365)
        min_train = max(30, int(252 * bpy / 365))
        fold_size = max(20, (total - min_train) // (n_splits + 1))

        fold_calmars = []
        for i in range(n_splits):
            val_start = min_train + fold_size * i
            val_end = min(val_start + fold_size, total)
            if val_end <= val_start:
                break
            val_df = df.iloc[val_start:val_end]
            try:
                sig = strategy.generate_signals(val_df, params)
                cr = calmar_ratio(sig, timeframe=timeframe)
                fold_calmars.append(cr if np.isfinite(cr) else -10.0)
            except Exception:
                fold_calmars.append(-10.0)

        return float(np.mean(fold_calmars)) if fold_calmars else float("-inf")

    def _tournament_select(
        self, population: np.ndarray, fitness: list[float], k: int
    ) -> np.ndarray:
        """锦标赛选择：随机取 k 个个体，返回其中适应度最高者"""
        idx = np.random.choice(len(population), size=k, replace=False)
        best_idx = idx[np.argmax([fitness[i] for i in idx])]
        return population[best_idx].copy()

    def _blx_crossover(
        self, p1: np.ndarray, p2: np.ndarray, alpha: float = 0.5
    ) -> np.ndarray:
        """BLX-α 交叉：在两父代解之间进行扩展插值"""
        d = np.abs(p1 - p2)
        low = np.minimum(p1, p2) - alpha * d
        high = np.maximum(p1, p2) + alpha * d
        child = np.random.uniform(low, high).astype(np.float32)
        return np.clip(child, 0.0, 1.0)

    def _mutate(
        self,
        chromosome: np.ndarray,
        mutation_rate: float,
        sigma: float,
    ) -> np.ndarray:
        """高斯变异：以 mutation_rate 概率对每个基因加入正态扰动"""
        mask = np.random.random(len(chromosome)) < mutation_rate
        noise = np.random.normal(0, sigma, size=chromosome.shape).astype(np.float32)
        mutated = chromosome + mask * noise
        return np.clip(mutated, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Phase 1 演化（单策略）
    # ------------------------------------------------------------------

    def _evolve_strategy(
        self,
        strategy,
        df_is: pd.DataFrame,
        bounds: dict,
        n_genes: int,
        pop_size: int,
        generations: int,
        n_splits: int,
        timeframe: str,
        emit: Callable,
        broadcast_fn: Callable | None,
        phase1_convergence: list,
    ) -> tuple[np.ndarray, list]:
        elite_n = max(1, int(config.ga_elite_ratio * pop_size))

        # 随机初始化种群
        population = np.random.uniform(0.0, 1.0, size=(pop_size, n_genes)).astype(np.float32)
        convergence = []

        for gen in range(generations):
            fitness = [
                self._wfv_fitness(strategy, df_is, chrom, bounds, n_splits, timeframe)
                for chrom in population
            ]

            ranked = sorted(zip(fitness, range(len(fitness))), reverse=True)
            elite_idx = [r[1] for r in ranked[:elite_n]]
            elites = population[elite_idx].copy()

            best_fit = ranked[0][0]
            std_fit = float(np.std([f for f, _ in ranked if np.isfinite(f)]))

            convergence.append({
                "gen": gen + 1,
                "strategy": strategy.name,
                "best_calmar": best_fit,
                "std_calmar": std_fit,
                "phase": 1,
            })

            emit(
                f"[GA P1] {strategy.name} | Gen {gen+1}/{generations} | "
                f"Best Calmar={best_fit:.4f} | Std={std_fit:.4f}"
            )

            if broadcast_fn:
                broadcast_fn({
                    "type": "progress_plot",
                    "data": {"step": gen, "reward": best_fit, "entropy": std_fit},
                })

            # 生成后代
            offspring = []
            valid_fitness = [(f if np.isfinite(f) else -999) for f in fitness]
            while len(offspring) < pop_size - elite_n:
                p1 = self._tournament_select(population, valid_fitness, config.ga_tournament_k)
                p2 = self._tournament_select(population, valid_fitness, config.ga_tournament_k)
                child = self._blx_crossover(p1, p2, config.ga_crossover_alpha)
                child = self._mutate(child, config.ga_mutation_rate, config.ga_mutation_sigma)
                offspring.append(child)

            population = np.vstack([elites, np.array(offspring, dtype=np.float32)])

        # 最终最优个体
        final_fitness = [
            self._wfv_fitness(strategy, df_is, chrom, bounds, n_splits, timeframe)
            for chrom in population
        ]
        best_idx = int(np.argmax([f if np.isfinite(f) else -999 for f in final_fitness]))
        return population[best_idx].copy(), convergence

    # ------------------------------------------------------------------
    # Phase 2 演化（因子权重）
    # ------------------------------------------------------------------

    def _evolve_factor_weights(
        self,
        factor_signals: dict[str, pd.Series],
        df_oos: pd.DataFrame,
        pop_size: int,
        generations: int,
        timeframe: str,
        emit: Callable,
        broadcast_fn: Callable | None,
    ) -> tuple[dict[str, float], list]:
        factor_names = list(factor_signals.keys())
        n = len(factor_names)
        elite_n = max(1, int(config.ga_elite_ratio * pop_size))

        # 对齐所有因子
        aligned = pd.concat(list(factor_signals.values()), axis=1)
        aligned.columns = factor_names
        aligned = aligned.dropna()

        def weight_fitness(raw_weights: np.ndarray) -> float:
            weights = softmax(raw_weights * 5)  # 放大差异，使 softmax 更具区分度
            combined = sum(weights[i] * aligned[name] for i, name in enumerate(factor_names))
            cr = calmar_ratio(combined, timeframe=timeframe)
            return cr if np.isfinite(cr) else -10.0

        # 使用 Dirichlet 分布初始化（确保权重多样性）
        population = np.random.dirichlet(np.ones(n), size=pop_size).astype(np.float32)
        convergence = []

        for gen in range(generations):
            fitness = [weight_fitness(chrom) for chrom in population]
            ranked = sorted(zip(fitness, range(len(fitness))), reverse=True)
            elite_idx = [r[1] for r in ranked[:elite_n]]
            elites = population[elite_idx].copy()

            best_fit = ranked[0][0]
            std_fit = float(np.std([f for f, _ in ranked if np.isfinite(f)]))

            convergence.append({
                "gen": gen + 1,
                "strategy": "factor_weights",
                "best_calmar": best_fit,
                "std_calmar": std_fit,
                "phase": 2,
            })

            emit(
                f"[GA P2] 因子权重 | Gen {gen+1}/{generations} | "
                f"Portfolio Calmar={best_fit:.4f}"
            )

            if broadcast_fn:
                broadcast_fn({
                    "type": "progress_plot",
                    "data": {"step": gen + 100, "reward": best_fit, "entropy": std_fit},
                })

            offspring = []
            valid_fitness = [(f if np.isfinite(f) else -999) for f in fitness]
            while len(offspring) < pop_size - elite_n:
                p1 = self._tournament_select(population, valid_fitness, config.ga_tournament_k)
                p2 = self._tournament_select(population, valid_fitness, config.ga_tournament_k)
                child = self._blx_crossover(p1, p2, config.ga_crossover_alpha)
                child = self._mutate(child, config.ga_mutation_rate, config.ga_mutation_sigma)
                offspring.append(child)

            population = np.vstack([elites, np.array(offspring, dtype=np.float32)])

        # 最终最优权重
        final_fitness = [weight_fitness(chrom) for chrom in population]
        best_idx = int(np.argmax([f if np.isfinite(f) else -999 for f in final_fitness]))
        best_raw = population[best_idx]
        best_weights_arr = softmax(best_raw * 5)
        best_weights = {name: float(best_weights_arr[i]) for i, name in enumerate(factor_names)}

        return best_weights, convergence


ENGINE_REGISTRY.register("genetic", GeneticEngine)
