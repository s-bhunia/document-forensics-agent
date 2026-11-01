export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" className="fill-indigo-600 dark:fill-indigo-500" />
      <path
        d="M10 8h7.5a6.5 6.5 0 0 1 0 13H14v3h-4z"
        fill="none"
        stroke="#fff"
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <circle cx="17" cy="14.5" r="2.5" fill="#c7d2fe" />
    </svg>
  );
}
