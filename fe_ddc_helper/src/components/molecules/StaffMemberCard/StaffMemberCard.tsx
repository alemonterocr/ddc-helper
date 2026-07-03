import { useState } from "react";
import type { StaffMember } from "../../../types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Field, FieldLabel } from "@/components/ui/field";
import { Pencil, X, User, Check } from "lucide-react";

interface StaffMemberCardProps {
  member: StaffMember;
  /** Index inside its department's array (for store updates). */
  index: number;
  onEdit: (index: number, patch: Partial<StaffMember>) => void;
  onDelete: (index: number) => void;
}

export function StaffMemberCard({
  member,
  index,
  onEdit,
  onDelete,
}: StaffMemberCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<StaffMember>(member);

  function startEdit() {
    setDraft(member);
    setEditing(true);
  }

  function save() {
    onEdit(index, {
      name: draft.name,
      title: draft.title,
      phone: draft.phone,
      email: draft.email,
      bio: draft.bio,
    });
    setEditing(false);
  }

  function cancel() {
    setEditing(false);
  }

  if (editing) {
    return (
      <div className="group flex flex-col gap-3 p-3 rounded-md border border-border bg-card">
        <Field>
          <FieldLabel htmlFor={`name-${index}`} className="text-xs">Name</FieldLabel>
          <Input
            id={`name-${index}`}
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="Full name"
          />
        </Field>
        <div className="flex gap-2">
          <Field>
            <FieldLabel htmlFor={`title-${index}`} className="text-xs">Title</FieldLabel>
            <Input
              id={`title-${index}`}
              value={draft.title ?? ""}
              onChange={(e) => setDraft({ ...draft, title: e.target.value || null })}
              placeholder="Sales Manager"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor={`phone-${index}`} className="text-xs">Phone</FieldLabel>
            <Input
              id={`phone-${index}`}
              value={draft.phone ?? ""}
              onChange={(e) => setDraft({ ...draft, phone: e.target.value || null })}
              placeholder="555-1234"
            />
          </Field>
        </div>
        <Field>
          <FieldLabel htmlFor={`email-${index}`} className="text-xs">Email</FieldLabel>
          <Input
            id={`email-${index}`}
            type="email"
            value={draft.email ?? ""}
            onChange={(e) => setDraft({ ...draft, email: e.target.value || null })}
            placeholder="jane@dealer.com"
          />
        </Field>
        <Field>
          <FieldLabel htmlFor={`bio-${index}`} className="text-xs">Bio</FieldLabel>
          <Textarea
            id={`bio-${index}`}
            value={draft.bio ?? ""}
            onChange={(e) => setDraft({ ...draft, bio: e.target.value || null })}
            placeholder="Short biography…"
            rows={3}
            className="min-h-16 max-h-40 resize-none"
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={cancel}>
            Cancel
          </Button>
          <Button size="sm" onClick={save} disabled={!draft.name.trim()}>
            <Check size={12} className="mr-1" /> Save
          </Button>
        </div>
      </div>
    );
  }

  // Read-only display
  return (
    <div className="group flex items-start gap-3 p-3 rounded-md border border-border bg-card hover:bg-accent/30 transition-colors">
      {/* Avatar */}
      <PhotoAvatar member={member} />

      {/* Body */}
      <div className="flex-1 min-w-0 flex flex-col gap-0.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-foreground truncate">
            {member.name || <span className="italic text-muted-foreground">unnamed</span>}
          </span>
          {!member.has_photo && (
            <Badge variant="outline" className="text-[10px] border-border text-muted-foreground">
              no photo
            </Badge>
          )}
        </div>
        {member.title && (
          <p className="text-xs text-muted-foreground truncate">{member.title}</p>
        )}
        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
          {member.phone && <span className="font-mono truncate">{member.phone}</span>}
          {member.email && (
            <span className="font-mono truncate" title={member.email}>
              {member.email}
            </span>
          )}
        </div>
        {member.bio && (
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{member.bio}</p>
        )}
      </div>

      {/* Hover actions */}
      <div className="shrink-0 flex flex-col gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={startEdit}
          title="Edit"
        >
          <Pencil size={12} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-destructive"
          onClick={() => onDelete(index)}
          title="Remove"
        >
          <X size={12} />
        </Button>
      </div>
    </div>
  );
}

function PhotoAvatar({ member }: { member: StaffMember }) {
  const [errored, setErrored] = useState(false);
  const url = member.photo || member.original_photo_url;
  if (!url || errored) {
    return (
      <div className="shrink-0 w-10 h-10 rounded-full bg-muted flex items-center justify-center">
        <User size={16} className="text-muted-foreground" />
      </div>
    );
  }
  return (
    <img
      src={url}
      alt={member.name}
      loading="lazy"
      onError={() => setErrored(true)}
      className="shrink-0 w-10 h-10 rounded-full object-cover"
    />
  );
}
