interface NeonInputProps {
  type?: 'number' | 'text' | 'password' | 'range' | 'select';
  label?: string;
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

export default function NeonInput({
  type = 'text',
  label,
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
        {label && <span className="text-text-secondary text-caption">{label}</span>}
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
          <span className="text-text-secondary text-caption flex justify-between">
            <span>{label}</span>
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
      {label && <span className="text-text-secondary text-caption">{label}</span>}
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
