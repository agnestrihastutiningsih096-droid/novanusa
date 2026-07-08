import type { InputHTMLAttributes } from "react";

type SearchBoxProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
};

export default function SearchBox({ className = "", label = "Search", ...props }: SearchBoxProps) {
  return (
    <label className={`block ${className}`}>
      <span className="sr-only">{label}</span>
      <span className="flex h-11 items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition-colors focus-within:border-slate-400 focus-within:ring-4 focus-within:ring-slate-200/70">
        <span className="relative size-4 shrink-0" aria-hidden="true">
          <span className="absolute left-0 top-0 size-3 rounded-full border border-slate-400" />
          <span className="absolute bottom-0 right-0 h-2 w-px rotate-[-45deg] rounded-full bg-slate-400" />
        </span>
        <input
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-950 outline-none placeholder:text-slate-400"
          type="search"
          {...props}
        />
      </span>
    </label>
  );
}
