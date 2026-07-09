export type NavigationSection = "main";

export type NavigationItem = {
  label: string;
  href: string;
  badge: string;
  section: NavigationSection;
};

export const navigationSections: Array<{ id: NavigationSection; label: string }> = [
  { id: "main", label: "Utama" },
];

export const navigationItems: NavigationItem[] = [
  { label: "Beranda", href: "/", badge: "B", section: "main" },
  { label: "Prospek", href: "/outreach/prospect-queue", badge: "P", section: "main" },
  { label: "Institusi", href: "/institutions", badge: "IN", section: "main" },
  { label: "Produk", href: "/products", badge: "PR", section: "main" },
  { label: "Kontak", href: "/contact-master", badge: "KO", section: "main" },
  { label: "Outreach", href: "/outreach", badge: "OU", section: "main" },
  { label: "CRM", href: "/crm", badge: "CR", section: "main" },
  { label: "Bukti", href: "/evidence", badge: "BU", section: "main" },
  { label: "Pengaturan", href: "/settings", badge: "PG", section: "main" },
];