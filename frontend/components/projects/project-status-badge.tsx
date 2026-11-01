import { Badge } from "@/components/ui/badge";
import type { ProjectStatus } from "@/types/api";

const TONES = {
  active: "accent",
  paused: "warning",
  completed: "success",
  archived: "neutral",
} as const;

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge tone={TONES[status]} className="capitalize">
      {status}
    </Badge>
  );
}
