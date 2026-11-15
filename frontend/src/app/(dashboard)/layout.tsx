import { MarketingNav, MarketingFooter } from "@/components/marketing-nav";
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <MarketingNav />
      {children}
      <MarketingFooter />
    </>
  );
}
