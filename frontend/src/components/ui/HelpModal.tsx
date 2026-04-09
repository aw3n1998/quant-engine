interface Props {
  onClose: () => void;
}

export default function HelpModal({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="bg-bg-secondary border border-border-base w-[600px] max-w-[95vw] max-h-[85vh] overflow-y-auto p-6 flex flex-col gap-6"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border-base pb-3">
          <span className="text-heading text-accent-emerald uppercase tracking-widest">
            [? 新手指南]
          </span>
          <button
            onClick={onClose}
            className="text-caption text-text-muted hover:text-accent-magenta transition-colors"
          >
            [✕ 关闭]
          </button>
        </div>

        {/* 三步上手 */}
        <div>
          <div className="text-caption text-accent-cyan uppercase tracking-widest mb-3">
            ── 三步快速上手
          </div>
          <div className="flex flex-col gap-3">
            {[
              { step: '① 选择数据源', desc: '侧边栏 DATA SOURCE：合成数据适合快速测试，Binance 可拉取真实行情，CSV 可导入自己的历史数据。' },
              { step: '② 运行引擎',   desc: '展开任意引擎区域，点击运行按钮。新手推荐 ENGINE A（DRL），AI 自动学习，无需手动调参。' },
              { step: '③ 查看结果',   desc: '引擎完成后，主区域 RESULTS 标签自动显示权益曲线和各项指标评分，越绿越好。' },
            ].map(item => (
              <div key={item.step} className="flex gap-3 border border-border-dim p-3 bg-bg-primary">
                <span className="text-accent-amber font-mono text-caption shrink-0 w-20">{item.step}</span>
                <span className="text-caption text-text-secondary leading-relaxed">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 引擎对比 */}
        <div>
          <div className="text-caption text-accent-cyan uppercase tracking-widest mb-3">
            ── 三大引擎对比
          </div>
          <table className="w-full text-caption font-mono border-collapse">
            <thead>
              <tr className="border-b border-border-base text-text-muted text-[10px] uppercase">
                <th className="text-left py-2 pr-4">引擎</th>
                <th className="text-left py-2 pr-4">原理</th>
                <th className="text-left py-2">适合谁</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border-dim">
                <td className="py-2 pr-4 text-accent-amber">ENGINE A — DRL</td>
                <td className="py-2 pr-4 text-text-secondary">深度强化学习，AI 在模拟环境中反复试错学习最优仓位</td>
                <td className="py-2 text-accent-emerald">★ 新手首选</td>
              </tr>
              <tr className="border-b border-border-dim">
                <td className="py-2 pr-4 text-accent-cyan">ENGINE B — 贝叶斯</td>
                <td className="py-2 pr-4 text-text-secondary">用 Optuna 智能搜索每个策略的最优参数组合</td>
                <td className="py-2 text-text-secondary">有策略偏好的用户</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-accent-emerald">ENGINE C — 遗传算法</td>
                <td className="py-2 pr-4 text-text-secondary">模拟进化，优选多策略因子权重组合</td>
                <td className="py-2 text-text-secondary">追求极致优化的用户</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 指标速查 */}
        <div>
          <div className="text-caption text-accent-cyan uppercase tracking-widest mb-3">
            ── 结果指标速查
          </div>
          <div className="flex flex-col gap-2">
            {[
              { name: '年化收益 Annual Return', desc: '策略折算成一年的收益率。30%+ 优秀，5% 以下偏低。' },
              { name: '最大回撤 Max Drawdown',  desc: '历史上最大亏损幅度（负数）。越接近 0 越好，-25% 以下需谨慎。' },
              { name: '夏普比率 Sharpe Ratio',  desc: '每承受一单位风险能获得多少超额收益。2+ 优秀，<1 偏低。' },
              { name: 'Calmar 比率',             desc: '年化收益除以最大回撤。衡量"值不值"。1.5+ 优秀，<0.4 偏低。' },
            ].map(item => (
              <div key={item.name} className="flex gap-3 border-l-2 border-border-base pl-3">
                <span className="text-accent-violet font-mono text-caption w-44 shrink-0">{item.name}</span>
                <span className="text-caption text-text-secondary leading-relaxed">{item.desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
