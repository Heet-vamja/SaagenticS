"use client";
import { useState } from "react";
import { ArrowRight, Globe2, LoaderCircle, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { InlineError } from "./states";
export function ProjectDialog({
  onCreated,
}: {
  onCreated: (project: Project) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button onClick={() => setError("")}>
          <Plus size={14} />
          New project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <span className="mb-5 grid size-11 place-items-center rounded-xl border bg-accent-soft text-signal">
          <Globe2 size={21} />
        </span>
        <DialogTitle className="text-xl font-semibold tracking-tight">
          A home for your website.
        </DialogTitle>
        <DialogDescription className="mb-6 mt-2 text-xs leading-6 text-muted-foreground">
          Create a project to keep website scans and agent executions together.
        </DialogDescription>
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            setBusy(true);
            setError("");
            try {
              let url = String(form.get("url")).trim();
              if (!/^https?:\/\//i.test(url)) url = `https://${url}`;
              const project = await api.createProject(
                String(form.get("name")),
                url,
              );
              onCreated(project);
              setOpen(false);
            } catch (e) {
              setError(
                e instanceof Error ? e.message : "Could not create project",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <label className="block text-xs font-medium">
            Project name
            <input
              name="name"
              required
              maxLength={200}
              placeholder="Your product"
              className="field mt-2"
            />
          </label>
          <label className="block text-xs font-medium">
            Website URL
            <input
              name="url"
              inputMode="url"
              required
              maxLength={2048}
              placeholder="https://yourwebsite.com"
              className="field mt-2"
            />
          </label>
          {error && <InlineError>{error}</InlineError>}
          <Button className="w-full" disabled={busy}>
            {busy ? (
              <>
                <LoaderCircle className="animate-spin" size={14} />
                Creating project…
              </>
            ) : (
              <>
                Create project
                <ArrowRight size={14} />
              </>
            )}
          </Button>
          <p className="text-center text-[12px] leading-5 text-muted-foreground">
            Creating a project does not start a scan.
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}
