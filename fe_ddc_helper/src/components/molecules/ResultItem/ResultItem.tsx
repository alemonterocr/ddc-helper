import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { Badge } from "@/components/ui/badge";

interface ResultItemProps {
  title: string;
  description: string;
  projectStatus: "Finished" | "In Progress";
  onClick?: () => void;
}

export default function ResultItem({
  title,
  description,
  projectStatus,
  onClick,
}: ResultItemProps) {
  return (
    <Item
      variant="muted"
      onClick={onClick}
      className={onClick ? "cursor-pointer hover:bg-muted transition-colors" : ""}
    >
      <ItemContent className="px-4">
        <ItemTitle>{title}</ItemTitle>
        <ItemDescription>{description}</ItemDescription>
      </ItemContent>
      <ItemActions>
        <Badge>{projectStatus}</Badge>
      </ItemActions>
    </Item>
  );
}
