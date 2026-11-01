"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/form-controls";
import { useLibraryMutation } from "@/hooks/use-research-data";
import { collectionService } from "@/services/researchos";
import type { Collection } from "@/types/api";

interface CollectionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  collection?: Collection;
  onDeleted?: () => void;
}

export function CollectionDialog({ open, onOpenChange, collection, onDeleted }: CollectionDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={collection ? "Edit collection" : "New collection"}
        description="Collections group related sources. A document can belong to several."
      >
        {open ? (
          <CollectionForm
            collection={collection}
            onDone={() => onOpenChange(false)}
            onDeleted={onDeleted}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function CollectionForm({
  collection,
  onDone,
  onDeleted,
}: {
  collection?: Collection;
  onDone: () => void;
  onDeleted?: () => void;
}) {
  const [name, setName] = useState(collection?.name ?? "");
  const [description, setDescription] = useState(collection?.description ?? "");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const save = useLibraryMutation((input: { name: string; description: string | null }) =>
    collection ? collectionService.update(collection.id, input) : collectionService.create(input.name, input.description),
  );
  const remove = useLibraryMutation((id: number) => collectionService.remove(id));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await save.mutateAsync({ name: name.trim(), description: description.trim() || null });
      toast.success(collection ? "Collection updated" : "Collection created");
      onDone();
    } catch {
      // shown inline
    }
  }

  async function handleDelete() {
    if (!collection) return;
    try {
      await remove.mutateAsync(collection.id);
      toast.success(`Deleted “${collection.name}”`);
      onDone();
      onDeleted?.();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete collection");
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <Label htmlFor="collection-name">Name</Label>
        <Input id="collection-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} required autoFocus />
      </div>
      <div>
        <Label htmlFor="collection-description">Description</Label>
        <Textarea
          id="collection-description"
          rows={2}
          maxLength={2000}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Optional"
        />
      </div>
      {save.error ? (
        <p role="alert" className="text-[13px] text-danger">
          {save.error.message}
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-2 pt-1">
        {collection ? (
          confirmDelete ? (
            <div className="flex items-center gap-2 text-[13px]">
              <span className="text-muted-foreground">Documents are kept.</span>
              <Button type="button" size="sm" variant="danger" onClick={handleDelete} disabled={remove.isPending}>
                Confirm delete
              </Button>
            </div>
          ) : (
            <Button type="button" size="sm" variant="ghost" className="hover:text-danger" onClick={() => setConfirmDelete(true)}>
              Delete collection
            </Button>
          )
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <DialogClose asChild>
            <Button type="button" variant="ghost">
              Cancel
            </Button>
          </DialogClose>
          <Button type="submit" variant="primary" disabled={save.isPending || !name.trim()}>
            {save.isPending ? "Saving…" : collection ? "Save" : "Create"}
          </Button>
        </div>
      </div>
    </form>
  );
}
