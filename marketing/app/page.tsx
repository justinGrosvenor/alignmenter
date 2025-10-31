import { Hero } from "../components/hero";
import { ProblemSolution } from "../components/problem-solution";
import { MetricsShowcase } from "../components/metrics-showcase";
import { CLIPreview } from "../components/cli-preview";
import { UseCases } from "../components/use-cases";
import { TrustSection } from "../components/trust-section";
import { CTASection } from "../components/cta-section";
import { Footer } from "../components/footer";

export default function Home() {
  return (
    <>
      <Hero />
      <ProblemSolution />
      <MetricsShowcase />
      <CLIPreview />
      <UseCases />
      <TrustSection />
      <div className="min-h-screen snap-start snap-always flex flex-col">
        <CTASection />
        <Footer />
      </div>
    </>
  );
}
