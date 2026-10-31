import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return (
    <main className="grid min-h-screen place-content-center px-6 text-center">
      <span className="mx-auto grid size-14 place-items-center rounded-2xl border bg-card text-muted-foreground">
        <SearchX size={26} strokeWidth={1.5} />
      </span>
      <p className="eyebrow mt-6">404 · Not found</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        This path leads nowhere.
      </h1>
      <p className="mt-4 max-w-sm text-sm leading-7 text-muted-foreground">
        The page may have moved, or this link doesn’t point to an existing
        resource.
      </p>
      <Button asChild className="mx-auto mt-7">
        <Link href="/dashboard">
          <ArrowLeft size={14} />
          Back to your workspace
        </Link>
      </Button>
    </main>
  );
}
