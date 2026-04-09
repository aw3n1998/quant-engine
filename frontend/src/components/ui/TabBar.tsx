interface Tab {
  id: string;
  label: string;
}

interface TabBarProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
}

export default function TabBar({ tabs, active, onChange }: TabBarProps) {
  return (
    <div className="flex border-b border-border-base">
      {tabs.map(tab => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`px-4 py-2 text-caption uppercase tracking-widest transition-all relative ${
              isActive
                ? 'text-accent-emerald'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {tab.label}
            {isActive && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-accent-emerald shadow-[0_0_8px_#00FF41]" />
            )}
          </button>
        );
      })}
    </div>
  );
}
