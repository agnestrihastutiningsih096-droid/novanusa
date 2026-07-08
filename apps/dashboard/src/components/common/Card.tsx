import type { HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  tone?: "default" | "muted";
};

export default function Card({ children, className = "", tone = "default", ...props }: CardProps) {
  const toneClass = tone === "muted" ? "bg-slate-50/80" : "bg-white";

  return (
    <div
      className={`rounded-lg border border-slate-200/80 ${toneClass} shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
