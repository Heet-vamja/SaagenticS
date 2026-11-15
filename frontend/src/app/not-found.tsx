import Link from "next/link";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Brand } from "@/components/product-ui";
export default function NotFound() {
  return (
    <main
      id="main-content"
      className="flex min-h-screen flex-col items-center px-5 py-8 text-center"
    >
      <Brand />
      <div className="my-auto flex flex-col items-center py-16">
        <p
          aria-hidden="true"
          className="font-display text-[clamp(7rem,28vw,13rem)] font-extrabold leading-none tracking-[-.035em] text-primary"
        >
          4<span className="mark-lime mx-[.04em]">0</span>4
        </p>
        <p className="chip mt-8">
          <span className="chip-dot" aria-hidden="true" />
          404 · Not found
        </p>
        <h1 className="display-md mt-5 max-w-[18ch]">
          This path leads nowhere.
        </h1>
        <p className="lede mt-4 max-w-md">
          The page may have moved, or this link doesn’t point to an existing
          resource.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/">
              <ArrowLeft size={16} />
              Back to home
            </Link>
          </Button>
          <Button asChild size="lg" variant="secondary">
            <Link href="/docs">
              Read the docs
              <ArrowRight size={16} />
            </Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
