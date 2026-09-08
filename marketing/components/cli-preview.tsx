export function CLIPreview() {
  return (
    <section className="px-4 sm:px-6 py-16 sm:py-24 min-h-screen snap-start flex items-center">
      <div className="max-w-6xl mx-auto space-y-8 w-full">
        <div className="text-center space-y-4">
          <h2 className="text-3xl sm:text-5xl font-bold text-white">From a failure to a release check</h2>
          <p className="text-lg text-slate-300">Run the offline example, then connect your application and review its evidence.</p>
        </div>
        <pre className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-sm text-slate-300 overflow-x-auto"><code>{`pip install alignmenter
alignmenter init-suite --out evals/resource-task
alignmenter run-suite evals/resource-task/suite.yaml --out reports

# Compare two saved run directories
alignmenter compare BASELINE_RUN CANDIDATE_RUN --out reports/comparison

# Export evidence for human review
alignmenter review-export RUN --out review.jsonl
# A reviewer fills the annotation fields before import
alignmenter review-import RUN --annotations review.jsonl
alignmenter qualify RUN`}</code></pre>
        <div className="grid sm:grid-cols-3 gap-6 text-center text-slate-300">
          <p><strong className="block text-white">Saved evidence</strong>Inspect answers and source quotes offline</p>
          <p><strong className="block text-white">Explicit coverage</strong>Missing work cannot produce a pass</p>
          <p><strong className="block text-white">Human references</strong>Preserve disagreements and adjudication</p>
        </div>
      </div>
    </section>
  );
}
