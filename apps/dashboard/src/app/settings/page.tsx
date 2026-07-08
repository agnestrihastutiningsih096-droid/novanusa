import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import PageHeader from "@/components/common/PageHeader";
import { appConfig } from "@/lib/config";

export default function SettingsPage() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="p-6 md:p-7">
          <PageHeader
            eyebrow="Settings"
            title="Settings"
            description="Application settings for the single NovaNusa Dashboard."
            actions={<Badge tone="info">{appConfig.environment}</Badge>}
          />
        </Card>

        <Card className="p-5 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Application</p>
          <dl className="mt-4 grid gap-3 text-sm leading-6 text-slate-700 md:grid-cols-2">
            <div>
              <dt className="font-medium text-slate-950">Name</dt>
              <dd className="mt-1">{appConfig.title}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-950">Description</dt>
              <dd className="mt-1">{appConfig.description}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-950">URL</dt>
              <dd className="mt-1 break-all">{appConfig.url}</dd>
            </div>
            <div>
              <dt className="font-medium text-slate-950">API base URL</dt>
              <dd className="mt-1 break-all">{appConfig.apiBaseUrl}</dd>
            </div>
          </dl>
        </Card>
    </div>
  );
}
