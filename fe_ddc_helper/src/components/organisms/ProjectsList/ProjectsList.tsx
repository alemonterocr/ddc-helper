import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/ui/field";
import { useEffect, useState } from "react";
import ResultItem from "@/components/molecules/ResultItem/ResultItem";
import type { BaseProject } from "@/store/types.ts";

interface ProjectsListProps {
  projectList: BaseProject[];
  onSearch: (query: string) => BaseProject[];
  onItemClick?: (project: BaseProject) => void;
  title: string;
  searchLabel: string;
  notFoundMessage: string;
}

export default function ProjectsList({
  projectList,
  onSearch,
  onItemClick,
  title,
  searchLabel,
  notFoundMessage,
}: ProjectsListProps) {
  const [projectItems, setProjectItems] = useState<BaseProject[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [hasSearched, setHasSearched] = useState(false);

  const calculateElapsedDays = (startDate: Date, endDate: Date): number => {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const differenceInSeconds = Math.floor(
      (end.getTime() - start.getTime()) / 1000,
    );
    const differenceInDays = Math.floor(
      Math.floor(differenceInSeconds / 3600) / 24,
    );
    return differenceInDays;
  };

  const getElapsedTime = (project: BaseProject): string => {
    const today = new Date();
    if (!project.finishedDate && project.status == "Finished") {
      const end = new Date(project.finishedDate!);
      const differenceInDays = calculateElapsedDays(end, today);
      return `Finished ${differenceInDays} days ago`;
    } else {
      const start = new Date(project.createdAt);
      const differenceInDays = calculateElapsedDays(start, today);
      return `Started ${differenceInDays} days ago`;
    }
  };

  useEffect(() => {
    setProjectItems(projectList);
    setHasSearched(false);
    setSearchQuery("");
  }, [projectList]);

  const isEmpty = projectList.length === 0;

  return (
    <section
      aria-label={title}
      className="flex flex-col min-w-0 gap-4 rounded-lg border border-border bg-card p-6"
    >
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const result = onSearch(searchQuery);
          setProjectItems(result);
          setHasSearched(true);
        }}
      >
        <Field orientation="horizontal">
          <Input
            type="search"
            placeholder={searchLabel}
            className="min-w-0 flex-1"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            disabled={isEmpty}
          />
          <Button type="submit" size="sm" disabled={isEmpty}>
            Search
          </Button>
        </Field>
      </form>

      {isEmpty ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          {notFoundMessage}
        </p>
      ) : hasSearched && projectItems.length === 0 ? (
        <p className="text-sm text-muted-foreground py-6 text-center">
          0 results for{" "}
          <span className="text-foreground font-mono">{searchQuery}</span>
        </p>
      ) : (
        <div className="flex flex-col gap-2 overflow-y-auto max-h-[60vh] scrollbar-thin">
          {projectItems.map((project) => (
            <ResultItem
              key={project.id}
              title={project.dealerId}
              description={getElapsedTime(project)}
              projectStatus={project.status}
              onClick={onItemClick ? () => onItemClick(project) : undefined}
            />
          ))}
        </div>
      )}
    </section>
  );
}
