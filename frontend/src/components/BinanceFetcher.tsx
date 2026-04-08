import { useState } from 'react';
import { fetchBinance } from '../services/api';

const SYMBOLS = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
  'XRP/USDT', 'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
];

const TIMEFRAMES = [
  { value: '1d',  label: '1D  日线（中长期）' },
  { value: '4h',  label: '4H  四小时（摆动）' },
  { value: '1h',  label: '1H  小时（日内推荐）' },
  { value: '30m', label: '30M 半小时' },
  { value: '15m', label: '15M 十五分钟' },
  { value: '5m',  label: '5M  五分钟（高频日内）' },
];

// 推荐K线数：约覆盖3个月历史
const RECOMMENDED_LIMITS: Record<string, number> = {
  '1d': 90, '4h': 540, '1h': 2160, '30m': 4320, '15m': 8640, '5m': 25920,
};

// 每根K线对应小时数
const TF_HOURS: Record<string, number> = {
  '1d': 24, '4h': 4, '1h': 1, '30m': 0.5, '15m': 0.25, '5m': 1 / 12,
};

interface Props {
  onLoaded?: (info: { symbol: string; timeframe: string; rows: number; date_range: string }) => void;
}

export default function BinanceFetcher({ onLoaded }: Props) {
  const [symbol, setSymbol]     = useState('BTC/USDT');
  const [timeframe, setTf]      = useState('1h');
  const [limit, setLimit]       = useState(2160);
  const [useMev, setUseMev]     = useState(false);
  const [useNlp, setUseNlp]     = useState(false);
  const [nlpKey, setNlpKey]     = useState('');
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<string | null>(null);
  const [error, setError]       = useState<string | null>(null);

  const handleTfChange = (tf: string) => {
    setTf(tf);
    setLimit(RECOMMENDED_LIMITS[tf] ?? 1000);
  };

  const estimatedDays = Math.round((limit * TF_HOURS[timeframe]) / 24);

  const handleFetch = async () => {
    if (useNlp && !nlpKey.trim()) {
      setError('启用 NLP 情绪时需填写 WorldNewsAPI Key');
      return;
    }
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetchBinance({
        symbol,
        timeframe,
        limit,
        use_mev: useMev,
        use_nlp: useNlp,
        worldnews_api_key: nlpKey,
      });
      const tags = [
        res.mev_enabled ? 'MEV✓' : '',
        res.nlp_enabled ? 'NLP✓' : '',
      ].filter(Boolean).join(' ');
      const msg = `已加载 ${res.symbol} ${res.timeframe} × ${res.rows} 根K线 (${res.date_range})${tags ? ' [' + tags + ']' : ''}`;
      setResult(msg);
      onLoaded?.({ symbol: res.symbol, timeframe: res.timeframe, rows: res.rows, date_range: res.date_range });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '拉取失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* 交易对 */}
      <label className="flex flex-col gap-1">
        <span className="text-[#00FFFF] text-xs uppercase tracking-wider">交易对</span>
        <select
          className="matrix-input w-full bg-[#050a05]"
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
        >
          {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </label>

      {/* 时间框架 */}
      <label className="flex flex-col gap-1">
        <span className="text-[#00FFFF] text-xs uppercase tracking-wider">时间框架</span>
        <select
          className="matrix-input w-full bg-[#050a05]"
          value={timeframe}
          onChange={e => handleTfChange(e.target.value)}
        >
          {TIMEFRAMES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </label>

      {/* K线数量 */}
      <label className="flex justify-between items-center text-xs">
        <span>K线数量</span>
        <input
          type="number"
          min={100}
          max={100000}
          step={100}
          className="matrix-input w-28 text-right"
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
        />
      </label>

      {/* 数据覆盖估算 */}
      <div className="text-xs text-[#008F11] bg-[#008F11]/10 border border-[#008F11]/30 p-2">
        预计覆盖约 <span className="text-[#00FF41] font-mono">{estimatedDays}</span> 天历史数据
        {timeframe === '5m' && (
          <span className="text-[#C724FF]">（高频数据量大，拉取耗时较长）</span>
        )}
      </div>

      {/* ── MEV 开关 ─────────────────────────────────────── */}
      <div className="border border-[#008F11]/30 p-3 flex flex-col gap-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={useMev}
            onChange={e => setUseMev(e.target.checked)}
            className="accent-[#00FFFF]"
          />
          <span className="text-xs text-[#00FFFF] uppercase tracking-wider">
            获取链上 MEV 数据
          </span>
        </label>
        {useMev && (
          <p className="text-xs text-[#008F11] leading-relaxed">
            使用 Flashbots Boost Relay 公开 API（无需 Key）。<br />
            拉取以太坊区块 MEV 提取价值，聚合为 {timeframe} 波动率信号。<br />
            <span className="text-[#C724FF]">
              覆盖约最近 30~60 天；BTC/SOL 使用 ETH MEV 作为跨资产代理。
            </span>
          </p>
        )}
      </div>

      {/* ── NLP 情绪开关 ──────────────────────────────────── */}
      <div className="border border-[#008F11]/30 p-3 flex flex-col gap-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={useNlp}
            onChange={e => setUseNlp(e.target.checked)}
            className="accent-[#C724FF]"
          />
          <span className="text-xs text-[#C724FF] uppercase tracking-wider">
            获取 WorldNews NLP 情绪
          </span>
        </label>
        {useNlp && (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-[#008F11] leading-relaxed">
              使用 WorldNewsAPI 拉取加密货币新闻，情绪分 [-1, 1]。<br />
              免费层每天 1000 次请求。
              <a
                href="https://worldnewsapi.com/register"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#00FFFF] underline ml-1"
              >
                申请 Key →
              </a>
            </p>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-[#C724FF]">WorldNewsAPI Key</span>
              <input
                type="password"
                placeholder="输入 API Key..."
                value={nlpKey}
                onChange={e => setNlpKey(e.target.value)}
                className="matrix-input w-full bg-[#050a05] text-xs"
              />
            </label>
          </div>
        )}
      </div>

      {/* 拉取按钮 */}
      <button
        onClick={handleFetch}
        disabled={loading}
        className="matrix-btn py-2 w-full"
      >
        {loading
          ? `[拉取中... ${useMev ? 'MEV ' : ''}${useNlp ? 'NLP ' : ''}]`
          : '[从 BINANCE 拉取数据]'
        }
      </button>

      {result && (
        <div className="text-xs text-[#00FF41] border border-[#00FF41]/30 p-2">
          ✓ {result}
        </div>
      )}
      {error && (
        <div className="text-xs text-[#C724FF] border border-[#C724FF]/30 p-2">
          ✗ {error}
        </div>
      )}
    </div>
  );
}
