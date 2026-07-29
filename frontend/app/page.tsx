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
              Open <code>/admin/runs/&lt;run_id&gt;</code> to inspect the minimal execution view,
              including approvals, tool summaries, artifacts, side effects, and live polling.
            </p>
          </div>
          <div className="hero-meta">
            <span className="status-pill">local-demo</span>
            <Link className="meta-chip link-chip" href="/admin/runs/replace-with-run-id">
              Open a run detail
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
