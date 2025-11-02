export function ProblemSolution() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 md:py-32 relative min-h-screen snap-start snap-always flex items-center">
      {/* Gradient divider */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-slate-800 to-transparent" />

      <div className="max-w-6xl mx-auto w-full">
        <div className="text-center mb-8 sm:mb-12 md:mb-16">
          <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white mb-3 sm:mb-4 px-4">
            Why Alignmenter?
          </h2>
          <p className="text-base sm:text-lg text-slate-400 max-w-2xl mx-auto px-4">
            Testing AI behavior is hard. Here&rsquo;s the problem we&rsquo;re solving.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-8 sm:gap-12 md:gap-16 items-start">
          {/* Problem */}
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              The challenge
            </div>

            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white leading-tight">
              You can&rsquo;t see AI behavior problems until users do
            </h2>

            <div className="space-y-3 sm:space-y-4 text-sm sm:text-base text-slate-300 leading-relaxed">
              <p>
                You ship a new model version. Within hours, users notice the tone feels wrong.
                Support gets complaints about inappropriate responses. Your brand voice has changed.
              </p>
              <p>
                Standard tests check if answers are correct, but miss tone and personality shifts.
                You need a way to measure brand voice, safety, and consistency before shipping.
              </p>
            </div>

            <ul className="space-y-2 sm:space-y-3 text-sm sm:text-base text-slate-400">
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-red-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span>Generic evals don&rsquo;t measure brand alignment</span>
              </li>
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-red-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span>Manual review doesn&rsquo;t scale across versions</span>
              </li>
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-red-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span>Behavior drift goes undetected until production</span>
              </li>
            </ul>
          </div>

          {/* Solution */}
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-signal/10 border border-signal/20 text-signal text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-signal" />
              The solution
            </div>

            <h2 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white leading-tight">
              Test every release before your users see it
            </h2>

            <div className="space-y-3 sm:space-y-4 text-sm sm:text-base text-slate-300 leading-relaxed">
              <p>
                Alignmenter measures how your AI behaves. Run tests in minutes, compare different
                models side-by-side, and catch problems before shipping.
              </p>
              <p>
                Works with OpenAI, custom GPTs, Anthropic, and local models. Your data stays on your computer.
                Everything runs locally with shareable HTML reports.
              </p>
            </div>

            <ul className="space-y-2 sm:space-y-3 text-sm sm:text-base text-slate-300">
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-signal mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span><strong className="text-white">Brand voice matching</strong> checks if responses sound like you</span>
              </li>
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-signal mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span><strong className="text-white">Safety checks</strong> catch harmful or off-brand responses</span>
              </li>
              <li className="flex items-start gap-2 sm:gap-3">
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-signal mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span><strong className="text-white">Consistency tracking</strong> spots when behavior changes unexpectedly</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
