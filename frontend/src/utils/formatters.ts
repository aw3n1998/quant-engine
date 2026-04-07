// frontend/src/utils/formatters.ts

export function formatPercent(value: number): string {
  return (value * 100).toFixed(2) + "%";
}

export function formatNumber(value: number, decimals: number = 3): string {
  return value.toFixed(decimals);
}

export function formatTimestamp(): string {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

export function truncateText(text: string, maxLength: number = 60): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function classNames(...classes: (string | boolean | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
