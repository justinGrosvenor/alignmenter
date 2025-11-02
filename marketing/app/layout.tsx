import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { GoogleAnalytics } from "../components/google-analytics";

export const metadata: Metadata = {
  title: "Alignmenter: Test Your AI's Voice and Safety",
  description:
    "Open-source testing tool for AI behavior. Check if your AI matches your brand voice, stays safe, and behaves consistently across updates.",
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
        <div className="snap-y snap-mandatory h-screen overflow-y-scroll">
          {children}
        </div>
      </body>
    </html>
  );
}
