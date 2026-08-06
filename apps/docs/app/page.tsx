export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-bold">PaxRelay Documentation</h1>
        <p className="text-lg text-slate-600">
          The AI payment relay — route, pay, and verify agent-to-service calls.
        </p>
        <a
          href="/docs"
          className="inline-block px-6 py-3 bg-brand text-white rounded-lg hover:bg-brand-700"
        >
          Read the Docs
        </a>
      </div>
    </main>
  );
}
