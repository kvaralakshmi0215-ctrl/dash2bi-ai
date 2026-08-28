import { Card, Badge } from '../components/ui'

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold text-white">Settings</h1>
      <p className="text-slate-400 mt-1 text-sm">Configuration for this MVP is managed via backend environment variables.</p>

      <Card className="mt-6">
        <h2 className="text-white font-medium mb-3">AI Provider</h2>
        <p className="text-slate-400 text-sm">
          Set <code className="text-brand-300">AI_PROVIDER</code> and <code className="text-brand-300">ANTHROPIC_API_KEY</code> in
          the backend&apos;s <code className="text-brand-300">.env</code> file. When no provider is configured, the app falls back to
          deterministic string-similarity heuristics for column matching and DAX generation — the pipeline still works, just with
          lower confidence scores (surfaced as &quot;AI Suggested&quot; rather than &quot;Automatic&quot;).
        </p>
        <div className="flex gap-2 mt-3">
          <Badge>AI_PROVIDER=anthropic</Badge>
          <Badge>AI_PROVIDER=none</Badge>
        </div>
      </Card>

      <Card className="mt-6">
        <h2 className="text-white font-medium mb-3">Upload limits</h2>
        <p className="text-slate-400 text-sm">
          Controlled by <code className="text-brand-300">MAX_UPLOAD_SIZE_MB</code> (default 25MB per file).
        </p>
      </Card>

      <Card className="mt-6">
        <h2 className="text-white font-medium mb-3">Database</h2>
        <p className="text-slate-400 text-sm">
          SQLite by default (<code className="text-brand-300">DATABASE_URL=sqlite:///./dash2bi.db</code>). Point
          <code className="text-brand-300"> DATABASE_URL</code> at a PostgreSQL DSN to scale up — no application code changes required.
        </p>
      </Card>
    </div>
  )
}
