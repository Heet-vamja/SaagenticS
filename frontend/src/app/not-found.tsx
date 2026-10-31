import Link from "next/link";
export default function NotFound() {
  return (
    <main className="grid min-h-screen place-content-center gap-4 text-center">
      <h1 className="text-3xl font-semibold">Page not found</h1>
      <Link className="text-primary underline" href="/">
        Return to your workspace
      </Link>
    </main>
  );
}
