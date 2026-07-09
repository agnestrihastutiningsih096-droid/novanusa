import { appConfig } from "@/lib/config";

export default function Topbar() {
  return (
    <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-6">
      <div className="min-w-0">
        <div className="text-xs font-medium uppercase leading-4 tracking-[0.14em] text-slate-400">
          Pusat operasi sales
        </div>
        <div className="truncate text-sm font-semibold leading-5 text-slate-950">{appConfig.name}</div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden h-8 w-56 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-xs text-slate-500 md:flex">
          Cari entitas
        </div>
        <div className="flex size-8 items-center justify-center rounded-full border border-slate-200 bg-white text-xs font-semibold text-slate-700">
          NN
        </div>
      </div>
    </header>
  );
}
