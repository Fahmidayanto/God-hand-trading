export default function MT5Footer() {
  return (
    <footer className="mt-10 py-5 text-center text-[var(--text-tertiary)] text-sm">
      <div className="flex justify-center gap-6 mb-3">
        <a
          href="#"
          className="text-[var(--text-secondary)] no-underline transition-colors hover:text-[var(--neon-blue)]"
        >
          Documentation
        </a>
        <span>•</span>
        <a
          href="#"
          className="text-[var(--text-secondary)] no-underline transition-colors hover:text-[var(--neon-blue)]"
        >
          API
        </a>
        <span>•</span>
        <a
          href="#"
          className="text-[var(--text-secondary)] no-underline transition-colors hover:text-[var(--neon-blue)]"
        >
          GitHub
        </a>
        <span>•</span>
        <a
          href="#"
          className="text-[var(--text-secondary)] no-underline transition-colors hover:text-[var(--neon-blue)]"
        >
          Support
        </a>
      </div>
      <div>
        © 2026 God Hand Trading System • Version 1.0.0 • Built with ✋⚡
      </div>
    </footer>
  );
}
