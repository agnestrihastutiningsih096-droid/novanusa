"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Badge from "@/components/common/Badge";
import Card from "@/components/common/Card";
import { formatIdr, splitList, type Prospect } from "@/lib/institution-utils";

type ContactFilter = "ALL" | "FOUND" | "MISSING";
type EvidenceFilter = "ALL" | "SIRUP_PLANNING_ONLY";

type InstitutionsClientProps = {
  institutions: Prospect[];
  initialContactFilter?: ContactFilter;
  initialEvidenceFilter?: EvidenceFilter;
};

const pageSize = 25;
const contactFilters: Array<{ label: string; value: ContactFilter }> = [
  { label: "All", value: "ALL" },
  { label: "Contact Found", value: "FOUND" },
  { label: "Contact Missing", value: "MISSING" },
];

function hasContactEmail(institution: Prospect) {
  return institution.contact_email.trim().length > 0;
}

function contactPriority(institution: Prospect) {
  return hasContactEmail(institution) ? 0 : 1;
}

export default function InstitutionsClient({
  institutions,
  initialContactFilter = "ALL",
  initialEvidenceFilter = "ALL",
}: InstitutionsClientProps) {
  const router = useRouter();
  const [contactFilter, setContactFilter] = useState<ContactFilter>(initialContactFilter);
  const [evidenceFilter] = useState<EvidenceFilter>(initialEvidenceFilter);
  const [query, setQuery] = useState("");
  const [visibleCount, setVisibleCount] = useState(pageSize);

  const filteredInstitutions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return institutions
      .map((institution, index) => ({ institution, index }))
      .filter(({ institution }) => {
        const contactFound = hasContactEmail(institution);
        const matchesContact =
          contactFilter === "ALL" ||
          (contactFilter === "FOUND" && contactFound) ||
          (contactFilter === "MISSING" && !contactFound);
        const matchesEvidence = evidenceFilter === "ALL" || institution.evidence_status === evidenceFilter;
        const searchText = [
          institution.institution_display_name,
          institution.institution_name,
          institution.parent_organization,
          institution.work_unit,
          institution.province_or_region,
          institution.location_hint,
          institution.relevant_categories,
          institution.contact_email,
        ]
          .join(" ")
          .toLowerCase();
        const matchesQuery = !normalizedQuery || searchText.includes(normalizedQuery);

        return matchesContact && matchesEvidence && matchesQuery;
      })
      .sort((left, right) => {
        const priority = contactPriority(left.institution) - contactPriority(right.institution);
        return priority || left.index - right.index;
      })
      .map(({ institution }) => institution);
  }, [contactFilter, evidenceFilter, institutions, query]);

  const visibleInstitutions = filteredInstitutions.slice(0, visibleCount);

  function updateContactFilter(value: ContactFilter) {
    setContactFilter(value);
    setVisibleCount(pageSize);
  }

  function updateQuery(value: string) {
    setQuery(value);
    setVisibleCount(pageSize);
  }

  function openInstitution(institutionId: string) {
    router.push(`/institutions/${institutionId}`);
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-slate-200/80 px-5 py-4 md:px-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">Institution list</p>
              <h2 className="mt-1 text-base font-semibold text-slate-950">Workspace-ready records</h2>
              <p className="mt-1 text-sm text-slate-600">
                Showing {visibleInstitutions.length.toLocaleString("id-ID")} of {filteredInstitutions.length.toLocaleString("id-ID")} filtered records. Contact email records are listed first.
              </p>
            </div>
            <Link href="/outreach/prospect-queue" className="inline-flex h-9 items-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50">Open Prospect Queue</Link>
          </div>

          <div className="grid gap-3 lg:grid-cols-[1fr_auto] lg:items-end">
            <label className="flex flex-col gap-1.5 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              Search institutions
              <input
                value={query}
                onChange={(event) => updateQuery(event.target.value)}
                placeholder="Search name, region, category, or contact email..."
                className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium normal-case tracking-normal text-slate-800 outline-none transition focus:border-blue-300 focus:ring-4 focus:ring-blue-100"
              />
            </label>

            <div className="flex flex-wrap gap-2" aria-label="Contact filter">
              {contactFilters.map((filter) => (
                <button
                  key={filter.value}
                  type="button"
                  onClick={() => updateContactFilter(filter.value)}
                  className={`h-10 rounded-md border px-3 text-sm font-medium ${
                    contactFilter === filter.value ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  {filter.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1280px] border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
            <tr>
              <th className="border-b border-slate-200 px-5 py-3">Institution</th>
              <th className="border-b border-slate-200 px-5 py-3">Region</th>
              <th className="border-b border-slate-200 px-5 py-3">Category</th>
              <th className="border-b border-slate-200 px-5 py-3">Packages</th>
              <th className="border-b border-slate-200 px-5 py-3">Pagu</th>
              <th className="border-b border-slate-200 px-5 py-3">Contact</th>
              <th className="border-b border-slate-200 px-5 py-3">Workspace</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200/80 bg-white">
            {visibleInstitutions.map((institution) => (
              <tr
                key={institution.institution_id}
                role="link"
                tabIndex={0}
                onClick={() => openInstitution(institution.institution_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openInstitution(institution.institution_id);
                  }
                }}
                className="cursor-pointer align-top transition-colors hover:bg-slate-50/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-blue-300"
              >
                <td className="max-w-[360px] px-5 py-4">
                  <span className="font-medium text-slate-950 underline-offset-4 group-hover:text-blue-700">
                    {institution.institution_display_name}
                  </span>
                  <p className="mt-1 text-xs leading-5 text-slate-500">{institution.parent_organization || institution.work_unit}</p>
                </td>
                <td className="px-5 py-4 text-slate-600">{institution.province_or_region || "Not provided"}</td>
                <td className="max-w-[280px] px-5 py-4 text-slate-600">{splitList(institution.relevant_categories).join(", ") || "Not categorized"}</td>
                <td className="px-5 py-4 text-slate-700">{institution.total_relevant_packages.toLocaleString("id-ID")}</td>
                <td className="whitespace-nowrap px-5 py-4 text-slate-700">{formatIdr(institution.total_pagu)}</td>
                <td className="max-w-[260px] px-5 py-4">
                  {hasContactEmail(institution) ? (
                    <div className="space-y-2">
                      <p className="break-all text-sm font-medium text-slate-950">{institution.contact_email}</p>
                      <Badge tone="success">{institution.contact_status || "CONTACT_FOUND"}</Badge>
                    </div>
                  ) : (
                    <span className="text-sm text-slate-500">CONTACT_MISSING</span>
                  )}
                </td>
                <td className="px-5 py-4">
                  <span className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2.5 text-xs font-medium text-slate-700">Open</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 border-t border-slate-200/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between md:px-6">
        <p className="text-sm text-slate-600">
          {filteredInstitutions.length === 0 ? "No institutions match the current filters." : `${visibleInstitutions.length.toLocaleString("id-ID")} visible of ${filteredInstitutions.length.toLocaleString("id-ID")}`}
        </p>
        {visibleCount < filteredInstitutions.length ? (
          <button
            type="button"
            onClick={() => setVisibleCount((current) => current + pageSize)}
            className="inline-flex h-9 items-center justify-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Show more
          </button>
        ) : null}
      </div>
    </Card>
  );
}
