"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/form-controls";
import { useLibraryMutation } from "@/hooks/use-research-data";
import { documentService } from "@/services/researchos";
import type { DocumentDetail, DocumentUpdate } from "@/types/api";

export function MetadataDialog({
  doc,
  open,
  onOpenChange,
}: {
  doc: DocumentDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="Edit details"
        description="Correct anything that was detected wrongly. Leave unknown fields empty rather than guessing."
        className="max-w-2xl"
      >
        {open ? <MetadataForm doc={doc} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function MetadataForm({ doc, onDone }: { doc: DocumentDetail; onDone: () => void }) {
  const [title, setTitle] = useState(doc.title);
  const [authors, setAuthors] = useState(doc.authors.join("\n"));
  const [year, setYear] = useState(doc.publication_year?.toString() ?? "");
  const [venue, setVenue] = useState(doc.venue ?? "");
  const [doi, setDoi] = useState(doc.doi ?? "");
  const [keywords, setKeywords] = useState(doc.keywords.join(", "));
  const [abstract, setAbstract] = useState(doc.abstract ?? "");
  const save = useLibraryMutation((input: DocumentUpdate) => documentService.update(doc.id, input));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const input: DocumentUpdate = {
      title: title.trim(),
      authors: authors.split("\n").map((a) => a.trim()).filter(Boolean),
      publication_year: year ? Number(year) : null,
      venue: venue.trim() || null,
      doi: doi.trim() || null,
      keywords: keywords.split(/[,;]/).map((k) => k.trim()).filter(Boolean),
      abstract: abstract.trim() || null,
    };
    try {
      await save.mutateAsync(input);
      toast.success("Details saved");
      onDone();
    } catch {
      // shown inline
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label htmlFor="meta-title">Title</Label>
        <Input id="meta-title" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={500} required />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="meta-authors">Authors (one per line)</Label>
          <Textarea id="meta-authors" rows={4} value={authors} onChange={(e) => setAuthors(e.target.value)} />
        </div>
        <div className="space-y-4">
          <div>
            <Label htmlFor="meta-year">Publication year</Label>
            <Input
              id="meta-year"
              inputMode="numeric"
              value={year}
              onChange={(e) => setYear(e.target.value.replace(/\D/g, "").slice(0, 4))}
              placeholder="Unknown"
            />
          </div>
          <div>
            <Label htmlFor="meta-venue">Journal / venue</Label>
            <Input id="meta-venue" value={venue} onChange={(e) => setVenue(e.target.value)} maxLength={500} />
          </div>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor="meta-doi">DOI</Label>
          <Input id="meta-doi" value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="10.xxxx/…" maxLength={255} />
        </div>
        <div>
          <Label htmlFor="meta-keywords">Keywords (comma-separated)</Label>
          <Input id="meta-keywords" value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        </div>
      </div>
      <div>
        <Label htmlFor="meta-abstract">Abstract</Label>
        <Textarea id="meta-abstract" rows={5} value={abstract} onChange={(e) => setAbstract(e.target.value)} />
      </div>
      {save.error ? (
        <p role="alert" className="text-[13px] text-danger">
          {save.error.message}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <DialogClose asChild>
          <Button type="button" variant="ghost">
            Cancel
          </Button>
        </DialogClose>
        <Button type="submit" variant="primary" disabled={save.isPending || !title.trim()}>
          {save.isPending ? "Saving…" : "Save details"}
        </Button>
      </div>
    </form>
  );
}
