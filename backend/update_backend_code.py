import re
import os

print(f"Current dir: {os.getcwd()}")

# 1. Update routes.py
routes_path = "app/api/routes.py"
with open(routes_path, "r", encoding="utf-8") as f:
    r_code = f.read()

r_code = r_code.replace("payload: RunRequest", "payload: RunEngineRequest")
r_code = r_code.replace(
    "async def _run_in_background(\n    engine_id: str, strategy_ids: list[str], df: pd.DataFrame\n) -> None:",
    "async def _run_in_background(\n    engine_id: str, strategy_ids: list[str], df: pd.DataFrame, params: dict\n) -> None:"
)
replacement = """    if engine_id == 'drl':
        strategies = [STRATEGY_REGISTRY[sid] for sid in strategy_ids]
        try:
            await manager.send_log("info", f"[{engine.name}] Running PPO Fusion on {len(strategies)} strategies")
            result = await asyncio.to_thread(engine.run, strategies, df, log_callback=log_cb, **params)
            result_dict = {
                "engine": engine_id,
                "strategy": "portfolio",
                "strategy_name": "DRL Fusion Portfolio",
                "best_params": result.best_params,
                "sharpe": result.sharpe,
                "calmar": result.calmar,
                "max_drawdown": result.max_drawdown,
                "annual_return": result.annual_return,
                "equity_curve": result.equity_curve,
            }
            await manager.send_result(result_dict)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            await manager.send_log("error", f"[{engine.name}] DRL Fusion failed: {exc}")
    else:
        for sid in strategy_ids:
            strategy = STRATEGY_REGISTRY[sid]
            await manager.send_log("info", f"[{engine.name}] Running strategy: {strategy.name}")
            try:
                result = await asyncio.to_thread(engine.run, strategy, df, log_callback=log_cb, **params)
                result_dict = {
                    "engine": engine_id,
                    "strategy": sid,
                    "strategy_name": strategy.name,
                    "best_params": result.best_params,
                    "sharpe": result.sharpe,
                    "calmar": result.calmar,
                    "max_drawdown": result.max_drawdown,
                    "annual_return": result.annual_return,
                    "equity_curve": result.equity_curve,
                }
                await manager.send_result(result_dict)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                await manager.send_log("error", f"[{engine.name}] {strategy.name} failed: {exc}")
"""
r_code = re.sub(r'    for sid in strategy_ids:[\s\S]+?failed: \{exc\}"\)', replacement, r_code)
# Ensure the background task launch is updated
r_code = r_code.replace(
    'background_tasks.add_task(_run_in_background, payload.engine, payload.strategies, df)',
    'background_tasks.add_task(_run_in_background, payload.engine, payload.strategies, df, payload.model_dump())'
)
with open(routes_path, "w", encoding="utf-8") as f:
    f.write(r_code)

# 2. Update bayesian_engine.py
bayes_path = "app/engines/bayesian_engine.py"
with open(bayes_path, "r", encoding="utf-8") as f:
    b_code = f.read()

b_code = b_code.replace("def run(self, strategy: BaseStrategy, df: pd.DataFrame, log_callback=None) -> EngineResult:", 
                        "def run(self, strategy, df: pd.DataFrame, log_callback=None, **kwargs) -> EngineResult:")

b_code = b_code.replace("n_trials = (\n            config.bayesian_n_trials_quick\n            if config.quick_mode\n            else config.bayesian_n_trials\n        )", 
                        'n_trials = kwargs.get("optuna_trials", 100)')
b_code = b_code.replace("n_splits = config.bayesian_n_splits_wfv", 'n_splits = kwargs.get("wfv_folds", 5)')

b_code = b_code.replace("""        study = optuna.create_study(direction="maximize", sampler=sampler)""",
"""        pruner = optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)
        study = optuna.create_study(direction="maximize", sampler=sampler, pruner=pruner)""")

with open(bayes_path, "w", encoding="utf-8") as f:
    f.write(b_code)

# 3. Update drl_engine.py
drl_path = "app/engines/drl_engine.py"
with open(drl_path, "r", encoding="utf-8") as f:
    d_code = f.read()

d_code = d_code.replace("def run(self, strategy: BaseStrategy, df: pd.DataFrame, log_callback=None) -> EngineResult:",
                        "def run(self, strategies: list, df: pd.DataFrame, log_callback=None, **kwargs) -> EngineResult:")

d_body = """
        def emit(msg: str) -> None:
            if log_callback:
                log_callback("info", msg)

        from stable_baselines3 import PPO
        import numpy as np
        
        emit(f"[{self.name}] Accumulating signals from {len(strategies)} strategies...")
        all_returns = []
        for s in strategies:
            p = self._get_default_params(s)
            ret = s.generate_signals(df, p).fillna(0)
            all_returns.append(ret.values)
        
        # Shape: (T, N)
        portfolio_returns = np.column_stack(all_returns)
        
        train_size = int(len(df) * (1 - kwargs.get("oos_split", 20.0)/100.0))
        train_returns = portfolio_returns[:train_size]
        val_returns = portfolio_returns[train_size:]

        train_env = CryptoPortfolioEnv(
            target_returns=train_returns,
            target_roi=kwargs.get("target_roi", 10.0),
            max_drawdown=kwargs.get("max_drawdown", -15.0),
            friction_penalty=kwargs.get("friction_penalty", 0.0005)
        )
        
        total_timesteps = kwargs.get("ppo_timesteps", 50000)
        if kwargs.get("quick_mode", False):
            total_timesteps = 1000

        emit(f"[{self.name}] Training PPO setup completed...")

        model = PPO(
            "MlpPolicy",
            train_env,
            learning_rate=config.drl_learning_rate,
            gamma=config.drl_gamma,
            ent_coef=0.01,
            seed=config.default_seed,
            verbose=0,
        )
        
        emit(f"[{self.name}] Training PPO on {total_timesteps} timesteps...")
        model.learn(total_timesteps=total_timesteps)

        emit(f"[{self.name}] Converging... evaluating agent on validation set")
        val_env = CryptoPortfolioEnv(
            target_returns=val_returns,
            target_roi=kwargs.get("target_roi", 10.0),
            max_drawdown=kwargs.get("max_drawdown", -15.0),
            friction_penalty=kwargs.get("friction_penalty", 0.0005)
        )

        obs, _ = val_env.reset()
        done = False
        val_equity = [1.0]

        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, _ = val_env.step(action)
            val_equity.append(val_env.env._portfolio_value if hasattr(val_env, 'env') else val_env._portfolio_value)
            done = terminated or truncated

        val_eq_arr = np.array(val_equity)
        daily_ret = np.diff(val_eq_arr) / val_eq_arr[:-1]
        daily_ret_series = pd.Series(daily_ret)
        
        from app.utils.metrics import compute_all_metrics
        metrics = compute_all_metrics(daily_ret_series)

        return EngineResult(
            engine_id="drl",
            strategy_id="portfolio",
            best_params={"algorithm": "PPO", "ent_coef": 0.01, "timesteps": total_timesteps},
            sharpe=metrics["sharpe"],
            calmar=metrics["calmar"],
            max_drawdown=metrics["max_drawdown"],
            annual_return=metrics["annual_return"],
            equity_curve=val_equity,
        )
"""
d_code = re.sub(r'        def emit\(msg: str\) -> None:(.|\n)+?equity_curve=[\w\.]+,?\s*\)', d_body, d_code)

with open(drl_path, "w", encoding="utf-8") as f:
    f.write(d_code)

print("Update completed successfully.")
