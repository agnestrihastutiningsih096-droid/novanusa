"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navigationItems, navigationSections } from "@/lib/navigation";

export default function Sidebar() {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") {
      return pathname === "/";
    }
    if (href === "/outreach") {
      return pathname === "/outreach";
    }
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <aside className="flex h-screen w-20 shrink-0 flex-col border-r border-slate-200 bg-white text-slate-950 md:w-64">
      <div className="border-b border-slate-200 px-4 py-4">
        <Link href="/" className="flex items-center gap-3" aria-label="NovaNusa Dashboard home">
          <span className="flex size-8 items-center justify-center rounded-md bg-slate-950 text-xs font-semibold tracking-[0.08em] text-white">
            NN
          </span>
          <span className="hidden min-w-0 md:block">
            <span className="block truncate text-sm font-semibold leading-5">NovaNusa</span>
            <span className="block truncate text-xs leading-4 text-slate-500">Procurement Intelligence</span>
          </span>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3" aria-label="Primary navigation">
        {navigationSections.map((section) => {
          const sectionItems = navigationItems.filter((item) => item.section === section.id);

          return (
            <div key={section.id} className="mb-4 last:mb-0">
              <div className="hidden px-2 pb-1.5 text-[11px] font-medium uppercase leading-4 tracking-[0.12em] text-slate-400 md:block">
                {section.label}
              </div>
              <div className="space-y-0.5">
                {sectionItems.map((item) => {
                  const active = isActive(item.href);

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      title={item.label}
                      className={`group flex h-9 items-center gap-2 rounded-md px-2 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400 ${
                        active ? "bg-slate-950 text-white" : "text-slate-600 hover:bg-slate-100 hover:text-slate-950"
                      }`}
                    >
                      <span
                        className={`flex size-5 shrink-0 items-center justify-center rounded border text-[10px] font-semibold leading-none transition-colors ${
                          active
                            ? "border-slate-800 bg-white text-slate-950"
                            : "border-slate-200 bg-slate-50 text-slate-500 group-hover:border-slate-300 group-hover:bg-white group-hover:text-slate-800"
                        }`}
                      >
                        {item.badge}
                      </span>
                      <span className="hidden truncate md:block">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="hidden border-t border-slate-200 px-4 py-3 md:block">
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
          <div className="text-xs font-medium leading-4 text-slate-700">Enterprise workspace</div>
          <div className="mt-0.5 text-[11px] leading-4 text-slate-500">Institution operations</div>
        </div>
      </div>
    </aside>
  );
}
