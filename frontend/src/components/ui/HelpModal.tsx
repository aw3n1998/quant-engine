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
            ── 核心功能概览
          </div>
          <div className="flex flex-col gap-3">
            {[
              { step: '① 运行引擎',   desc: '展开左侧任意引擎区域（如 Bandit 或 DRL），点击运行按钮。系统将自动寻找最优策略组合并生成 OOS 权益曲线。' },
              { step: '② 历史对比',   desc: '在 HISTORY 面板勾选多个运行记录，点击 [COMPARE] 按钮，可在主图表中叠加显示多条权益曲线。' },
              { step: '③ 引擎融合',   desc: '在 HISTORY 中勾选多个记录并点击 [FUSE]，按自定义权重将不同引擎的结果融合成一个新的虚拟投资组合。' },
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
            ── 核心算法引擎
          </div>
          <table className="w-full text-caption font-mono border-collapse">
            <thead>
              <tr className="border-b border-border-base text-text-muted text-[10px] uppercase">
                <th className="text-left py-2 pr-4">引擎</th>
                <th className="text-left py-2 pr-4">原理</th>
                <th className="text-left py-2">应用场景</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border-dim">
                <td className="py-2 pr-4 text-accent-amber">Bandit / RL</td>
                <td className="py-2 pr-4 text-text-secondary">多臂老虎机/强化学习，实时动态调整多策略权重</td>
                <td className="py-2 text-accent-emerald">★ 策略池优化</td>
              </tr>
              <tr className="border-b border-border-dim">
                <td className="py-2 pr-4 text-accent-cyan">Bayesian / Genetic</td>
                <td className="py-2 pr-4 text-text-secondary">贝叶斯搜索或进化算法，暴力寻找单策略的最优参数</td>
                <td className="py-2 text-text-secondary">参数调优首选</td>
              </tr>
              <tr>
                <td className="py-2 pr-4 text-accent-magenta">Engine Fusion</td>
                <td className="py-2 pr-4 text-text-secondary">二阶组合，将不同风格的引擎结果再次加权融合</td>
                <td className="py-2 text-accent-emerald">★ 风险对冲组合</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* 关键概念 */}
        <div>
          <div className="text-caption text-accent-cyan uppercase tracking-widest mb-3">
            ── 关键量化概念
          </div>
          <div className="flex flex-col gap-2">
            {[
              { name: 'OOS (Out-of-Sample)', desc: '样本外验证。所有图表展示的均为未参与训练的数据，代表策略在未来的真实表现。' },
              { name: 'Sharpe 夏普比率',    desc: '衡量每单位风险的收益。1.5+ 具备实盘潜力，2.0+ 表现优异。' },
              { name: 'Calmar 比率',        desc: '年化收益与最大回撤之比。衡量"值不值"。越高代表回撤控制越好。' },
              { name: '权益叠加 Overlay',   desc: '将多条曲线放在一起对比，观察不同策略在相同市场环境下的相关性。' },
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
