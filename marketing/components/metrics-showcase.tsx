const metrics = [
  {
    name: "Authenticity",
    tagline: "Does it sound like your brand?",
    description:
      "Checks if AI responses match your brand&rsquo;s voice and personality. Compares writing style, tone, and word choices against examples you provide. Optional LLM judge adds qualitative analysis with human-readable explanations.",
    formula: "0.6 × style_sim + 0.25 × traits + 0.15 × lexicon",
    features: [
      "Compares writing style to your brand examples",
      "Checks personality traits match your tone",
      "Flags words and phrases that feel off-brand",
      "Optional LLM judge explains strengths and weaknesses",
      "Cost-optimized sampling strategies (90% savings)",
      "Syncs instructions from your custom GPTs",
    ],
    color: "signal",
  },
  {
    name: "Safety",
    tagline: "Catch harmful responses early",
    description:
      "Combines keyword filters with AI judges to find safety issues. Set spending limits for AI reviewers and get offline backups when you need them. Tracks how well different checks agree.",
    formula: "min(1 - violation_rate, judge_score)",
    features: [
      "Pattern matching catches obvious problems fast",
      "AI judges review complex cases within your budget",
      "Tracks agreement between different safety checks",
      "Works offline with local safety models",
    ],
    color: "blue-500",
  },
  {
    name: "Stability",
    tagline: "Spot unexpected behavior changes",
    description:
      "Measures if your AI stays consistent. Flags when responses vary wildly in a single session. Compares versions to catch changes between releases you didn&rsquo;t intend.",
    formula: "1 - normalized_variance(embeddings)",
    features: [
      "Finds inconsistent responses within conversations",
      "Compares old and new model versions automatically",
      "Set custom thresholds for when to warn you",
      "Visual charts show where behavior shifted",
    ],
    color: "purple-500",
  },
];

export function MetricsShowcase() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 bg-gradient-to-b from-transparent via-slate-950/30 to-transparent min-h-screen snap-start snap-always flex items-center">
      <div className="max-w-6xl mx-auto space-y-8 sm:space-y-12 md:space-y-16 w-full">
        <div className="text-center space-y-3 sm:space-y-4 px-4">
          <h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-white">
            Three ways to measure AI behavior
          </h2>
          <p className="text-base sm:text-lg md:text-xl text-slate-300 max-w-3xl mx-auto">
            Consistent, repeatable scores that show what&rsquo;s actually happening
          </p>
        </div>

        <div className="space-y-8 sm:space-y-12">
          {metrics.map((metric, idx) => (
            <div
              key={metric.name}
              className="group relative rounded-2xl sm:rounded-3xl border border-slate-800 bg-slate-950/70 p-6 sm:p-8 md:p-10 lg:p-12 shadow-xl shadow-black/40 backdrop-blur transition-all hover:border-slate-700 hover:shadow-2xl"
            >
              {/* Decorative gradient */}
              <div
                className={`absolute top-0 right-0 w-48 h-48 sm:w-64 sm:h-64 bg-${metric.color}/5 rounded-full blur-3xl -z-10 opacity-0 group-hover:opacity-100 transition-opacity`}
              />

              <div className="grid md:grid-cols-2 gap-6 sm:gap-8">
                <div className="space-y-4 sm:space-y-6">
                  <div>
                    <div
                      className={`inline-flex items-center gap-2 px-3 py-1 rounded-full bg-${metric.color}/10 border border-${metric.color}/20 text-${metric.color} text-xs font-medium mb-3`}
                    >
                      {String(idx + 1).padStart(2, '0')}
                    </div>
                    <h3 className="text-2xl sm:text-3xl font-bold text-white mb-2">
                      {metric.name}
                    </h3>
                    <p className="text-base sm:text-lg text-slate-400 font-medium">
                      {metric.tagline}
                    </p>
                  </div>

                  <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                    {metric.description}
                  </p>

                  <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-3 sm:p-4 overflow-x-auto">
                    <div className="text-xs text-slate-500 font-mono mb-1">
                      FORMULA
                    </div>
                    <code className="text-xs sm:text-sm text-signal font-mono whitespace-nowrap">
                      {metric.formula}
                    </code>
                  </div>
                </div>

                <div className="space-y-2 sm:space-y-3">
                  <div className="text-xs sm:text-sm text-slate-500 font-semibold uppercase tracking-wider mb-3 sm:mb-4">
                    Key features
                  </div>
                  {metric.features.map((feature) => (
                    <div
                      key={feature}
                      className="flex items-start gap-2 sm:gap-3 text-slate-300"
                    >
                      <svg
                        className="w-4 h-4 sm:w-5 sm:h-5 text-signal mt-0.5 flex-shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                      <span className="text-xs sm:text-sm">{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
