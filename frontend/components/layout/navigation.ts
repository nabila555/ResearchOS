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
export const CURRENT_PHASE = 2;

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
    planned: [
      "Local models through Ollama; optional Claude API with explicit consent",
      "Local embeddings and vector search over page-aware chunks",
      "Every answer cites document and page; says so when evidence is insufficient",
    ],
  },
  {
    href: "/gaps",
    label: "Research Gap Finder",
    icon: ScanSearch,
    phase: 4,
    summary: "Find underexplored areas, contradictions, and open questions in a collection.",
    planned: [
      "Underexplored areas, contradictory findings, missing perspectives",
      "Methodological limitations and candidate research questions",
      "AI hypotheses clearly separated from literature-supported conclusions",
    ],
  },
  {
    href: "/compare",
    label: "Paper Comparison",
    icon: GitCompareArrows,
    phase: 4,
    summary: "Side-by-side structured comparison of selected papers.",
    planned: [
      "Objectives, questions, methods, datasets, sample sizes, findings, limitations",
      "Each cell linked to the supporting passage, or marked “not reported”",
      "Research Paper Detective: per-paper analytical observations",
    ],
  },
  {
    href: "/graph",
    label: "Knowledge Graph",
    icon: Network,
    phase: 5,
    summary: "Explore relationships between papers, authors, concepts, and methods.",
    planned: [
      "Interactive React Flow graph of papers, authors, topics, methods, and findings",
      "Filter by node type, focus on a node’s neighbourhood",
    ],
  },
  {
    href: "/review",
    label: "Literature Review",
    icon: BookOpen,
    phase: 5,
    summary: "Organise sources by theme and draft a cited literature review.",
    planned: [
      "Themes and grouped studies, thematic summaries, disagreements",
      "Structured outlines; every claim linked to sources",
      "Export to Markdown",
    ],
  },
  {
    href: "/citations",
    label: "Citation Manager",
    icon: Quote,
    phase: 5,
    summary: "Format references and export bibliographies.",
    planned: [
      "APA 7, MLA, Chicago, and IEEE formatting",
      "Copy citations, generate bibliographies, export BibTeX",
      "Missing fields are flagged, never invented",
    ],
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
