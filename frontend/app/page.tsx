import Link from "next/link";

export default function HomePage() {
  return (
    <main className="app-shell">
      <div className="page">
        <section className="hero hero-home">
          <div>
            <p className="kicker">Feishu Project Weekly Agent</p>
            <h1 className="title">Run detail and workflow trace</h1>
            <p className="lede">
              Open the admin dashboard, run list, or a specific run detail page to inspect the
              execution trace, approvals, tool summaries, artifacts, and side effects.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">local-demo</span>
            <Link className="meta-chip link-chip" href="/admin/dashboard">
              Open dashboard
            </Link>
            <Link className="meta-chip link-chip" href="/admin/runs">
              Open run list
            </Link>
            <Link className="meta-chip link-chip" href="/admin/runs/replace-with-run-id">
              Open run detail
            </Link>
            <Link className="meta-chip link-chip" href="/admin/configuration">
              Open configuration
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
