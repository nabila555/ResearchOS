import {
  BookOpen,
  FolderKanban,
  GitCompareArrows,
  LayoutDashboard,
  Library,
  type LucideIcon,
  MessageSquareText,
  Network,
  Quote,
  ScrollText,
  ScanSearch,
  Settings,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Roadmap phase that delivers the feature. Items with a phase > CURRENT_PHASE are not built yet. */
  phase: number;
  summary: string;
  planned: string[];
}

/** The phase whose features are fully implemented. */
export const CURRENT_PHASE = 6;

export const NAV_ITEMS: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: LayoutDashboard,
    phase: 1,
    summary: "Overview of your research library and projects.",
    planned: [],
  },
  {
    href: "/library",
    label: "Research Library",
    icon: Library,
    phase: 2,
    summary: "Import, organise, and search papers, articles, and notes.",
    planned: [],
  },
  {
    href: "/assistant",
    label: "AI Assistant",
    icon: MessageSquareText,
    phase: 3,
    summary: "Ask questions answered only from your own sources, with page-level citations.",
    planned: [],
  },
  {
    href: "/gaps",
    label: "Research Gap Finder",
    icon: ScanSearch,
    phase: 4,
    summary: "Find underexplored areas, contradictions, and open questions in a collection.",
    planned: [],
  },
  {
    href: "/compare",
    label: "Paper Comparison",
    icon: GitCompareArrows,
    phase: 4,
    summary: "Side-by-side structured comparison of selected papers.",
    planned: [],
  },
  {
    href: "/graph",
    label: "Knowledge Graph",
    icon: Network,
    phase: 5,
    summary: "Explore relationships between papers, authors, concepts, and methods.",
    planned: [],
  },
  {
    href: "/review",
    label: "Literature Review",
    icon: BookOpen,
    phase: 5,
    summary: "Organise sources by theme and draft a cited literature review.",
    planned: [],
  },
  {
    href: "/citations",
    label: "Citation Manager",
    icon: Quote,
    phase: 5,
    summary: "Format references and export bibliographies.",
    planned: [],
  },
  {
    href: "/projects",
    label: "Research Projects",
    icon: FolderKanban,
    phase: 1,
    summary: "Group your work around research questions.",
    planned: [],
  },
  {
    href: "/reports",
    label: "Reports",
    icon: ScrollText,
    phase: 6,
    summary: "Generated reports, with Markdown and PDF export.",
    planned: [],
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    phase: 1,
    summary: "Appearance, local storage, and AI provider status.",
    planned: [],
  },
];

export function isAvailable(item: NavItem) {
  return item.phase <= CURRENT_PHASE;
}

export function findNavItem(href: string) {
  return NAV_ITEMS.find((item) => item.href === href);
}
