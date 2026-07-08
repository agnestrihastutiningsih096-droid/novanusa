import Link from "next/link";
import Card from "@/components/common/Card";
import Badge from "@/components/common/Badge";

type KPIProps = {
  label: string;
  value: string;
  detail: string;
  badge?: string;
  href?: string;
};

export default function KPI({ label, value, detail, badge, href }: KPIProps) {
  const card = (
    <Card className="p-5 transition-colors hover:bg-slate-50">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-slate-500">{label}</p>
          <p className="mt-3 text-2xl font-semibold tracking-normal text-slate-950">{value}</p>
        </div>
        {badge ? <Badge>{badge}</Badge> : null}
      </div>
      <p className="mt-3 text-sm leading-5 text-slate-500">{detail}</p>
    </Card>
  );

  if (!href) {
    return card;
  }

  return (
    <Link href={href} className="block rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-400">
      {card}
    </Link>
  );
}
