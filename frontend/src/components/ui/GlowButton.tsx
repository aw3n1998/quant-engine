interface GlowButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'danger';
  size?: 'sm' | 'md';
  fullWidth?: boolean;
  loading?: boolean;
}

export default function GlowButton({
  children,
  onClick,
  disabled = false,
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  loading = false,
}: GlowButtonProps) {
  const isDisabled = disabled || loading;

  const base = 'uppercase font-bold tracking-widest transition-all duration-200 border';
  const sizeClass = size === 'sm' ? 'py-1 px-3 text-caption' : 'py-2 px-4 text-body';
  const widthClass = fullWidth ? 'w-full' : '';

  const variantClass = variant === 'danger'
    ? 'border-accent-magenta text-accent-magenta hover:bg-accent-magenta hover:text-black shadow-[inset_0_0_10px_rgba(199,36,255,0.3)]'
    : 'border-accent-emerald text-accent-emerald hover:bg-accent-emerald hover:text-black shadow-[inset_0_0_10px_rgba(0,255,65,0.3)]';

  const disabledClass = isDisabled ? 'opacity-30 cursor-not-allowed shadow-none pointer-events-none' : 'cursor-pointer';

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isDisabled}
      className={`${base} ${sizeClass} ${widthClass} ${variantClass} ${disabledClass}`}
    >
      {loading ? (
        <span className="animate-glow-pulse">[···]</span>
      ) : children}
    </button>
  );
}
