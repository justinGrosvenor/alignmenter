import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-slate-800 bg-slate-950/50 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 sm:gap-10 md:gap-12 mb-8 sm:mb-12">
          {/* Brand */}
          <div className="col-span-2 space-y-3 sm:space-y-4">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-gradient-to-br from-signal to-emerald-400 flex items-center justify-center">
                <span className="text-black font-bold text-base sm:text-lg">A</span>
              </div>
              <span className="text-lg sm:text-xl font-bold text-white">Alignmenter</span>
            </div>
            <p className="text-sm sm:text-base text-slate-400 max-w-sm">
              Open-source testing tool for AI behavior. Check your AI&rsquo;s voice, safety, and consistency
              before every release.
            </p>
            <div className="flex items-center gap-3 sm:gap-4">
              <Link
                href="https://github.com/justinGrosvenor/alignmenter"
                className="text-slate-400 hover:text-signal transition-colors"
                aria-label="GitHub"
              >
                <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                </svg>
              </Link>
              <Link
                href="https://twitter.com/alignmenter"
                className="text-slate-400 hover:text-signal transition-colors"
                aria-label="Twitter"
              >
                <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </Link>
            </div>
          </div>

          {/* Product */}
          <div>
            <h4 className="font-semibold text-white mb-3 sm:mb-4 text-sm sm:text-base">Product</h4>
            <ul className="space-y-2 sm:space-y-3 text-xs sm:text-sm text-slate-400">
              <li>
                <Link href="https://docs.alignmenter.com" className="hover:text-signal transition-colors">
                  Documentation
                </Link>
              </li>
              <li>
                <Link href="https://docs.alignmenter.com/getting-started/quickstart/" className="hover:text-signal transition-colors">
                  Quick start
                </Link>
              </li>
              <li>
                <Link href="https://docs.alignmenter.com/reference/cli/" className="hover:text-signal transition-colors">
                  CLI reference
                </Link>
              </li>
              <li>
                <Link href="https://docs.alignmenter.com/guides/persona/" className="hover:text-signal transition-colors">
                  Examples
                </Link>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h4 className="font-semibold text-white mb-3 sm:mb-4 text-sm sm:text-base">Resources</h4>
            <ul className="space-y-2 sm:space-y-3 text-xs sm:text-sm text-slate-400">
              <li>
                <Link href="https://github.com/justinGrosvenor/alignmenter" className="hover:text-signal transition-colors">
                  GitHub
                </Link>
              </li>
              <li>
                <Link href="https://github.com/justinGrosvenor/alignmenter/issues" className="hover:text-signal transition-colors">
                  Issues
                </Link>
              </li>
              <li>
                <Link href="https://docs.alignmenter.com/contributing/" className="hover:text-signal transition-colors">
                  Contributing
                </Link>
              </li>
              <li>
                <Link href="https://pypi.org/project/alignmenter/" className="hover:text-signal transition-colors">
                  PyPI
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom */}
        <div className="pt-6 sm:pt-8 border-t border-slate-800 flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-4 text-xs sm:text-sm text-slate-500">
          <p>
            © 2025 Alignmenter. Licensed under Apache 2.0.
          </p>
          <div className="flex items-center gap-4 sm:gap-6">
            <Link href="https://x.com/alignmenter" className="hover:text-signal transition-colors">
              X (Twitter)
            </Link>
            <Link href="https://github.com/justinGrosvenor/alignmenter" className="hover:text-signal transition-colors">
              GitHub
            </Link>
            <Link href="https://findly.tools" className="hover:opacity-80 transition-opacity">
              <img
                src="https://findly.tools/badges/findly-tools-badge-dark.svg"
                alt="Featured on Findly Tools"
                className="h-6"
              />
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
