import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { GoogleAnalytics } from "../components/google-analytics";
import { SeoStructuredData } from "../components/seo-structured-data";

export const metadata: Metadata = {
  title: "Alignmenter: Test Your AI's Voice and Safety",
  description:
    "Open-source testing tool for AI behavior. Check if your AI matches your brand voice, stays safe, and behaves consistently across updates.",
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
    title: "Alignmenter: Test Your AI's Voice and Safety",
    description:
      "Audit brand voice, safety, and behavior drift for your AI copilots. Works with Custom GPTs, Anthropic, and local models.",
    url: "https://alignmenter.com",
    siteName: "Alignmenter",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "https://alignmenter.com/og-image.png",
        width: 1200,
        height: 630,
        alt: "Alignmenter brand voice and safety dashboard",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Alignmenter: Test Your AI's Voice and Safety",
    description:
      "Open-source testing tool for AI behavior. Check brand voice, safety, and stability in minutes.",
    creator: "@alignmenter",
    site: "@alignmenter",
    images: ["https://alignmenter.com/og-image.png"],
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
