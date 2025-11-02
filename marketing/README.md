# Alignmenter Marketing Site

This Next.js + Tailwind app powers the Alignmenter marketing experience.

## Getting Started

```bash
npm install
npm run dev
```

- `app/page.tsx` contains the hero page and feature highlights.
- Tailwind is configured in `tailwind.config.ts` with the brand "signal" accent color.
- Update CTA links to point at the deployed CLI docs or demo booking flow.

## Production Build

```bash
npm run build
npm run start
```

Deployable via Vercel, Netlify, or any Node-friendly host.

### Analytics

The site loads Google Analytics automatically when `NEXT_PUBLIC_GA_MEASUREMENT_ID` is defined.
For the hosted version we use `G-3733FD2K8Q` (stream ID 12827493090). Set your own measurement ID in deployment environments if you prefer a different property.
