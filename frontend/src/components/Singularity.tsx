interface SingularityProps {
  status: 'idle' | 'running' | 'done' | 'error';
  recentLog?: string;
}

const STATUS_TEXTS: Record<string, string> = {
  idle: '> [SYS] 系统待机 | 等待指令',
  running: '> [SYS] 引擎运行中 | AI 计算进行中...',
  done: '> [SYS] 运算完成 | 查看右侧结果',
  error: '> [ERR] 连接断开 | 请检查后端服务',
};

const STATUS_COLORS: Record<string, string> = {
  idle: 'text-text-secondary',
  running: 'text-accent-cyan',
  done: 'text-accent-emerald',
  error: 'text-accent-magenta',
};

export default function Singularity({ status, recentLog }: SingularityProps) {
  const statusCls = status === 'running' ? 'is-running'
    : status === 'done' ? 'is-done'
    : status === 'error' ? 'is-error' : '';

  return (
    <div className="flex items-center gap-4 px-4 py-2">
      <div className={`magnetic-field-container scale-[1.8] ${statusCls}`}>
        <div className="magnetic-field">
          {[...Array(6)].map((_, i) => <div key={i} className="magnetic-line" />)}
          <div className="magnetic-equator" />
          <div className="magnetic-core" />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 min-w-0 flex-1">
        <span className="text-display tracking-widest text-text-primary">QUANT ENGINE</span>
        <span
          className={`font-mono text-caption truncate max-w-lg ${STATUS_COLORS[status]}`}
          style={{ textShadow: status === 'running' ? '0 0 8px var(--c-accent-cyan)' : 'none' }}
        >
          {recentLog || STATUS_TEXTS[status]}
        </span>
      </div>
    </div>
  );
}
