import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { GoogleAnalytics } from "../components/google-analytics";
import { SeoStructuredData } from "../components/seo-structured-data";

export const metadata: Metadata = {
  title: "Alignmenter: Application Evaluations and Release Checks",
  description:
    "Evaluate application commitments with saved evidence, matched comparisons, human review, and CI gates. Lightweight Python SDK and CLI.",
  metadataBase: new URL("https://alignmenter.com"),
  keywords: [
    "AI alignment",
    "brand voice testing",
    "LLM evaluation",
    "AI safety",
    "Custom GPT",
    "Anthropic",
    "OpenAI",
    "model drift",
  ],
  alternates: {
    canonical: "https://alignmenter.com",
  },
  openGraph: {
    title: "Alignmenter: Application Evaluations and Release Checks",
    description:
      "Capture answers, compare changes, review failures, and preserve regression cases with the Alignmenter SDK and CLI.",
    url: "https://alignmenter.com",
    siteName: "Alignmenter",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "https://alignmenter.com/alignmenter-banner.png",
        width: 1200,
        height: 630,
        alt: "Alignmenter - Persona-aligned evaluation for conversational AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Alignmenter: Application Evaluations and Release Checks",
    description:
      "Open-source application evaluations with saved evidence, human review, and consistent release gates.",
    creator: "@alignmenter",
    site: "@alignmenter",
    images: ["https://alignmenter.com/alignmenter-banner.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(0,255,149,0.08),_rgba(0,0,0,0))]">
        <GoogleAnalytics />
        <SeoStructuredData />
        <div className="snap-y snap-mandatory h-screen overflow-y-scroll">
          {children}
        </div>
      </body>
    </html>
  );
}
