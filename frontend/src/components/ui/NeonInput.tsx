interface NeonInputProps {
  type?: 'number' | 'text' | 'password' | 'range' | 'select';
  label?: string;
  tooltip?: string;
  value: string | number;
  onChange: (val: string) => void;
  options?: { value: string; label: string }[];
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
  layout?: 'row' | 'col';
  className?: string;
}

function LabelWithTooltip({ label, tooltip }: { label: string; tooltip?: string }) {
  return (
    <span className="flex items-center gap-1 text-text-secondary text-caption shrink-0">
      {label}
      {tooltip && (
        <span className="relative group cursor-help">
          <span className="text-text-muted text-[10px] border border-text-muted rounded-full w-3 h-3 flex items-center justify-center leading-none">?</span>
          <span className="absolute left-0 bottom-full mb-1 w-52 bg-bg-tertiary border border-border-base text-text-primary text-[10px] p-2 hidden group-hover:block z-50 leading-relaxed pointer-events-none">
            {tooltip}
          </span>
        </span>
      )}
    </span>
  );
}

export default function NeonInput({
  type = 'text',
  label,
  tooltip,
  value,
  onChange,
  options,
  min,
  max,
  step,
  suffix,
  layout = 'row',
  className = '',
}: NeonInputProps) {
  const isRow = layout === 'row';
  const wrapperClass = isRow
    ? 'flex items-center justify-between gap-2 text-body'
    : 'flex flex-col gap-1 text-body';

  const inputBase = 'bg-bg-input border border-border-bright text-text-primary font-mono outline-none px-2 py-1 text-body transition-all focus:border-text-primary focus:shadow-[0_0_8px_rgba(0,255,65,0.25)]';

  if (type === 'select') {
    return (
      <label className={`${wrapperClass} ${className}`}>
        {label && <LabelWithTooltip label={label} tooltip={tooltip} />}
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className={`${inputBase} ${isRow ? 'w-32' : 'w-full'}`}
        >
          {options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </label>
    );
  }

  if (type === 'range') {
    return (
      <label className={`flex flex-col gap-1 ${className}`}>
        {label && (
          <span className="text-caption flex justify-between items-center">
            <LabelWithTooltip label={label} tooltip={tooltip} />
            <span className="text-text-primary font-mono">{value}{suffix}</span>
          </span>
        )}
        <input
          type="range"
          value={value}
          onChange={e => onChange(e.target.value)}
          min={min}
          max={max}
          step={step}
        />
      </label>
    );
  }

  return (
    <label className={`${wrapperClass} ${className}`}>
      {label && <LabelWithTooltip label={label} tooltip={tooltip} />}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        min={min}
        max={max}
        step={step}
        className={`${inputBase} ${isRow ? 'w-24 text-right' : 'w-full'}`}
      />
    </label>
  );
}
