import { useState } from 'react';
import { fetchBinance } from '../services/api';
import TerminalSection from './ui/TerminalSection';
import GlowButton from './ui/GlowButton';
import NeonInput from './ui/NeonInput';

const SYMBOLS = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
  'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
];

const TIMEFRAMES = [
  { value: '1d',  label: '1D Daily' },
  { value: '4h',  label: '4H Swing' },
  { value: '1h',  label: '1H Intraday' },
  { value: '30m', label: '30M' },
  { value: '15m', label: '15M' },
  { value: '5m',  label: '5M HFT' },
];

const RECOMMENDED: Record<string, number> = {
  '1d': 90, '4h': 540, '1h': 2160, '30m': 4320, '15m': 8640, '5m': 25920,
};

const TF_HOURS: Record<string, number> = {
  '1d': 24, '4h': 4, '1h': 1, '30m': 0.5, '15m': 0.25, '5m': 1 / 12,
};

interface Props {
  onLoaded?: (info: { symbol: string; timeframe: string; rows: number; date_range: string }) => void;
}

export default function BinanceFetcher({ onLoaded }: Props) {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTf] = useState('1h');
  const [limit, setLimit] = useState(2160);
  const [useMev, setUseMev] = useState(false);
  const [useNlp, setUseNlp] = useState(false);
  const [nlpKey, setNlpKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleTfChange = (tf: string) => { setTf(tf); setLimit(RECOMMENDED[tf] ?? 1000); };
  const estimatedDays = Math.round((limit * (TF_HOURS[timeframe] || 1)) / 24);

  const handleFetch = async () => {
    setLoading(true); setResult(null); setError(null);
    try {
      const res = await fetchBinance({ symbol, timeframe, limit, use_mev: useMev, use_nlp: useNlp, worldnews_api_key: nlpKey });
      const tags = [res.mev_enabled ? 'MEV' : '', res.nlp_enabled ? 'NLP' : ''].filter(Boolean).join('+');
      setResult(`${res.symbol} ${res.timeframe} x ${res.rows} (${res.date_range})${tags ? ' [' + tags + ']' : ''}`);
      onLoaded?.({ symbol: res.symbol, timeframe: res.timeframe, rows: res.rows, date_range: res.date_range });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fetch failed');
    } finally { setLoading(false); }
  };

  return (
    <div className="flex flex-col gap-3">
      <NeonInput type="select" label="Symbol" value={symbol} onChange={setSymbol} layout="col"
        options={SYMBOLS.map(s => ({ value: s, label: s }))} />
      <NeonInput type="select" label="Timeframe" value={timeframe} onChange={handleTfChange} layout="col"
        options={TIMEFRAMES} />
      <NeonInput type="number" label="K-lines" value={limit} onChange={v => setLimit(Number(v))} min={100} max={100000} step={100} />

      <div className="text-caption text-text-secondary border border-border-dim p-2">
        Coverage: <span className="text-text-primary font-mono">{estimatedDays}</span> days
        {timeframe === '5m' && <span className="text-accent-magenta ml-1">(large dataset)</span>}
      </div>

      {/* MEV */}
      <label className="flex items-center gap-2 cursor-pointer text-caption">
        <input type="checkbox" checked={useMev} onChange={e => setUseMev(e.target.checked)} className="accent-accent-cyan" />
        <span className="text-accent-cyan uppercase tracking-wider">MEV Data (Flashbots, no key)</span>
      </label>

      {/* NLP */}
      <label className="flex items-center gap-2 cursor-pointer text-caption">
        <input type="checkbox" checked={useNlp} onChange={e => setUseNlp(e.target.checked)} className="accent-accent-magenta" />
        <span className="text-accent-magenta uppercase tracking-wider">NLP Sentiment (WorldNews)</span>
      </label>
      {useNlp && (
        <div className="pl-4 flex flex-col gap-2">
          <div className="text-caption text-accent-emerald">Default key configured in backend</div>
          <NeonInput type="password" label="Override Key" value={nlpKey} onChange={setNlpKey} layout="col" />
        </div>
      )}

      <GlowButton fullWidth onClick={handleFetch} loading={loading} disabled={loading}>
        [FETCH FROM BINANCE]
      </GlowButton>

      {result && <div className="text-caption text-accent-emerald border border-accent-emerald/30 p-2">{result}</div>}
      {error && <div className="text-caption text-accent-magenta border border-accent-magenta/30 p-2">{error}</div>}
    </div>
  );
}
