const useCases = [
  {
    persona: "ML Engineer",
    title: "Test before you ship",
    scenario:
      "Run brand voice, safety, and consistency checks before each release. Compare GPT-4o vs Claude on real conversations. Catch problems automatically in your build pipeline.",
    outcomes: ["Stop regressions", "Compare models", "Automate testing"],
  },
  {
    persona: "Product Manager",
    title: "Keep your brand voice consistent",
    scenario:
      "Sync your Custom GPT instructions into Alignmenter, make sure every release stays on-brand, and track voice consistency over time. Optional LLM judge analysis explains exactly what's on or off-brand. Share easy-to-read HTML reports with your team.",
    outcomes: ["Protect brand voice", "Get qualitative feedback", "Share with stakeholders"],
  },
  {
    persona: "AI Safety Team",
    title: "Safety and compliance checks",
    scenario:
      "Use keyword filters plus AI judges to catch safety issues. Control spending with budget limits. Export complete audit trails for compliance reviews.",
    outcomes: ["Reduce risk", "Control costs", "Audit documentation"],
  },
  {
    persona: "Researcher",
    title: "Run repeatable experiments",
    scenario:
      "Test how well different models match specific personalities. Every run produces the same results with saved outputs. Build custom tests and share them with others.",
    outcomes: ["Repeatable results", "Custom metrics", "Share findings"],
  },
];

export function UseCases() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 min-h-screen snap-start snap-always flex items-center">
      <div className="max-w-6xl mx-auto space-y-8 sm:space-y-12 md:space-y-16 w-full">
        <div className="text-center space-y-3 sm:space-y-4 px-4">
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white">
            Built for your workflow
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-slate-300 max-w-3xl mx-auto">
            Whether you&rsquo;re validating releases, monitoring brand voice, or conducting research,
            Alignmenter integrates into your process.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-6 sm:gap-8">
          {useCases.map((useCase) => (
            <div
              key={useCase.title}
              className="group relative rounded-2xl sm:rounded-3xl border border-slate-800 bg-slate-950/70 p-6 sm:p-8 shadow-lg shadow-black/30 backdrop-blur transition-all hover:border-slate-700"
            >
              <div className="space-y-3 sm:space-y-4">
                <div>
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-signal/10 border border-signal/20 text-signal text-xs font-medium mb-2 sm:mb-3">
                    {useCase.persona}
                  </div>
                  <h3 className="text-xl sm:text-2xl font-bold text-white mb-2 sm:mb-3">
                    {useCase.title}
                  </h3>
                  <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                    {useCase.scenario}
                  </p>
                </div>

                <div className="pt-3 sm:pt-4 border-t border-slate-800">
                  <div className="flex flex-wrap gap-2">
                    {useCase.outcomes.map((outcome) => (
                      <span
                        key={outcome}
                        className="px-2.5 sm:px-3 py-1 rounded-full bg-slate-900 text-slate-400 text-xs font-medium"
                      >
                        {outcome}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
