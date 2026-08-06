import { DocsPage, DocsBody } from "fumadocs-ui/page";

export default function Page() {
  return (
    <DocsPage>
      <DocsBody>
        <h1>Introduction</h1>
        <p>
          PaxRelay is the payment relay for AI agents — route, pay, and verify
          agent-to-service calls using the 402LXP protocol.
        </p>
        <h2>Core Concepts</h2>
        <ul>
          <li>
            <strong>Agents</strong> — autonomous AI services that consume paid
            capabilities
          </li>
          <li>
            <strong>Providers</strong> — service operators publishing callable
            endpoints
          </li>
          <li>
            <strong>Policies</strong> — spend limits and approval rules enforced
            per agent
          </li>
          <li>
            <strong>Receipts</strong> — signed execution proofs anchored
            on-chain
          </li>
        </ul>
      </DocsBody>
    </DocsPage>
  );
}
