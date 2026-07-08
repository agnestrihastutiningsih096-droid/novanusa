export type NavigationSection = "main";

export type NavigationItem = {
  label: string;
  href: string;
  badge: string;
  section: NavigationSection;
};

export const navigationSections: Array<{ id: NavigationSection; label: string }> = [
  { id: "main", label: "Main" },
];

export const navigationItems: NavigationItem[] = [
  { label: "Home", href: "/", badge: "H", section: "main" },
  { label: "Prospect Queue", href: "/outreach/prospect-queue", badge: "PQ", section: "main" },
  { label: "Institutions", href: "/institutions", badge: "IN", section: "main" },
  { label: "Products", href: "/products", badge: "PR", section: "main" },
  { label: "Outreach", href: "/outreach", badge: "OU", section: "main" },
  { label: "CRM", href: "/crm", badge: "CR", section: "main" },
  { label: "Settings", href: "/settings", badge: "S", section: "main" },
];
