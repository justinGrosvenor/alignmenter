"use client";

import Script from "next/script";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://alignmenter.com";

export function SeoStructuredData() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Alignmenter",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Cross-platform",
    description:
      "Alignmenter tests AI assistants for brand voice alignment, safety issues, and behavioral drift.",
    url: SITE_URL,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    creator: {
      "@type": "Organization",
      name: "Alignmenter",
      url: SITE_URL,
    },
  };

  return (
    <Script id="seo-structured-data" type="application/ld+json" strategy="afterInteractive">
      {JSON.stringify(jsonLd)}
    </Script>
  );
}
