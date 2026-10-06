# PaxRelay: Project Structure and Technical Reference

This document contains the detailed product specification, system design, and developer reference. For a plain-language introduction, start with [README.md](README.md).

> **Implementation status:** This specification describes both implemented code and planned capabilities. Read the current-checkout notes below before relying on the architecture, integrations, or setup instructions.

## Current checkout

The repository is in pre-alpha and in an active refactor.

- The control-plane API has routes for agents, providers, services, policies, scoped API keys, receipts, public receipt-key distribution, transactions, analytics, and webhooks. It includes one-time tenant/key bootstrap, key inventory and revocation, request IDs, PostgreSQL readiness reporting, and audited service pause/resume controls. Service publishing accepts HTTP JSON or MCP Streamable HTTP. MCP versions pin a tool name and Draft 2020-12 input schema; the gateway checks arguments before quoting. Pausing prevents new routes while already-issued, unexpired quotes remain completable. The gateway emits the published LayerX 402LXP v2 offer, consumes buyer proofs, and verifies signed payment receipts with a pinned official SDK. A funded testnet transaction and external network qualification remain pending operator credentials, a funded test payer, signer-produced activity, and trusted testnet values. Staging and production dashboard users sign in through OIDC. The web server sends a short-lived signed assertion to the API; the API checks the user's active project membership and role on every request. Machine API keys remain available for SDK and gateway integrations.
- The gateway contains the two-stage paid-call flow: create a quote, then verify payment, forward the request, and issue a receipt.
- The web console includes API-backed tenant pages and live production dashboard overviews. Its agent, policy, provider, service, receipt, analytics, and transaction pages read tenant-scoped data from the API using `agents:read`, `policies:read`, `providers:read`, `services:read`, `receipts:read`, `analytics:read`, and `transactions:read` keys. The Agents page also registers agents with `agents:write`; the complete dashboard flow requires both agent scopes. A successful registration appears in the directory and exposes the full agent UUID for copying. An optional wallet address is stored as metadata and does not connect a wallet or enable payment. The Providers page also registers profiles with `providers:write`, including an optional HTTP(S) website and a payment wallet address; production profiles require that address. Provider UUIDs can be copied from registration or the directory. Provider website links are limited to HTTP(S), and registration does not verify provider ownership. The provider list does not include live health or performance data. The Services page publishes services with `services:write` for a copied provider UUID. It captures a capability, protocols, exact USDX per-call price, base and invocation URLs, and bounded health-check settings; exact amounts are sent as integer atomic units. Use HTTPS in staging and production; at invocation, the gateway checks URLs and the production host allowlist before forwarding. The service list shows the latest worker probe result, timestamp, and failure count; a new service stays out of routing until its first probe passes. The Settings page lists project API keys with `api-keys:read`, creates or revokes keys with `api-keys:write`, and manages project members with `project-members:read` and `project-members:write`; a new raw key is shown once in page memory. General workspace preferences such as network defaults are not exposed by the current API. The receipt list displays recent summaries, exact atomic-unit payment amounts, and signature metadata; the page does not verify signatures. Its approval page reads requests with `approvals:read` and submits confirmed decisions with `approvals:write`. Approval allows a request to continue to payment checks but does not submit payment. The policy directory can create supported spending rules and expands policies to full rule and assignment details; assigning a policy uses an agent UUID. The evaluator does not enforce allowed contracts, maximum drawdown, or session expiry. The gateway loads recent completed provider failures when a policy sets a failure threshold. The `/dashboard`, `/admin`, and `/creator` overview pages now load live tenant-scoped production data from services, transactions, approvals, providers, receipts, and analytics endpoints. They verify the environment through `GET /v1/context`, refresh every 30 seconds, and show independent loading, empty, scope, and API-error states rather than sample figures. The admin view is project-scoped, not cross-customer; the creator view is also project-scoped because the API does not yet expose per-creator authorization. The sign-in page uses Auth.js with an OIDC provider. Project owners and administrators manage project memberships in Settings; role grants are enforced by the API, not only by the web interface.
- The simulator returns fake payment and settlement results. Its service registry is stored in memory.
- The worker expires overdue policy approvals, recovers stale paid executions as unknown without replaying providers, fans supported events into the durable webhook queue, sends signed webhooks with DNS pinning and bounded retries, probes configured provider health paths, indexes recent execution metrics, rebuilds recent hourly and daily tenant spend rollups, and compares verified payments with local and external evidence. Local mismatches are reviewable through a scoped API route. LayerX/Paxeer endpoint contracts and commitment semantics still need validation. Analytics API queries use fresh daily rollups for complete days and source payments for partial days or whenever the rollup refresh is stale or unavailable.
- Python runtime packages required by the API, gateway, worker, and simulator are present in this checkout. The Python SDK supports tenant-scoped agent, provider, service, policy, approval, receipt-history, transaction-history, and spend-analytics operations; local receipt verification; public-key manifest retrieval; and a gateway client for requesting a quote and submitting caller-produced payment proof. The Python MCP package exposes configured paid tools through an agent-facing MCP server with structured outcomes and host-supplied payment proof. The gateway invokes provider services over HTTP JSON or MCP Streamable HTTP; MCP service versions pin the upstream tool name and argument schema. Neither MCP adapter signs or initiates payments. Transaction mutations and wallet signing remain unimplemented. The TypeScript SDK, MCP, UI, and API-client packages are not part of the current workspace.
- The technical references in `docs/` now describe the routes and flows in source, and call out incomplete or simulated behavior. Read [docs/TECHNICAL.md](docs/TECHNICAL.md) for local setup and the documentation index.

The specification below preserves the technical design that was previously in README.md. Treat feature descriptions as product intent unless the corresponding implementation exists in the current source tree. Provider MCP dispatch is implemented in the gateway, but still needs fake-server coverage and staging validation.

---
## Complete product and technical specification

**The MCP-native payment gateway, service router and AgentOps control plane for Paxeer Network.**

PaxRelay enables developers to monetise APIs, MCP tools and autonomous services through Paxeer’s 402LXP payment flow. It also gives AI-agent operators a unified platform for service discovery, programmable spending policies, intelligent provider routing, payment verification, execution receipts and operational monitoring.

[![GitHub](https://img.shields.io/badge/GitHub-thetruesammyjay-181717?logo=github)](https://github.com/thetruesammyjay/paxrelay)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange)](#project-status)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](#license)
[![Paxeer](https://img.shields.io/badge/network-Paxeer-purple)](https://www.paxeer.app/)
[![Chain ID](https://img.shields.io/badge/chain%20ID-125-black)](https://docs.paxeer.app/)

> PaxRelay is an independent developer project and is not currently an official Paxeer Network product.

---

## Table of Contents

* [Overview](#overview)
* [The Problem](#the-problem)
* [The Solution](#the-solution)
* [Why Paxeer](#why-paxeer)
* [Core Product Principles](#core-product-principles)
* [Target Users](#target-users)
* [Primary Use Cases](#primary-use-cases)
* [Core Features](#core-features)
* [System Architecture](#system-architecture)
* [402LXP Request Lifecycle](#402lxp-request-lifecycle)
* [Monorepo Structure](#monorepo-structure)
* [Application Responsibilities](#application-responsibilities)
* [Shared Packages](#shared-packages)
* [Technology Stack](#technology-stack)
* [Domain Model](#domain-model)
* [Database Design](#database-design)
* [Provider Routing Engine](#provider-routing-engine)
* [Policy Engine](#policy-engine)
* [MCP Integration](#mcp-integration)
* [Provider SDK](#provider-sdk)
* [Agent SDK](#agent-sdk)
* [Payment and Settlement Model](#payment-and-settlement-model)
* [Execution Receipts](#execution-receipts)
* [API Design](#api-design)
* [Events and Webhooks](#events-and-webhooks)
* [Authentication and Authorisation](#authentication-and-authorisation)
* [Security Model](#security-model)
* [Reliability and Fault Tolerance](#reliability-and-fault-tolerance)
* [Observability](#observability)
* [Local Development](#local-development)
* [Environment Variables](#environment-variables)
* [Testing Strategy](#testing-strategy)
* [Deployment](#deployment)
* [CI/CD](#cicd)
* [Documentation Structure](#documentation-structure)
* [Development Roadmap](#development-roadmap)
* [Non-Goals](#non-goals)
* [Contributing](#contributing)
* [Security Disclosure](#security-disclosure)
* [License](#license)
* [Disclaimer](#disclaimer)

---

## Overview

PaxRelay is a payment and operations infrastructure layer for autonomous software running on Paxeer Network.

It sits between AI agents and paid machine services.

A provider can connect an existing MCP server, FastAPI endpoint, Express route, LangChain tool or autonomous service to PaxRelay. PaxRelay exposes the service through a standard paid interface, responds to unpaid calls with a 402LXP payment requirement, verifies settlement and forwards authorised requests to the provider.

An agent operator can use PaxRelay to:

* Register autonomous agents.
* Assign spending limits.
* Define provider and capability allowlists.
* Discover services.
* Compare providers.
* Pay for services through 402LXP.
* Retry failed calls safely.
* Route requests to fallback providers.
* Track every payment and tool execution.
* Generate verifiable execution receipts.
* Reconcile LayerX transactions with Paxeer L1 settlement records.

PaxRelay is not intended to replace Paxeer’s protocol-level wallets, payment rails, service registry or settlement records. It provides the developer experience, routing, monitoring and operational controls required to use those primitives reliably in production applications.

### Product positioning

> PaxRelay is Stripe Connect, Cloudflare API Gateway and AgentOps for machine-to-machine commerce on Paxeer.

### Repository

```text
https://github.com/thetruesammyjay/paxrelay
```

### Maintainer

```text
GitHub: @thetruesammyjay
```

---

## The Problem

AI agents are increasingly capable of selecting tools, calling APIs, purchasing data, renting compute and coordinating with other autonomous services.

However, connecting an agent directly to a wallet creates several risks:

* The agent may spend more than its approved budget.
* The same request may be paid for more than once.
* A provider may receive payment but fail to deliver.
* An agent may select an unreliable or overpriced service.
* Operators may be unable to explain why a provider was selected.
* Tool-call failures may leave payment and execution state inconsistent.
* Teams may lack visibility into agent expenses.
* API providers may find payment integration too complicated.
* Traditional API keys and monthly subscriptions do not work well for autonomous per-call commerce.
* Existing MCP servers do not have a standard monetisation layer.

Paxeer provides infrastructure for agent wallets, HTTP-native payments, service discovery and settlement records. Developers still need a production-ready control plane that coordinates those components.

---

## The Solution

PaxRelay provides five connected layers.

### 1. Payment gateway

A reverse proxy that handles:

* HTTP 402 payment challenges.
* 402LXP quote generation.
* Payment verification.
* Request authorisation.
* Provider forwarding.
* Idempotency.
* Replay protection.
* Settlement tracking.

### 2. Agent treasury

A control plane for:

* Agent wallets.
* Spending policies.
* Daily and monthly budgets.
* Approval thresholds.
* Session permissions.
* Provider allowlists.
* Capability restrictions.
* Emergency stops.

### 3. Intelligent service router

A deterministic router that evaluates:

* Price.
* Provider reputation.
* Historical delivery success.
* Response latency.
* Availability.
* Policy compatibility.
* Service version.
* Geographic or jurisdictional restrictions.

### 4. MCP monetisation layer

Python and TypeScript packages that allow developers to turn existing MCP tools and APIs into paid Paxeer services without manually implementing the complete payment flow.

### 5. AgentOps dashboard

A web application for monitoring:

* Agent expenditure.
* Provider revenue.
* Payment state.
* Tool calls.
* Failed executions.
* Settlement reconciliation.
* Provider health.
* Budget consumption.
* Approval requests.
* Security events.

---

## Why Paxeer

PaxRelay is designed around the current Paxeer agent-commerce architecture.

The integration assumes access to:

* Paxeer EVM execution.
* Paxeer Chain ID `125`.
* Paxeer-compatible smart wallets.
* Policy-controlled agent wallets.
* LayerX settlement.
* USDX-denominated agent payments.
* 402LXP payment challenges.
* A provider and capability registry.
* On-chain settlement records.
* Python and TypeScript integration surfaces.

All protocol-specific operations are isolated behind adapter interfaces. This prevents the rest of the application from depending directly on unstable contract addresses, RPC methods or SDK implementations.

```text
Application code
      |
      v
PaxRelay domain interfaces
      |
      v
Paxeer adapter
      |
      +---- Paxeer L1
      +---- LayerX
      +---- 402LXP
      +---- Service registry
      +---- Settlement records
```

---

## Core Product Principles

### Non-custodial by default

PaxRelay should not take permanent custody of customer funds or seed phrases.

Agents should transact through user-controlled smart wallets, delegated session keys or externally managed signing infrastructure.

### Policy before payment

Every payment must pass through a deterministic policy evaluation before it can be authorised.

### Idempotent execution

Repeating a request with the same idempotency key must not create multiple payments or duplicate provider executions.

### Payment and delivery are separate states

A successful payment does not automatically mean the provider delivered a successful response.

PaxRelay tracks:

```text
Request state
Payment state
Execution state
Receipt state
Settlement state
```

independently.

### Explainable routing

Every provider decision must produce a human-readable explanation and a machine-readable score breakdown.

### Fail closed

When payment state, policy state or signature verification is uncertain, the request must be rejected rather than executed.

### Protocol abstraction

Paxeer-specific code must remain behind explicit interfaces so that network upgrades do not require rewriting the business logic.

### Observable by default

Every request should generate structured logs, traces, metrics and an audit entry.

---

## Target Users

### AI-agent developers

Developers building agents with:

* MCP.
* LangChain.
* LangGraph.
* CrewAI.
* ElizaOS.
* OpenAI Agents SDK.
* Custom Python agents.
* Custom TypeScript agents.

### API and MCP service providers

Providers selling:

* Model inference.
* Web search.
* Data extraction.
* Market data.
* Blockchain data.
* Storage.
* Compute.
* Image generation.
* Document processing.
* Oracle data.
* Identity verification.
* Autonomous workflows.

### AI application teams

Companies that need to control and observe spending across several autonomous agents.

### Infrastructure operators

Teams building marketplaces, agent networks, service registries or machine-payment products on Paxeer.

---

## Primary Use Cases

### Paid MCP tools

A developer wraps an MCP tool with PaxRelay and charges a fixed USDX amount for each invocation.

### Paid REST APIs

An existing FastAPI or Express API is placed behind the PaxRelay Gateway.

### Agent-controlled procurement

An autonomous agent discovers and purchases services that satisfy price, quality and policy requirements.

### Multi-provider inference routing

An agent requests model inference and PaxRelay selects the most appropriate provider based on cost, reputation and latency.

### Usage-based machine services

Providers charge per request, token, byte, second or compute unit.

### Team-level agent budgets

An organisation assigns different limits and permissions to research, operations, trading and customer-support agents.

### Escalated payments

Payments above a configured threshold require approval from a human operator.

### Provider failover

A request is retried with a different provider when the first provider times out or fails before delivery.

---

## Core Features

### Agent management

* Create and manage agents.
* Associate agents with Paxeer wallet addresses.
* Issue scoped API keys.
* Configure session permissions.
* Pause or revoke an agent.
* View agent spending history.
* Rotate delegated session keys.

### Provider management

* Register service providers.
* Verify provider ownership.
* Publish service capabilities.
* Configure pricing models.
* Configure health-check endpoints.
* Set concurrency limits.
* Track provider reputation.
* Disable unhealthy services automatically.

### Service registry

* Search by capability.
* Filter by price.
* Filter by reputation.
* Filter by response time.
* Filter by supported protocol.
* Filter by payment currency.
* Filter by provider status.
* Cache registry results.
* Synchronise with Paxeer registry records.

### Payment gateway

* Generate 402LXP payment requirements.
* Verify payment proofs.
* Enforce quote expiration.
* Prevent proof reuse.
* Support per-call pricing.
* Support metered pricing.
* Support streaming-payment adapters.
* Track refunds and disputes when available.
* Reconcile LayerX and L1 records.

### Policy controls

* Maximum payment per call.
* Daily spending limit.
* Monthly spending limit.
* Capability allowlist.
* Provider allowlist.
* Provider blocklist.
* Contract allowlist.
* Required minimum reputation.
* Required minimum success rate.
* Maximum accepted latency.
* Human approval thresholds.
* Emergency stop conditions.
* Maximum consecutive failures.
* Maximum drawdown.
* Session expiry.
* Currency restrictions.

### Routing

* Lowest-cost routing.
* Lowest-latency routing.
* Highest-reputation routing.
* Balanced routing.
* Custom weighted routing.
* Provider fallback chains.
* Sticky provider sessions.
* Region-aware routing.
* Deterministic routing explanations.

### Developer experience

* Python SDK.
* TypeScript SDK.
* MCP provider adapter.
* MCP client adapter.
* FastAPI middleware.
* Express middleware.
* LangChain tools.
* OpenAPI specification.
* Generated API clients.
* Local payment simulator.
* Example applications.

### Operations

* Real-time request dashboard.
* Spending analytics.
* Provider revenue analytics.
* Settlement reconciliation.
* Failed-request inspection.
* Webhook delivery logs.
* Audit logs.
* Security event monitoring.
* Budget alerts.
* Provider health alerts.

---

## System Architecture

```mermaid
flowchart TB
    subgraph Clients["Agent and Developer Clients"]
        MCPCLIENT["MCP Client"]
        PYAGENT["Python Agent"]
        TSAGENT["TypeScript Agent"]
        DASHBOARD["PaxRelay Dashboard"]
        CLI["PaxRelay CLI"]
    end

    subgraph Edge["PaxRelay Edge"]
        GATEWAY["402LXP Gateway"]
        AUTH["Authentication and API Keys"]
        RATE["Rate Limiter"]
        IDEMP["Idempotency Layer"]
    end

    subgraph ControlPlane["PaxRelay Control Plane"]
        API["FastAPI Control Plane"]
        POLICY["Policy Engine"]
        ROUTER["Provider Router"]
        REGISTRY["Service Registry"]
        APPROVALS["Approval Service"]
        RECEIPTS["Receipt Service"]
        WEBHOOKS["Webhook Service"]
    end

    subgraph Workers["Asynchronous Workers"]
        RECONCILER["Settlement Reconciler"]
        INDEXER["Paxeer Event Indexer"]
        HEALTH["Provider Health Worker"]
        ANALYTICS["Analytics Aggregator"]
        OUTBOX["Outbox Dispatcher"]
    end

    subgraph Storage["Data Infrastructure"]
        NEON["Railway PostgreSQL"]
        REDIS["Railway Redis"]
        OBJECTS["Object Storage"]
    end

    subgraph Paxeer["Paxeer Network"]
        LAYERX["LayerX"]
        LXP["402LXP"]
        L1["Paxeer L1"]
        PAXREGISTRY["Paxeer Service Registry"]
        SETTLEMENTS["Settlement Records"]
        WALLETS["Policy-Bound Wallets"]
    end

    subgraph Providers["Service Providers"]
        MCPTOOLS["Paid MCP Servers"]
        FASTAPI["FastAPI Services"]
        EXPRESS["Express Services"]
        INFERENCE["Inference Providers"]
        DATA["Data and Oracle Providers"]
    end

    MCPCLIENT --> GATEWAY
    PYAGENT --> GATEWAY
    TSAGENT --> GATEWAY
    DASHBOARD --> API
    CLI --> API

    GATEWAY --> AUTH
    AUTH --> RATE
    RATE --> IDEMP
    IDEMP --> POLICY
    POLICY --> ROUTER
    ROUTER --> REGISTRY
    ROUTER --> LXP

    API --> POLICY
    API --> ROUTER
    API --> APPROVALS
    API --> RECEIPTS
    API --> WEBHOOKS

    REGISTRY <--> PAXREGISTRY
    LXP <--> LAYERX
    LAYERX --> L1
    L1 --> SETTLEMENTS
    POLICY <--> WALLETS

    ROUTER --> MCPTOOLS
    ROUTER --> FASTAPI
    ROUTER --> EXPRESS
    ROUTER --> INFERENCE
    ROUTER --> DATA

    API --> NEON
    GATEWAY --> NEON
    GATEWAY --> REDIS
    POLICY --> REDIS
    ROUTER --> REDIS
    RECEIPTS --> OBJECTS

    INDEXER --> L1
    INDEXER --> NEON
    RECONCILER --> LAYERX
    RECONCILER --> SETTLEMENTS
    RECONCILER --> NEON
    HEALTH --> Providers
    HEALTH --> NEON
    ANALYTICS --> NEON
    OUTBOX --> WEBHOOKS
    OUTBOX --> NEON
```

---

## 402LXP Request Lifecycle

```mermaid
sequenceDiagram
    autonumber

    participant A as AI Agent
    participant G as PaxRelay Gateway
    participant P as Policy Engine
    participant R as Provider Router
    participant X as LayerX / 402LXP
    participant S as Service Provider
    participant D as Neon PostgreSQL
    participant L as Paxeer L1

    A->>G: Invoke capability with idempotency key
    G->>D: Check existing request

    alt Existing completed request
        D-->>G: Stored response and receipt
        G-->>A: Return previous result
    else New request
        G->>P: Evaluate agent policy
        P-->>G: Allow, deny or require approval

        alt Policy denied
            G-->>A: 403 Policy violation
        else Approval required
            G-->>A: 202 Approval pending
        else Policy allowed
            G->>R: Find eligible providers
            R-->>G: Selected provider and route explanation
            G-->>A: HTTP 402 with payment requirement
            A->>X: Pay quoted USDX amount
            X-->>A: Payment proof
            A->>G: Retry request with payment proof
            G->>X: Verify payment
            X-->>G: Payment verified
            G->>D: Reserve execution atomically
            G->>S: Forward authorised request
            S-->>G: Return service response
            G->>D: Store execution result
            G->>G: Generate signed receipt
            G-->>A: Result and execution receipt
            X->>L: Batch settlement record
        end
    end
```

### Request states

```text
created
policy_pending
approval_pending
payment_required
payment_submitted
payment_verified
execution_reserved
executing
delivered
failed
expired
cancelled
```

### Payment states

```text
unpaid
quoted
submitted
verified
settled_layerx
anchored_l1
refunded
disputed
failed
expired
```

### Execution states

```text
not_started
reserved
running
succeeded
provider_error
timeout
cancelled
unknown
```

---

## Monorepo Structure

```text
paxrelay/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   │   ├── (auth)/
│   │   │   ├── dashboard/
│   │   │   ├── agents/
│   │   │   ├── providers/
│   │   │   ├── services/
│   │   │   ├── transactions/
│   │   │   ├── receipts/
│   │   │   ├── approvals/
│   │   │   ├── policies/
│   │   │   ├── analytics/
│   │   │   ├── settings/
│   │   │   └── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── public/
│   │   ├── tests/
│   │   └── package.json
│   │
│   ├── api/
│   │   ├── src/paxrelay_api/
│   │   │   ├── routes/
│   │   │   ├── dependencies/
│   │   │   ├── middleware/
│   │   │   ├── services/
│   │   │   ├── schemas/
│   │   │   ├── security/
│   │   │   ├── exceptions/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   ├── gateway/
│   │   ├── src/paxrelay_gateway/
│   │   │   ├── proxy/
│   │   │   ├── payment/
│   │   │   ├── verification/
│   │   │   ├── idempotency/
│   │   │   ├── metering/
│   │   │   ├── receipts/
│   │   │   ├── middleware/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   ├── worker/
│   │   ├── src/paxrelay_worker/
│   │   │   ├── jobs/
│   │   │   ├── consumers/
│   │   │   ├── reconciliation/
│   │   │   ├── indexing/
│   │   │   ├── analytics/
│   │   │   ├── health/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   ├── simulator/
│   │   ├── src/paxrelay_simulator/
│   │   │   ├── layerx/
│   │   │   ├── lxp402/
│   │   │   ├── providers/
│   │   │   ├── scenarios/
│   │   │   └── main.py
│   │   ├── tests/
│   │   └── pyproject.toml
│   │
│   └── docs/
│       ├── app/
│       ├── content/
│       ├── components/
│       └── package.json
│
├── packages/
│   ├── db/
│   │   ├── src/paxrelay_db/
│   │   │   ├── models/
│   │   │   ├── repositories/
│   │   │   ├── migrations/
│   │   │   ├── session.py
│   │   │   └── base.py
│   │   └── pyproject.toml
│   │
│   ├── domain/
│   │   ├── src/paxrelay_domain/
│   │   │   ├── agents/
│   │   │   ├── providers/
│   │   │   ├── payments/
│   │   │   ├── policies/
│   │   │   ├── routing/
│   │   │   ├── receipts/
│   │   │   └── events/
│   │   └── pyproject.toml
│   │
│   ├── paxeer-adapter/
│   │   ├── src/paxrelay_paxeer/
│   │   │   ├── client.py
│   │   │   ├── wallets.py
│   │   │   ├── layerx.py
│   │   │   ├── lxp402.py
│   │   │   ├── registry.py
│   │   │   ├── settlement.py
│   │   │   └── interfaces.py
│   │   └── pyproject.toml
│   │
│   ├── policy-engine/
│   │   ├── src/paxrelay_policy/
│   │   │   ├── evaluator.py
│   │   │   ├── rules/
│   │   │   ├── compiler.py
│   │   │   ├── explanations.py
│   │   │   └── models.py
│   │   └── pyproject.toml
│   │
│   ├── provider-router/
│   │   ├── src/paxrelay_router/
│   │   │   ├── filters.py
│   │   │   ├── scoring.py
│   │   │   ├── strategies.py
│   │   │   ├── failover.py
│   │   │   └── explanations.py
│   │   └── pyproject.toml
│   │
│   ├── receipts/
│   │   ├── src/paxrelay_receipts/
│   │   │   ├── canonical.py
│   │   │   ├── hashing.py
│   │   │   ├── signing.py
│   │   │   ├── verification.py
│   │   │   └── schemas.py
│   │   └── pyproject.toml
│   │
│   ├── mcp-python/
│   │   ├── src/paxrelay_mcp/
│   │   │   ├── client.py
│   │   │   ├── server.py
│   │   │   ├── decorators.py
│   │   │   ├── middleware.py
│   │   │   └── types.py
│   │   ├── examples/
│   │   └── pyproject.toml
│   │
│   ├── sdk-python/
│   │   ├── src/paxrelay/
│   │   │   ├── client.py
│   │   │   ├── agents.py
│   │   │   ├── providers.py
│   │   │   ├── payments.py
│   │   │   ├── receipts.py
│   │   │   └── exceptions.py
│   │   └── pyproject.toml
│   │
│   ├── sdk-typescript/
│   │   ├── src/
│   │   │   ├── client.ts
│   │   │   ├── agents.ts
│   │   │   ├── providers.ts
│   │   │   ├── payments.ts
│   │   │   ├── receipts.ts
│   │   │   └── types.ts
│   │   └── package.json
│   │
│   ├── mcp-typescript/
│   │   ├── src/
│   │   │   ├── client.ts
│   │   │   ├── server.ts
│   │   │   ├── middleware.ts
│   │   │   └── types.ts
│   │   ├── examples/
│   │   └── package.json
│   │
│   ├── api-client/
│   │   ├── src/
│   │   └── package.json
│   │
│   ├── contracts/
│   │   ├── src/
│   │   ├── script/
│   │   ├── test/
│   │   └── foundry.toml
│   │
│   ├── config/
│   │   ├── eslint/
│   │   ├── typescript/
│   │   ├── ruff/
│   │   └── pytest/
│   │
│   └── ui/
│       ├── src/
│       └── package.json
│
├── examples/
│   ├── paid-mcp-weather/
│   ├── paid-fastapi-search/
│   ├── paid-express-api/
│   ├── langchain-agent/
│   ├── crewai-agent/
│   └── provider-failover/
│
├── docs/
│   ├── architecture.md
│   ├── protocol-integration.md
│   ├── 402lxp-flow.md
│   ├── mcp-integration.md
│   ├── policy-engine.md
│   ├── provider-routing.md
│   ├── execution-receipts.md
│   ├── data-model.md
│   ├── api-reference.md
│   ├── threat-model.md
│   ├── deployment.md
│   ├── operations.md
│   └── contributing.md
│
├── infrastructure/
│   ├── docker/
│   ├── terraform/
│   ├── railway/
│   ├── vercel/
│   ├── monitoring/
│   └── scripts/
│
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   │   ├── ci.yml
│   │   ├── frontend.yml
│   │   ├── python.yml
│   │   ├── contracts.yml
│   │   ├── security.yml
│   │   └── release.yml
│   ├── dependabot.yml
│   └── pull_request_template.md
│
├── .changeset/
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── Makefile
├── README.md
├── docker-compose.yml
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── pyproject.toml
├── turbo.json
└── uv.lock
```

---

## Application Responsibilities

### `apps/web`

The Next.js dashboard.

Responsibilities:

* Organisation onboarding.
* Agent management.
* Provider management.
* Policy configuration.
* Payment monitoring.
* Receipt inspection.
* Approval workflows.
* Analytics.
* API key management.
* Webhook configuration.
* Audit-log viewing.

Recommended implementation:

```text
Next.js App Router
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
React Hook Form
Zod
Recharts
viem
wagmi
```

### `apps/api`

The FastAPI control-plane service.

Responsibilities:

* User and organisation APIs.
* Agent and provider configuration.
* Policy management.
* Service registry management.
* API-key issuance.
* Approval workflows.
* Analytics queries.
* Webhook management.
* Administrative operations.
* OpenAPI generation.

The API should not proxy paid provider requests. Paid request forwarding belongs to the gateway.

### `apps/gateway`

The latency-sensitive data plane.

Responsibilities:

* Authenticate agents.
* Accept MCP and HTTP tool calls.
* Validate idempotency keys.
* Evaluate policies.
* Request provider routes.
* Generate 402LXP payment requirements.
* Verify payment proofs.
* Forward authorised requests.
* Apply timeouts and retries.
* Meter provider usage.
* Generate receipts.
* Return results to agents.

The gateway must remain stateless where possible. Durable state should be stored in PostgreSQL, while short-lived coordination and rate-limit counters use Redis.

Current gateway requests use tenant-scoped API keys. In staging and production,
Redis enforces a shared fixed-window limit of 120 requests per key per minute
by default; startup and `/ready` check Redis when this limit is enabled. The
gateway rejects oversized request bodies and provider responses and bounds
provider connection and total request timeouts.

### `apps/worker`

Background processing service.

Responsibilities:

* Paxeer event indexing.
* LayerX reconciliation.
* L1 settlement reconciliation.
* Provider health checks.
* Webhook delivery.
* Analytics aggregation.
* Expired quote cleanup.
* Approval expiry.
* Audit-log archival.
* Retry processing.

Durable jobs should use a PostgreSQL transactional outbox. Redis should not be treated as the only durable job store.

### `apps/simulator`

A local Paxeer and 402LXP development simulator.

Responsibilities:

* Generate mock payment demands.
* Simulate USDX balances.
* Produce test payment proofs.
* Simulate payment verification.
* Simulate provider timeouts.
* Simulate duplicate payments.
* Simulate expired quotes.
* Simulate LayerX batch anchoring.
* Generate reproducible failure scenarios.

### `apps/docs`

The public developer documentation website.

Recommended implementation:

```text
Next.js
MDX
Fumadocs or Nextra
OpenAPI-generated API references
Typedoc
MkDocs-compatible Python SDK references
```

---

## Shared Packages

### `packages/domain`

Contains framework-independent business rules and value objects.

It must not depend on:

* FastAPI.
* Next.js.
* SQLAlchemy.
* Redis.
* HTTP clients.
* Paxeer SDK implementations.

### `packages/paxeer-adapter`

Contains the boundary between PaxRelay and Paxeer.

Recommended interfaces:

```python
from typing import Protocol


class WalletAdapter(Protocol):
    async def get_wallet(self, address: str): ...
    async def read_policy(self, address: str): ...
    async def verify_session(self, session_proof: str): ...


class PaymentAdapter(Protocol):
    async def create_payment_requirement(self, quote): ...
    async def verify_payment(self, proof): ...
    async def get_payment_status(self, payment_id: str): ...


class RegistryAdapter(Protocol):
    async def publish_service(self, service): ...
    async def find_services(self, capability: str): ...
    async def read_provider_history(self, provider: str): ...


class SettlementAdapter(Protocol):
    async def read_settlement(self, settlement_id: str): ...
    async def read_batch(self, batch_id: str): ...
```

Provide at least two implementations:

```text
MockPaxeerAdapter
OfficialPaxeerAdapter
```

The mock implementation powers local development and automated tests.

### `packages/policy-engine`

A deterministic policy evaluator.

Input:

```json
{
  "agent_id": "agt_research_01",
  "capability": "research.web_search",
  "provider_id": "prv_search_01",
  "amount": "0.005",
  "currency": "USDX",
  "current_daily_spend": "2.45",
  "current_monthly_spend": "38.90",
  "provider_reputation": 0.986,
  "provider_success_rate": 0.991
}
```

Output:

```json
{
  "decision": "allow",
  "matched_rules": [
    "daily_budget",
    "capability_allowlist",
    "maximum_price_per_call",
    "minimum_provider_reputation"
  ],
  "explanation": "The request is within the agent's daily budget and satisfies all provider requirements.",
  "policy_version": 7
}
```

### `packages/provider-router`

Contains provider filtering, scoring and failover logic.

### `packages/receipts`

Canonicalises execution data, generates hashes, signs receipts, verifies signatures, and resolves trusted public keys through an activation/retirement/revocation keyring.

### `packages/mcp-python`

Provider and agent integrations for Python MCP applications.

### `packages/mcp-typescript`

Provider and agent integrations for TypeScript MCP applications.

### `packages/sdk-python`

Provides async control-plane and gateway clients. The control-plane client registers and looks up agents and providers, publishes services and manages their routing status, creates and assigns spend policies, reviews approval requests, and reads receipt/transaction history and spend analytics. The gateway client starts paid service calls and submits proof supplied by the caller. The SDK also supports local receipt verification and fetching the public receipt-key manifest. Receipt listing returns summaries; transaction mutations, wallet signing, and payment initiation remain unimplemented.

The package source includes `client.py` for HTTP transport, `agents.py`,
`approvals.py`, `analytics.py`, `providers.py`, `receipts.py`, `services.py`,
`policies.py`, `transactions.py`, and `payments.py` for gateway operations;
`receipts.py` also provides receipt verification helpers. `models.py` contains typed
responses, and `exceptions.py` contains API and transport failures.

### `packages/sdk-typescript`

Public TypeScript client for browsers, Node.js and agent runtimes.

### `packages/api-client`

Generated TypeScript client built from the FastAPI OpenAPI specification.

### `packages/contracts`

Optional PaxRelay-specific Solidity contracts.

Possible future contracts:

* Receipt anchor.
* Provider bond.
* Escrow extension.
* Dispute registry.
* Delegated policy registry.

PaxRelay should use existing Paxeer primitives whenever possible instead of deploying duplicate contracts.

---

## Technology Stack

| Layer                  | Technology                                           |
| ---------------------- | ---------------------------------------------------- |
| Monorepo               | Turborepo, pnpm, uv workspaces                       |
| Dashboard              | Next.js, TypeScript, Tailwind CSS, shadcn/ui         |
| API                    | Python, FastAPI, Pydantic                            |
| Gateway                | Python, FastAPI, HTTPX                               |
| Workers                | Python, PostgreSQL outbox workers                    |
| Python package manager | uv                                                   |
| Database               | Railway PostgreSQL                                   |
| ORM                    | SQLAlchemy 2                                         |
| Migrations             | Alembic                                              |
| Cache and coordination | Railway Redis                                        |
| Validation             | Pydantic, Zod                                        |
| Blockchain integration | viem, ethers, Paxeer SDK adapters                    |
| Smart contracts        | Solidity, Foundry                                    |
| MCP                    | Official Python and TypeScript MCP SDKs              |
| Authentication         | Auth.js with OIDC for dashboard users; scoped API keys for machine clients |
| Observability          | OpenTelemetry, Sentry, Prometheus-compatible metrics |
| Frontend hosting       | Vercel                                               |
| API hosting            | Railway                                              |
| Object storage         | Cloudflare R2 or S3-compatible storage               |
| CI/CD                  | GitHub Actions                                       |
| Documentation          | Next.js with MDX                                     |
| Testing                | Pytest, Vitest, Playwright, Foundry                  |

---

## Domain Model

### Organisation

Represents a team or company using PaxRelay.

### Project

Groups agents, providers, policies and API keys under one environment.

Environments:

```text
development
staging
production
```

### Agent

An autonomous software identity authorised to purchase services.

### Wallet

A Paxeer wallet or policy-bound smart wallet associated with an agent.

### Policy

A versioned set of spending and service-access rules.

### Provider

An organisation or wallet that sells machine services.

### Service

A callable capability published by a provider.

### Service version

An immutable version of a provider service definition.

### Route

The selected provider and scoring decision for a request.

### Quote

A time-limited payment requirement.

### Payment intent

A request to authorise a specific payment.

### Payment

The verified transfer associated with a payment intent.

### Tool call

A logical MCP or HTTP service invocation.

### Execution attempt

One request sent to one provider.

A tool call may have multiple attempts when failover is enabled.

### Receipt

A signed representation of payment, execution and delivery.

### Settlement record

The LayerX or Paxeer L1 record associated with the transaction.

### Approval

A human decision required before an agent can continue.

### Audit event

An immutable record of a security-sensitive action.

---

## Database Design

```mermaid
erDiagram
    ORGANISATIONS ||--o{ MEMBERSHIPS : has
    USERS ||--o{ MEMBERSHIPS : belongs_to
    ORGANISATIONS ||--o{ PROJECTS : owns
    PROJECTS ||--o{ API_KEYS : issues
    PROJECTS ||--o{ AGENTS : contains
    PROJECTS ||--o{ PROVIDERS : contains
    PROJECTS ||--o{ POLICIES : defines

    AGENTS ||--o{ WALLETS : uses
    AGENTS ||--o{ POLICY_ASSIGNMENTS : receives
    POLICIES ||--o{ POLICY_ASSIGNMENTS : assigned
    POLICIES ||--o{ POLICY_RULES : contains

    PROVIDERS ||--o{ SERVICES : publishes
    SERVICES ||--o{ SERVICE_VERSIONS : versions
    SERVICES ||--o{ PROVIDER_METRICS : produces

    AGENTS ||--o{ TOOL_CALLS : initiates
    SERVICE_VERSIONS ||--o{ TOOL_CALLS : handles
    TOOL_CALLS ||--o{ ROUTE_DECISIONS : evaluates
    TOOL_CALLS ||--o{ PAYMENT_INTENTS : requires
    TOOL_CALLS ||--o{ EXECUTION_ATTEMPTS : contains
    TOOL_CALLS ||--o| EXECUTION_RECEIPTS : produces

    PAYMENT_INTENTS ||--o| PAYMENTS : settles
    PAYMENTS ||--o{ SETTLEMENT_RECORDS : anchors
    EXECUTION_ATTEMPTS ||--o| EXECUTION_RECEIPTS : proves

    TOOL_CALLS ||--o{ APPROVAL_REQUESTS : may_require
    PROJECTS ||--o{ WEBHOOK_ENDPOINTS : configures
    WEBHOOK_ENDPOINTS ||--o{ WEBHOOK_DELIVERIES : receives
    PROJECTS ||--o{ AUDIT_LOGS : records
```

### Important tables

```text
users
organisations
memberships
projects
api_keys
agents
wallets
policies
policy_rules
policy_assignments
providers
services
service_versions
provider_metrics
tool_calls
route_decisions
payment_intents
payments
execution_attempts
execution_receipts
settlement_records
approval_requests
webhook_endpoints
webhook_deliveries
audit_logs
outbox_events
```

### Monetary values

Never store monetary values as floating-point numbers.

Use:

```text
amount_atomic NUMERIC(78, 0)
currency_decimals INTEGER
currency_symbol VARCHAR
```

or a fixed-precision decimal representation.

### Multi-tenancy

Every tenant-owned table must contain:

```text
organisation_id
project_id
environment
```

Database queries must enforce tenant scoping.

PostgreSQL Row-Level Security may be used as an additional defence but should not replace application-level authorisation checks.

---

## Provider Routing Engine

The routing engine performs two stages.

### Stage 1: hard filtering

Providers are removed when they fail any mandatory requirement.

Filters may include:

* Provider is inactive.
* Service health check is failing.
* Price exceeds the agent’s maximum.
* Capability does not match.
* Service version is unsupported.
* Provider is blocked by policy.
* Provider reputation is below the minimum.
* Provider success rate is below the minimum.
* Provider does not accept the required currency.
* Provider has reached its concurrency limit.
* Provider is unavailable in the required region.
* Provider does not support the requested protocol.

### Stage 2: weighted scoring

Default balanced strategy:

```text
provider_score =
    reputation_score      × 0.30
  + success_rate_score    × 0.25
  + latency_score         × 0.20
  + price_score           × 0.15
  + availability_score    × 0.10
```

All scores should be normalised to a range between `0` and `1`.

### Routing strategies

```text
balanced
lowest_cost
lowest_latency
highest_reputation
highest_availability
sticky_session
custom_weighted
```

### Example route request

```json
{
  "capability": "inference.text-generation",
  "constraints": {
    "maximum_price": {
      "amount": "0.02",
      "currency": "USDX"
    },
    "maximum_latency_ms": 3000,
    "minimum_success_rate": 0.98,
    "minimum_reputation": 0.95
  },
  "strategy": "balanced"
}
```

### Example route decision

```json
{
  "route_id": "rte_01J9YB8T4V",
  "provider_id": "prv_01J9Y9QN5A",
  "service_id": "svc_01J9YA6K2E",
  "score": 0.947,
  "strategy": "balanced",
  "breakdown": {
    "reputation": 0.992,
    "success_rate": 0.981,
    "latency": 0.918,
    "price": 0.876,
    "availability": 0.999
  },
  "explanation": "Selected for its strong delivery history and low latency while remaining below the maximum price."
}
```

### Failover

Failover is permitted only when:

* The original service request is safe to retry.
* The payment model supports retry or replacement.
* The idempotency state prevents double charging.
* The policy allows another provider.
* The maximum attempt count has not been reached.

Default retry policy:

```text
Maximum provider attempts: 2
Maximum same-provider retries: 1
Retryable conditions:
  - connection failure
  - timeout before provider acceptance
  - explicit temporary-unavailable response
Non-retryable conditions:
  - policy denial
  - invalid payment proof
  - provider accepted and completed side effects
  - malformed agent request
```

---

## Policy Engine

Policies are versioned and immutable after activation.

Editing an active policy creates a new version.

### Policy structure

```json
{
  "name": "Research Agent Policy",
  "version": 4,
  "mode": "enforce",
  "rules": {
    "maximum_per_call": {
      "amount": "0.10",
      "currency": "USDX"
    },
    "daily_budget": {
      "amount": "10.00",
      "currency": "USDX"
    },
    "monthly_budget": {
      "amount": "200.00",
      "currency": "USDX"
    },
    "allowed_capabilities": [
      "research.*",
      "data.market.*",
      "inference.text.*"
    ],
    "blocked_providers": [],
    "minimum_provider_reputation": 0.95,
    "approval_threshold": {
      "amount": "2.00",
      "currency": "USDX"
    },
    "maximum_consecutive_failures": 5
  }
}
```

### Decisions

```text
allow
deny
require_approval
pause_agent
```

### Evaluation order

```text
1. Agent status
2. Emergency stop
3. Session validity
4. Capability access
5. Provider access
6. Currency restrictions
7. Per-call limit
8. Daily budget
9. Monthly budget
10. Provider quality thresholds
11. Failure and drawdown rules
12. Human approval threshold
```

### Policy modes

```text
observe
warn
enforce
```

`observe` records violations without blocking.

`warn` permits the action but generates an alert.

`enforce` blocks the action.

Production agents should use `enforce`.

---

## MCP Integration

PaxRelay supports MCP in two directions.

### Provider-side MCP integration

An MCP server exposes paid tools through the PaxRelay Gateway.

```python
from paxrelay_mcp import PaxRelayMCPServer, paid_tool

server = PaxRelayMCPServer(
    provider_id="prv_searchlabs",
    signing_key_env="PAXRELAY_PROVIDER_SIGNING_KEY",
)


@paid_tool(
    capability="research.web-search",
    price="0.005 USDX",
    timeout_seconds=20,
)
async def search_web(query: str, limit: int = 10) -> dict:
    return {
        "query": query,
        "results": [],
    }


if __name__ == "__main__":
    server.run()
```

### Agent-side MCP integration

```python
from paxrelay_mcp import PaxRelayClient

client = PaxRelayClient(
    base_url="https://gateway.paxrelay.dev",
    api_key="pr_live_example",
    agent_id="agt_research",
)

result = await client.invoke(
    capability="research.web-search",
    arguments={
        "query": "Paxeer Network",
        "limit": 5,
    },
    idempotency_key="research-job-2026-08-01-001",
)
```

### MCP configuration example

```json
{
  "mcpServers": {
    "paxrelay": {
      "command": "uvx",
      "args": ["paxrelay-mcp"],
      "env": {
        "PAXRELAY_API_KEY": "${PAXRELAY_API_KEY}",
        "PAXRELAY_AGENT_ID": "${PAXRELAY_AGENT_ID}",
        "PAXRELAY_GATEWAY_URL": "https://gateway.paxrelay.dev"
      }
    }
  }
}
```

### PaxRelay MCP tools

The hosted PaxRelay MCP server should expose:

```text
paxrelay.discover_services
paxrelay.get_quote
paxrelay.invoke_service
paxrelay.get_payment
paxrelay.get_receipt
paxrelay.get_agent_budget
paxrelay.cancel_pending_request
```

---

## Provider SDK

### Python FastAPI middleware

```python
from fastapi import FastAPI
from paxrelay.fastapi import PaxRelayMiddleware

app = FastAPI()

app.add_middleware(
    PaxRelayMiddleware,
    provider_id="prv_example",
    service_id="svc_search",
    price="0.005 USDX",
)


@app.post("/search")
async def search(payload: dict):
    return {
        "query": payload["query"],
        "results": [],
    }
```

### TypeScript Express middleware

```typescript
import express from "express";
import { paxRelayPayment } from "@paxrelay/express";

const app = express();

app.use(
  "/search",
  paxRelayPayment({
    providerId: "prv_example",
    serviceId: "svc_search",
    price: "0.005 USDX",
  }),
);

app.post("/search", async (request, response) => {
  response.json({
    query: request.body.query,
    results: [],
  });
});
```

### Service manifest

```yaml
name: Search API
slug: search-api
capability: research.web-search
version: 1.0.0

protocols:
  - http
  - mcp

pricing:
  model: per_call
  amount: "0.005"
  currency: USDX

delivery:
  timeout_seconds: 20
  maximum_request_bytes: 32768
  idempotent: true

health:
  endpoint: /health
  interval_seconds: 30

authentication:
  provider_signature: required
```

---

## Agent SDK

### Python

```python
from paxrelay import PaxRelay

relay = PaxRelay(
    api_key="pr_live_example",
    agent_id="agt_research",
)

result = await relay.call(
    capability="research.web-search",
    arguments={
        "query": "machine-to-machine payments",
    },
    constraints={
        "maximum_price": "0.02 USDX",
        "minimum_reputation": 0.95,
        "maximum_latency_ms": 3000,
    },
    idempotency_key="job-0182-search-01",
)

print(result.output)
print(result.receipt.id)
```

### TypeScript

```typescript
import { PaxRelay } from "@paxrelay/sdk";

const relay = new PaxRelay({
  apiKey: process.env.PAXRELAY_API_KEY!,
  agentId: "agt_research",
});

const result = await relay.call({
  capability: "research.web-search",
  arguments: {
    query: "machine-to-machine payments",
  },
  constraints: {
    maximumPrice: "0.02 USDX",
    minimumReputation: 0.95,
    maximumLatencyMs: 3000,
  },
  idempotencyKey: "job-0182-search-01",
});

console.log(result.output);
console.log(result.receipt.id);
```

---

## Payment and Settlement Model

### Payment requirement

A payment requirement should contain:

```json
{
  "version": "1",
  "payment_scheme": "402LXP",
  "network": "paxeer",
  "chain_id": 125,
  "settlement_layer": "layerx",
  "currency": "USDX",
  "amount_atomic": "5000",
  "recipient": "0xProviderAddress",
  "quote_id": "qte_01J9YDN67A",
  "request_hash": "0xRequestHash",
  "expires_at": "2026-08-01T15:10:00Z",
  "nonce": "0xUniqueNonce"
}
```

### Quote rules

Every quote must be:

* Bound to one request hash.
* Bound to one provider.
* Bound to one service version.
* Bound to one currency and amount.
* Time limited.
* Protected against replay.
* Persisted before being returned.
* Signed by the gateway or provider.

### Payment verification

Verification must check:

* Correct network.
* Correct settlement layer.
* Correct asset.
* Correct recipient.
* Correct amount.
* Correct quote ID.
* Correct request hash.
* Correct nonce.
* Quote has not expired.
* Proof has not been used.
* Payment has sufficient finality for the configured environment.

### Settlement reconciliation

The worker runs an internal consistency pass followed by a leased external
evidence pass. It locks candidate rows only while claiming or saving them; HTTP
requests run outside database transactions. Claims expire after a lease and
due records retry with capped exponential backoff. The payment row is never
advanced by reconciliation.

The reconciler confirms:

```text
Payment agrees with its intent, quote, and originating tool call
Quote request hash, network, recipient, scheme, and settlement layer are valid
LayerX transaction exists at the stored transaction hash
LayerX transaction matches the stored amount, recipient, and quote ID
LayerX settlement evidence identifies the same payment and batch
Paxeer settlement record and batch identify the same commitment
The reported batch transaction list includes the LayerX transaction
Paxeer JSON-RPC confirms the claimed L1 transaction and block
The canonical receipt contains the configured contract event and commitment
```

Missing or unavailable evidence remains `awaiting_external` or
`layerx_confirmed` and is retried. Explicit conflicts become `mismatch`, are
visible through the tenant-scoped settlement review API, and emit
`settlement.mismatch` through the transactional outbox. `reconciled` means all
required evidence was present. The worker does not promote `PaymentModel.state`.

The adapter expects LayerX resources at `GET /transactions/{transaction_hash}`
and `GET /batches/{batch_id}`, plus a Paxeer settlement resource at
`GET /settlement/{settlement_id}`. These HTTP contracts remain assumptions and
must be confirmed with the network operator.
L1 receipt verification checks the configured chain ID, successful receipt,
canonical block, confirmation depth, deployed settlement contract, event topic,
and exact `bytes32` commitment. Production requires the contract address,
event topic, and confirmation depth. Batch IDs are opaque LayerX references,
not transaction hashes. The worker does not independently
recompute the LayerX batch commitment, so the operator must confirm how the
batch response's transaction list relates to the on-chain commitment before
using reconciliation for financial operations.

---

## Execution Receipts

A receipt proves what PaxRelay observed during a paid service call.

It is not necessarily proof that the provider’s output was factually correct.

### Receipt contents

```json
{
  "receipt_id": "rcp_01J9YF4KAS",
  "version": "1",
  "tool_call_id": "call_01J9YEZB3N",
  "agent_id": "agt_research",
  "provider_id": "prv_searchlabs",
  "service_id": "svc_websearch",
  "service_version": "1.0.0",
  "capability": "research.web-search",
  "request_hash": "0xRequestHash",
  "response_hash": "0xResponseHash",
  "payment": {
    "scheme": "402LXP",
    "currency": "USDX",
    "amount_atomic": "5000",
    "payment_id": "pay_01J9YF18NE",
    "layerx_transaction": "0xLayerXTransaction",
    "l1_settlement": null
  },
  "execution": {
    "started_at": "2026-08-01T14:00:02Z",
    "completed_at": "2026-08-01T14:00:03Z",
    "latency_ms": 874,
    "status": "succeeded"
  },
  "routing": {
    "route_id": "rte_01J9YEX31G",
    "strategy": "balanced",
    "score": 0.947
  },
  "issued_at": "2026-08-01T14:00:03Z",
  "signature": "0xReceiptSignature"
}
```

### Canonicalisation

Before signing, PaxRelay removes `signature`, `receipt_hash`, and
`signing_key_id`; sorts object keys by UTF-16 code units; normalizes UUIDs and
timestamps; preserves integers exactly; and emits finite floats as normalized
decimal JSON number tokens. It then serializes compact UTF-8 JSON, computes a
SHA-256 digest, and signs the digest with low-S ECDSA. The exact rules and a
cross-language vector are documented in `docs/execution-receipts.md` and
`docs/receipt-test-vectors.md`. The independent Node.js reference verifier is
`tools/verify-receipt.mjs`; its sample receipt and public key are under
`docs/vectors/`. Python consumers can use the `ReceiptKeyring` in
`packages/receipts` to resolve signing key IDs and enforce activation,
retirement, and revocation windows from a versioned public-key manifest. The
control-plane API serves the configured manifest at the public
`GET /v1/receipt-keys` endpoint, and the Python SDK provides
`paxrelay.fetch_receipt_keyring(url)` to retrieve and validate it.

### Storage

The database stores:

* Receipt metadata.
* Receipt hash.
* Signature.
* Storage location.
* Verification status.

Large request or response bodies should not be stored directly by default. Store hashes and optionally encrypted object-storage references.

---

## API Design

Base URL:

```text
https://api.paxrelay.dev/v1
```

Gateway URL:

```text
https://gateway.paxrelay.dev/v1
```

### Organisations

| Method  | Endpoint                      | Description              |
| ------- | ----------------------------- | ------------------------ |
| `POST`  | `/organisations`              | Create an organisation   |
| `GET`   | `/organisations/{id}`         | Retrieve an organisation |
| `PATCH` | `/organisations/{id}`         | Update an organisation   |
| `GET`   | `/organisations/{id}/members` | List members             |

### Projects

| Method  | Endpoint         | Description        |
| ------- | ---------------- | ------------------ |
| `POST`  | `/projects`      | Create a project   |
| `GET`   | `/projects`      | List projects      |
| `GET`   | `/projects/{id}` | Retrieve a project |
| `PATCH` | `/projects/{id}` | Update a project   |

### Agents

| Method  | Endpoint              | Description            |
| ------- | --------------------- | ---------------------- |
| `POST`  | `/agents`             | Register an agent      |
| `GET`   | `/agents`             | List agents            |
| `GET`   | `/agents/{id}`        | Retrieve an agent      |
| `PATCH` | `/agents/{id}`        | Update an agent        |
| `POST`  | `/agents/{id}/pause`  | Pause an agent         |
| `POST`  | `/agents/{id}/resume` | Resume an agent        |
| `GET`   | `/agents/{id}/spend`  | Retrieve spending data |

### Policies

| Method | Endpoint                                  | Description          |
| ------ | ----------------------------------------- | -------------------- |
| `POST` | `/policies`                               | Create a policy      |
| `GET`  | `/policies`                               | List policies        |
| `GET`  | `/policies/{id}`                          | Retrieve a policy    |
| `POST` | `/policies/{id}/versions`                 | Create a new version |
| `POST` | `/policies/{id}/evaluate`                 | Test a policy        |
| `POST` | `/agents/{agent_id}/policies/{policy_id}` | Assign a policy      |

### Providers and services

| Method | Endpoint                  | Description         |
| ------ | ------------------------- | ------------------- |
| `POST` | `/providers`              | Register a provider |
| `GET`  | `/providers`              | List providers      |
| `GET`  | `/providers/{id}`         | Retrieve a provider |
| `POST` | `/providers/{id}/verify`  | Verify ownership    |
| `POST` | `/services`               | Publish a service   |
| `GET`  | `/services`               | Search services     |
| `GET`  | `/services/{id}`          | Retrieve a service  |
| `POST` | `/services/{id}/versions` | Publish a version   |
| `POST` | `/services/{id}/disable`  | Disable a service   |

### Routing

| Method | Endpoint           | Description                      |
| ------ | ------------------ | -------------------------------- |
| `POST` | `/routes/resolve`  | Select a provider                |
| `GET`  | `/routes/{id}`     | Retrieve a route decision        |
| `POST` | `/routes/simulate` | Simulate routing without payment |

### Payments

| Method | Endpoint                    | Description               |
| ------ | --------------------------- | ------------------------- |
| `POST` | `/payments/quotes`          | Create a payment quote    |
| `POST` | `/payments/verify`          | Verify a payment proof    |
| `GET`  | `/payments/{id}`            | Retrieve payment state    |
| `GET`  | `/payments/{id}/settlement` | Retrieve settlement state |

### Tool calls

| Method | Endpoint               | Description             |
| ------ | ---------------------- | ----------------------- |
| `POST` | `/calls`               | Invoke a paid service   |
| `GET`  | `/calls`               | List tool calls         |
| `GET`  | `/calls/{id}`          | Retrieve a tool call    |
| `POST` | `/calls/{id}/cancel`   | Cancel a pending call   |
| `GET`  | `/calls/{id}/attempts` | List execution attempts |

### Receipts

| Method | Endpoint                    | Description               |
| ------ | --------------------------- | ------------------------- |
| `GET`  | `/receipts/{id}`            | Retrieve a receipt        |
| `POST` | `/receipts/verify`          | Verify a receipt          |
| `GET`  | `/receipts/{id}/settlement` | Retrieve anchoring status |

### Approvals

| Method | Endpoint                   | Description                 |
| ------ | -------------------------- | --------------------------- |
| `GET`  | `/approvals`               | List approval requests      |
| `POST` | `/approvals/{id}/decision` | Approve or reject a request |

### Webhooks

| Method   | Endpoint                    | Description       |
| -------- | --------------------------- | ----------------- |
| `POST`   | `/webhooks`                 | Create a webhook  |
| `GET`    | `/webhooks`                 | List webhooks     |
| `DELETE` | `/webhooks/{id}`            | Delete a webhook  |
| `GET`    | `/webhooks/{id}/deliveries` | View deliveries   |
| `POST`   | `/webhooks/{id}/test`       | Send a test event |

---

## Events and Webhooks

### Event types

```text
agent.created
agent.paused
agent.budget.warning
agent.budget.exhausted

provider.created
provider.verified
provider.unhealthy
provider.recovered

service.published
service.disabled
service.enabled

policy.created
policy.updated
policy.violation

approval.requested
approval.approved
approval.rejected
approval.expired

payment.quote.created
payment.submitted
payment.verified
payment.failed
payment.settled.layerx
payment.anchored.l1

call.created
call.executing
call.succeeded
call.failed

receipt.created
receipt.verified

settlement.reconciled
settlement.mismatch
```

### Webhook signature

```text
X-PaxRelay-Event
X-PaxRelay-Event-Id
X-PaxRelay-Delivery-Id
X-PaxRelay-Timestamp
X-PaxRelay-Signature
```

Signature input:

```text
timestamp + "." + delivery_id + "." + event_type + "." + raw_request_body
```

The timestamp, event type, event ID, and delivery ID identify the signed
request. Delivery is at least once; consumers should use constant-time HMAC
comparison and deduplicate delivery IDs. The worker currently emits
`agent.created`, `provider.created`, `policy.created`, `service.published`,
`service.disabled`, `service.enabled`, and approval decision/expiration
events. Other event types in the enum are available for subscriptions but are
not yet wired to producers.

Webhook consumers must reject:

* Invalid signatures.
* Timestamps outside the accepted tolerance.
* Previously processed delivery IDs.

---

## Authentication and Authorisation

### Dashboard users

Current staging and production dashboards use Auth.js with an OIDC provider.
The web server holds the encrypted HTTP-only session, then sends short-lived,
single-use signed assertions to the control-plane API. The API links verified
OIDC subjects to provisioned PaxRelay users and checks active project and
environment roles for each request. Bootstrap requires an initial owner email
for protected environments; owners and administrators manage memberships in
the Settings page. The browser does not hold a production machine API key.

Further identity controls can include:

* Email verification.
* Optional passkeys.
* Optional wallet authentication.
* Multi-factor authentication for sensitive actions.
* Short-lived access sessions.
* Refresh-token rotation.

### API clients

Use project-scoped API keys for machine integrations:

```text
pk_...
```

Store only hashed API keys.

### Agent authentication

The current gateway accepts a bearer project API key with the `gateway:invoke`
scope and an `X-Agent-Id` selector. It verifies that the selected active agent
matches the key's organisation, project, and environment. The key can invoke as
any active agent in that project; per-agent credentials are a future option.

Agents may authenticate through:

* Scoped API key.
* Signed wallet challenge.
* Delegated session key.
* Mutual TLS for enterprise deployments.

### Roles

```text
owner
admin
operator
analyst
viewer
```

Roles are scoped to one project and environment. The API maps each role to
resource scopes and enforces those scopes on every request.

### Sensitive operations

The following should require stronger permission checks:

* Creating production API keys.
* Changing wallet configuration.
* Raising spending limits.
* Disabling policy enforcement.
* Approving high-value payments.
* Rotating provider signing keys.
* Exporting audit logs.
* Deleting webhook endpoints.

---

## Security Model

### Key management

PaxRelay must never log:

* Private keys.
* Seed phrases.
* Complete bearer tokens.
* Complete session keys.
* Unredacted payment proofs.

Production signers should use:

* Cloud KMS.
* Hardware security modules.
* Dedicated wallet infrastructure.
* MPC signing services.
* User-controlled wallet signatures.

Local private keys are permitted only in local and test environments.

### Idempotency

Every paid call must include an idempotency key.

Uniqueness boundary:

```text
project_id + agent_id + idempotency_key
```

The database must enforce uniqueness.

Current gateway behavior serializes request intake with a PostgreSQL
transaction advisory lock for `(agent_id, idempotency_key)`. Repeating the same
request returns its active payment requirement or, after successful delivery,
the saved provider result and signed receipt without forwarding to the provider
again. Reusing the key with different arguments, capability, or constraints
returns HTTP 409. Migration `0010_tool_call_result_replay` stores the bounded
JSON provider result on the tool-call row. Calls completed before that
migration have no saved result and cannot replay the full response. Concurrent
database behavior and recovery of interrupted in-progress calls still require
verification.

### Replay protection

Bind payment proofs to:

* Quote ID.
* Agent.
* Provider.
* Service version.
* Request hash.
* Amount.
* Currency.
* Nonce.
* Expiration time.

### SSRF protection

Provider URLs must be validated.

Block access to:

```text
localhost
127.0.0.0/8
10.0.0.0/8
172.16.0.0/12
192.168.0.0/16
169.254.0.0/16
cloud metadata endpoints
unsupported protocols
```

Enterprise private-network support should use an explicit private connector rather than disabling SSRF protection globally.

### Request protection

* Maximum request sizes.
* Maximum response sizes.
* Content-type allowlists.
* Connection timeouts.
* Read timeouts.
* Provider concurrency limits.
* JSON depth limits.
* Schema validation.
* Malware scanning for uploaded files.

### Audit logging

Record:

* Actor.
* Organisation.
* Project.
* Action.
* Resource.
* Previous value hash.
* New value hash.
* Source IP.
* User agent.
* Request ID.
* Timestamp.

Audit logs should be append-only.

### Dependency security

* Dependabot.
* Renovate or equivalent.
* Python dependency scanning.
* npm audit.
* Trivy container scanning.
* Semgrep.
* CodeQL.
* Secret scanning.
* Signed release artifacts.
* Software bill of materials.

---

## Reliability and Fault Tolerance

### Database

Railway PostgreSQL is the source of truth for:

* Requests.
* Payments.
* Policies.
* Receipts.
* Settlements.
* Audit logs.
* Outbox events.

### Redis

Railway Redis is used for:

* Rate limiting.
* Short-lived caching.
* Distributed locks.
* Quote caching.
* Nonce replay detection.
* Provider health snapshots.
* Temporary routing state.

Railway Redis must not be the only storage location for payment or settlement data.

### Transactional outbox

When an application transaction generates an event, both the domain change and outbox record must be committed in one PostgreSQL transaction.

```text
BEGIN
  update payment state
  insert settlement event into outbox
COMMIT
```

The worker dispatches the event after commit.

### Circuit breakers

Open a provider circuit when:

* Consecutive failures exceed the threshold.
* Timeout rate exceeds the threshold.
* Health checks fail repeatedly.
* Invalid signatures are returned.
* Provider responses violate the service schema.

### Reconciliation

Periodic reconciliation detects:

* Verified payments without executions.
* Executions without receipts.
* LayerX payments without L1 batch references.
* L1 records that do not match local records.
* Duplicate provider executions.
* Expired approvals still marked as pending.

### Graceful degradation

When Paxeer registry access is unavailable:

* Use a recently cached registry result only within its configured freshness limit.
* Do not publish new services.
* Clearly mark routing decisions as cache-derived.

When settlement verification is unavailable:

* Do not treat unknown payment state as verified.
* Return a retryable service-unavailable response.

---

## Observability

### Structured logging

Every log should include:

```text
request_id
trace_id
organisation_id
project_id
agent_id
provider_id
service_id
tool_call_id
payment_id
route_id
environment
```

### Metrics

Gateway metrics:

```text
paxrelay_gateway_requests_total
paxrelay_gateway_request_duration_seconds
paxrelay_gateway_payment_challenges_total
paxrelay_gateway_payment_verification_failures_total
paxrelay_gateway_provider_timeouts_total
```

Payment metrics:

```text
paxrelay_payments_total
paxrelay_payment_amount_atomic
paxrelay_payment_verification_duration_seconds
paxrelay_settlement_reconciliation_lag_seconds
paxrelay_settlement_mismatches_total
```

Routing metrics:

```text
paxrelay_routes_total
paxrelay_route_score
paxrelay_provider_failovers_total
paxrelay_provider_circuit_state
```

Policy metrics:

```text
paxrelay_policy_decisions_total
paxrelay_policy_denials_total
paxrelay_approval_requests_total
```

### Distributed tracing

Trace the complete path:

```text
Agent
  -> Gateway
  -> Policy Engine
  -> Router
  -> LayerX verification
  -> Provider
  -> Receipt Service
  -> Database
```

Never attach sensitive request bodies or payment secrets to traces.

---

## Local Development

### Prerequisites

Install:

* Node.js `22` or later.
* pnpm `10` or later.
* Python `3.12` or later.
* uv.
* Docker.
* Docker Compose.
* Git.
* Foundry for contract development.

### Clone the repository

```bash
git clone https://github.com/thetruesammyjay/paxrelay.git
cd paxrelay
```

### Install JavaScript dependencies

```bash
pnpm install
```

### Install Python dependencies

```bash
uv sync --all-packages
```

### Configure environment variables

```bash
cp .env.example .env
```

### Start local infrastructure

```bash
docker compose up -d postgres redis
```

The Docker services are intended for local development. Production uses Railway PostgreSQL and Railway Redis.

### Run database migrations

```bash
cd apps/api
uv run python -m alembic upgrade head
```

The same command works from `packages/db`. Alembic uses the shared migrations
under `packages/db` and reads `DATABASE_URL` from the current folder's `.env`,
with the repository root `.env` as a fallback.

### Seed development data

```bash
uv run python scripts/seed.py
```

### Start all applications

```bash
pnpm dev
```

Or:

```bash
make dev
```

### Start applications individually

```bash
pnpm --filter web dev
uv run --package paxrelay-api fastapi dev apps/api/src/paxrelay_api/main.py
uv run --package paxrelay-gateway fastapi dev apps/gateway/src/paxrelay_gateway/main.py
uv run --package paxrelay-worker python -m paxrelay_worker
uv run --package paxrelay-simulator python -m paxrelay_simulator
```

### Default local URLs

```text
Dashboard:       http://localhost:3000
API:             http://localhost:8000
API docs:        http://localhost:8000/docs
Gateway:         http://localhost:8080
Simulator:       http://localhost:8090
Documentation:   http://localhost:3001
```

### Common commands

```bash
make install
make dev
make lint
make format
make typecheck
make test
make test-unit
make test-integration
make test-e2e
make migrate
make seed
make generate
make build
make clean
```

---

## Environment Variables

```dotenv
# Application
APP_ENV=development
APP_NAME=PaxRelay
LOG_LEVEL=INFO
API_BASE_URL=http://localhost:8000
API_MAX_REQUEST_BYTES=1048576
GATEWAY_BASE_URL=http://localhost:8080
WEB_BASE_URL=http://localhost:3000

# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis
RAILWAY_REDIS_URL=redis://localhost:6379
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=paxrelay
API_RATE_LIMIT_MAX_REQUESTS=300
API_RATE_LIMIT_WINDOW_SECONDS=60

# Authentication
AUTH_SECRET=replace-me
JWT_ISSUER=paxrelay
JWT_AUDIENCE=paxrelay-api
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_SECONDS=2592000

# Encryption
APPLICATION_ENCRYPTION_KEY=replace-me
RECEIPT_SIGNING_BACKEND=local
RECEIPT_SIGNING_PRIVATE_KEY=
RECEIPT_SIGNING_KEY_ID=local-development

# Paxeer
PAXEER_CHAIN_ID=125
PAXEER_RPC_URL=https://public-rpc.paxeer.app/rpc
PAXEER_EXPLORER_URL=https://paxscan.io
PAXEER_CONFIRMATION_POLICY=layerx_verified
PAXEER_NETWORK_ENVIRONMENT=mainnet

# LayerX
LAYERX_API_URL=
LAYERX_RPC_URL=
LAYERX_USDX_ADDRESS=
LAYERX_PAYMENT_VERIFIER_ADDRESS=
LAYERX_REGISTRY_ADDRESS=
LAYERX_SETTLEMENT_RECORD_ADDRESS=

# 402LXP
LXP402_ENABLED=true
LXP402_QUOTE_TTL_SECONDS=300
LXP402_MAX_CLOCK_SKEW_SECONDS=30
LXP402_REQUIRE_REQUEST_HASH=true

# Provider routing
ROUTER_DEFAULT_STRATEGY=balanced
ROUTER_REGISTRY_CACHE_TTL_SECONDS=30
ROUTER_MAX_PROVIDER_ATTEMPTS=2
ROUTER_HEALTH_FAILURE_THRESHOLD=3
ROUTER_CIRCUIT_OPEN_SECONDS=60

# Gateway
GATEWAY_REQUEST_TIMEOUT_SECONDS=30
GATEWAY_CONNECT_TIMEOUT_SECONDS=5
GATEWAY_MAX_REQUEST_BYTES=1048576
GATEWAY_MAX_RESPONSE_BYTES=10485760
GATEWAY_RATE_LIMIT_MAX_REQUESTS=120
GATEWAY_RATE_LIMIT_WINDOW_SECONDS=60
GATEWAY_MAX_CONCURRENT_REQUESTS_PER_KEY=10
GATEWAY_CONCURRENCY_LEASE_SECONDS=600
# Optional override; enabled by default in staging/production.
# GATEWAY_RATE_LIMIT_ENABLED=true

# Object storage
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET=paxrelay-receipts
S3_REGION=auto

# Webhooks
WEBHOOK_ENCRYPTION_KEY=replace-me-with-a-secure-random-string
WEBHOOK_MAX_ATTEMPTS=8
WEBHOOK_INITIAL_RETRY_SECONDS=30

# Observability
OTEL_ENABLED=false
OTEL_EXPORTER_OTLP_ENDPOINT=
SENTRY_DSN=
METRICS_ENABLED=true
```

Never commit a populated `.env` file.

Protocol contract addresses should be sourced from official Paxeer deployment records before production use.

---

## Testing Strategy

### Unit tests

Test:

* Policy evaluation.
* Routing scores.
* Quote validation.
* Request hashing.
* Receipt canonicalisation.
* Signature verification.
* Amount conversion.
* State transitions.
* Retry eligibility.

### Integration tests

Test:

* API with PostgreSQL.
* Gateway with simulated LayerX.
* Redis locks.
* Transactional outbox.
* Provider forwarding.
* Webhook signing.
* Settlement reconciliation.

### Contract tests

Test:

* Contract deployment.
* Access control.
* Replay resistance.
* Receipt anchoring.
* Escrow behaviour.
* Event emission.
* Upgrade restrictions.

### End-to-end tests

Primary flow:

```text
Create organisation
Create project
Register agent
Assign policy
Register provider
Publish paid tool
Invoke capability
Receive HTTP 402
Submit simulated payment
Execute provider request
Receive receipt
Verify receipt
Reconcile settlement
View transaction in dashboard
```

### Failure tests

Required scenarios:

* Duplicate idempotency key.
* Reused payment proof.
* Expired quote.
* Wrong payment amount.
* Wrong recipient.
* Provider timeout.
* Provider returns invalid schema.
* Database transaction failure.
* Redis unavailable.
* LayerX verification unavailable.
* L1 settlement delayed.
* Webhook endpoint unavailable.
* Agent budget exhausted.
* Human approval expired.

### Property-based tests

Use property-based testing for:

* Amount conversion.
* Policy combinations.
* Canonical receipt generation.
* State-machine transitions.
* Idempotency invariants.

---

## Deployment

### Recommended initial deployment

```text
Vercel
  - apps/web
  - apps/docs

Railway
  - apps/api
  - apps/gateway
  - apps/worker
  - apps/simulator in staging only
  - PostgreSQL
  - Redis

Cloudflare R2
  - encrypted receipt artifacts

GitHub Actions
  - CI, migrations and deployments
```

### Production topology

```mermaid
flowchart LR
    USER["Users and Agents"] --> CDN["CDN and WAF"]
    CDN --> WEB["Next.js Web"]
    CDN --> GATEWAY["Gateway Replicas"]
    WEB --> API["Control Plane API"]

    GATEWAY --> NEON["Railway PostgreSQL"]
    GATEWAY --> REDIS["Railway Redis"]
    API --> NEON
    API --> REDIS

    WORKER["Worker Replicas"] --> NEON
    WORKER --> REDIS
    WORKER --> PAXEER["Paxeer and LayerX"]

    GATEWAY --> PROVIDERS["Service Providers"]
    GATEWAY --> PAXEER

    RECEIPTS["Object Storage"] <--> GATEWAY
    RECEIPTS <--> WORKER
```

### Deployment rules

* Run migrations as a dedicated release step.
* Do not run schema migrations from every API instance.
* Use readiness and liveness probes.
* Use separate production and staging databases.
* Use separate production and staging signing keys.
* Restrict production contract addresses through configuration validation.
* Deny application startup when required production secrets are missing.
* Keep the simulator disabled in production.
* Protect administrative endpoints behind stronger authentication.

---

## CI/CD

### Pull-request checks

```text
Prettier
ESLint
TypeScript type checking
Ruff
Mypy or Pyright
Pytest
Vitest
Foundry tests
OpenAPI drift check
Database migration check
Secret scanning
Dependency scanning
Container scanning
```

### Main-branch workflow

```text
1. Run all tests.
2. Build containers.
3. Generate software bill of materials.
4. Sign container images.
5. Deploy staging.
6. Run staging smoke tests.
7. Require production approval.
8. Run production migrations.
9. Deploy production.
10. Run production health checks.
```

### Release process

Use semantic versioning:

```text
MAJOR.MINOR.PATCH
```

Public SDKs should be versioned independently through Changesets or an equivalent release system.

---

## Documentation Structure

### `docs/architecture.md`

* System context.
* Application boundaries.
* Data flow.
* Trust boundaries.
* Deployment topology.

### `docs/protocol-integration.md`

* Paxeer RPC configuration.
* Wallet integration.
* LayerX adapter.
* 402LXP adapter.
* Registry adapter.
* Settlement-record adapter.

### `docs/402lxp-flow.md`

* Payment requirement schema.
* Quote lifecycle.
* Payment proof verification.
* Replay protection.
* Error responses.

### `docs/mcp-integration.md`

* Provider adapters.
* Agent adapters.
* Tool manifests.
* MCP configuration examples.

### `docs/policy-engine.md`

* Policy schema.
* Rule evaluation order.
* Policy versioning.
* Approval decisions.
* Policy simulation.

### `docs/provider-routing.md`

* Hard filters.
* Weighted scoring.
* Failover.
* Circuit breakers.
* Routing explanations.

### `docs/execution-receipts.md`

* Receipt schema.
* Hashing.
* Signing.
* Verification.
* Storage.
* Future on-chain anchoring.

### `docs/threat-model.md`

* Assets.
* Actors.
* Trust boundaries.
* Threat scenarios.
* Mitigations.
* Residual risks.

### `docs/operations.md`

* Alerts.
* Runbooks.
* Reconciliation.
* Incident response.
* Key rotation.
* Provider suspension.

---

## Development Roadmap

## Phase 0: Foundation

* [ ] Initialise Turborepo and uv monorepo.
* [ ] Create Next.js dashboard.
* [ ] Create FastAPI control-plane service.
* [ ] Create FastAPI gateway.
* [ ] Configure Railway PostgreSQL.
* [ ] Configure Railway Redis.
* [ ] Add SQLAlchemy and Alembic.
* [ ] Add authentication.
* [ ] Add organisation and project models.
* [ ] Define Paxeer adapter interfaces.
* [ ] Implement local mock adapter.
* [ ] Publish architecture and threat-model documents.

## Phase 1: Paid-call MVP

* [ ] Register agents.
* [ ] Register providers.
* [ ] Publish services.
* [ ] Create per-call pricing.
* [ ] Implement policy evaluation.
* [ ] Implement payment quotes.
* [ ] Implement simulated 402LXP verification.
* [ ] Forward paid HTTP requests.
* [ ] Add idempotency.
* [ ] Generate signed execution receipts.
* [ ] Display transactions in dashboard.
* [ ] Release Python provider SDK.
* [ ] Release Python agent SDK.
* [ ] Publish one paid FastAPI example.

## Phase 2: Paxeer integration

* [ ] Integrate official Paxeer RPC.
* [ ] Integrate policy-bound wallet reads.
* [ ] Integrate LayerX payments.
* [ ] Integrate 402LXP verification.
* [ ] Integrate Paxeer service registry.
* [ ] Index settlement records.
* [ ] Reconcile LayerX payments with L1 batches.
* [ ] Add production configuration validation.
* [ ] Complete independent security review.

## Phase 3: MCP and routing

* [ ] Release Python MCP adapter.
* [ ] Release TypeScript MCP adapter.
* [ ] Release TypeScript SDK.
* [ ] Implement provider scoring.
* [ ] Implement routing strategies.
* [x] Add provider health checks.
* [ ] Add provider circuit breakers.
* [ ] Add safe failover.
* [ ] Add routing explanations.
* [ ] Publish LangChain integration.
* [ ] Publish CrewAI integration.

## Phase 4: Agent treasury

* [ ] Add daily and monthly budgets.
* [ ] Add human approval workflows.
* [ ] Add provider and capability allowlists.
* [ ] Add emergency agent pause.
* [ ] Add delegated session permissions.
* [ ] Add budget alerts.
* [ ] Add team roles.
* [ ] Add finance reporting.
* [ ] Add policy templates.

## Phase 5: Production operations

* [ ] Add advanced observability.
* [ ] Add webhook management.
* [ ] Add provider revenue dashboard.
* [ ] Add settlement mismatch alerts.
* [ ] Add encrypted receipt storage.
* [ ] Add enterprise audit exports.
* [ ] Add regional gateway deployment.
* [ ] Publish service-level objectives.
* [ ] Launch public provider onboarding.

## Phase 6: Verification and trust

* [ ] Add provider-signed outputs.
* [ ] Add optional receipt anchoring.
* [ ] Add TEE attestation adapters.
* [ ] Add provider bonds.
* [ ] Add dispute workflows.
* [ ] Add portable provider reputation.
* [ ] Add verifiable metering.
* [ ] Add streaming-payment support.

---

## Non-Goals

PaxRelay is not initially intended to be:

* A new Layer-1 blockchain.
* A replacement for Paxeer.
* A general-purpose cryptocurrency wallet.
* A decentralised exchange.
* A token launchpad.
* A custodial exchange.
* An AI-agent framework.
* A general consumer marketplace.
* An investment platform.
* A system that guarantees the factual correctness of provider outputs.
* A replacement for protocol-level security controls.

The initial product should remain focused on reliable paid machine-service execution.

---

## Contributing

Contributions are welcome.

### Development workflow

1. Fork the repository.
2. Create a feature branch.
3. Add or update tests.
4. Run linting and type checks.
5. Update documentation.
6. Open a pull request.

```bash
git checkout -b feat/provider-routing
```

### Commit convention

Use Conventional Commits:

```text
feat:
fix:
docs:
refactor:
test:
chore:
ci:
build:
perf:
security:
```

Example:

```text
feat(router): add reputation-weighted provider scoring
```

### Pull requests

Each pull request should include:

* Problem description.
* Proposed solution.
* Testing performed.
* Security implications.
* Database migration details.
* Screenshots for user-interface changes.
* Documentation changes.

Read [CONTRIBUTING.md](./CONTRIBUTING.md) before submitting a pull request.

---

## Security Disclosure

Do not report security vulnerabilities through public GitHub issues.

Report suspected vulnerabilities using the process described in [SECURITY.md](./SECURITY.md).

A complete report should include:

* Affected component.
* Reproduction steps.
* Potential impact.
* Suggested mitigation.
* Proof of concept where safe.

Do not access funds, data or systems belonging to other users while testing.

---

## License

PaxRelay is licensed under the Apache License 2.0.

See [LICENSE](./LICENSE) for the complete terms.

---

## Disclaimer

PaxRelay is experimental software.

It may interact with public blockchain networks, smart contracts, autonomous software, digital assets and irreversible transactions. These systems involve significant technical and financial risk.

Users are responsible for:

* Protecting their keys.
* Reviewing smart contracts.
* Setting appropriate spending policies.
* Testing integrations.
* Confirming network configuration.
* Complying with applicable laws.
* Monitoring autonomous-agent activity.

Nothing in this repository constitutes legal, financial, tax or investment advice.

PaxRelay is an independent project maintained by [@thetruesammyjay](https://github.com/thetruesammyjay). References to Paxeer Network, LayerX, 402LXP, PAX, USDX, Deus and related technologies do not imply endorsement, partnership or official affiliation unless explicitly announced by the relevant parties.

---

## Author

**Samuel Justin Ifiezibe**

GitHub: [@thetruesammyjay](https://github.com/thetruesammyjay)

Repository:

```text
https://github.com/thetruesammyjay/paxrelay
```
