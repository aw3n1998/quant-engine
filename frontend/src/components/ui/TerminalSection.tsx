import { useState, type ReactNode } from 'react';

interface TerminalSectionProps {
  title: ReactNode;
  accent?: 'cyan' | 'magenta' | 'emerald';
  collapsible?: boolean;
  defaultOpen?: boolean;
  children: React.ReactNode;
}

const ACCENT_MAP = {
  cyan: 'text-accent-cyan border-accent-cyan/40',
  magenta: 'text-accent-magenta border-accent-magenta/40',
  emerald: 'text-accent-emerald border-accent-emerald/40',
};

export default function TerminalSection({
  title,
  accent = 'cyan',
  collapsible = false,
  defaultOpen = true,
  children,
}: TerminalSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const accentCls = ACCENT_MAP[accent];
  const titleColor = accentCls.split(' ')[0];

  return (
    <section className={`border ${accentCls.split(' ')[1] || 'border-border-base'} bg-bg-secondary`}>
      <button
        type="button"
        onClick={() => collapsible && setOpen(!open)}
        className={`w-full flex items-center gap-2 px-3 py-2 text-heading uppercase tracking-widest ${titleColor} ${collapsible ? 'cursor-pointer hover:bg-bg-tertiary' : 'cursor-default'} transition-colors focus:outline-none overflow-hidden`}
      >
        {collapsible && (
          <span className="text-caption transition-transform duration-200 flex-shrink-0" style={{ transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}>
            ▸
          </span>
        )}
        <span className="text-left flex items-center gap-1" style={{ minWidth: 0 }}>[ {title} ]</span>
      </button>
      {(!collapsible || open) && (
        <div className="px-3 pb-3 pt-1 animate-fade-in">
          {children}
        </div>
      )}
    </section>
  );
}
