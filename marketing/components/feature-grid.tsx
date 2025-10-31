const features = [
  {
    title: "Authenticity scoring",
    description:
      "Persona-aligned embeddings, trait calibration, and lexicon checks tell you when models drift from brand voice.",
  },
  {
    title: "Safety oversight",
    description:
      "Blend rule-based heuristics with budget-aware judge calls. Snapshots highlight variance and unresolved disagreements.",
  },
  {
    title: "Stability metrics",
    description:
      "Detect behavioral drift across releases with session variance and run-to-run cosine deltas.",
  },
  {
    title: "Shareable reports",
    description:
      "Export HTML, JSON, and CSV artifacts for every run. Diff versions and annotate outliers in minutes.",
  },
];

export function FeatureGrid() {
  return (
    <section className="grid gap-6 md:grid-cols-2">
      {features.map((feature) => (
        <article
          key={feature.title}
          className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6 shadow-lg shadow-black/30 backdrop-blur"
        >
          <h3 className="text-xl font-semibold text-white">{feature.title}</h3>
          <p className="mt-3 text-sm text-slate-300">{feature.description}</p>
        </article>
      ))}
    </section>
  );
}
