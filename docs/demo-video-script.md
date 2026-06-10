# Demo Video Script — Sentinel SRE Agent (3 minutes)

**Theme:** "Self-improving ML incident response with Vertex AI ADK + Arize Phoenix"

---

## 0:00–0:30 — Problem Statement

| Visual | Audio |
|---|---|
| Screen: dashboard showing red alerts, latency spikes, error rates climbing | **Narrator:** "ML models in production fail silently. When a sentiment classifier's P99 latency jumps 150% at 2 AM, engineers spend hours manually checking metrics, traces, and logs — often missing the root cause entirely." |
| Cut to: single engineer toggling between 6 tabs | "SRE teams need an agent that doesn't just report problems — but investigates them, correlates signals, and learns from past incidents." |
| Title card: **Sentinel SRE Agent** | "Introducing Sentinel: a self-improving SRE agent that uses Vertex AI ADK for orchestration and Arize Phoenix for observability and memory." |

---

## 0:30–1:15 — Live Demo

| Visual | Audio |
|---|---|
| Screen: Sentinel web UI at /ui | **Narrator:** "Let's see it in action. I'll type a free-form incident: 'Investigate the P99 latency spike in sentiment-classifier-v2.'" |
| Type mission → click Investigate | "Sentinel starts by calling Self-Introspect — querying Arize Phoenix via MCP to find similar past cases." |
| Panel slides in: "Self-Improvement Context" | "It finds three similar latency investigations from last week, including one where the root cause was an upstream API timeout — with an evaluation score of 4.8." |
| Tool calls appear: query_metrics, correlate_signals | "Armed with that context, Sentinel queries live metrics, correlates signals across traces and alerts, and identifies the root cause." |
| Final response renders with markdown | "A new upstream data source is sending oversized payloads. Sentinel recommends a circuit breaker — specific, actionable, and informed by history." |
| Evaluation scores appear: Accuracy 4.5, Completeness 4.0, Actionability 5.0 | "The LLM-as-a-judge scores Sentinel's response. These scores are stored in Phoenix — so next time, Sentinel will learn from this investigation too." |

---

## 1:15–2:00 — Architecture Walkthrough

| Visual | Audio |
|---|---|
| Animated architecture diagram (Mermaid from README): | **Narrator:** "Here's how it works under the hood." |
| Highlight: **Vertex AI ADK** | "Sentinel uses Google's Agent Development Kit — a code-first framework that provides the agent runtime, tool calling, and session management. This satisfies Google Cloud Agent Builder requirement while keeping full control over our custom tool logic." |
| Highlight: **Arize Phoenix** | "Every LLM call and tool execution is traced via OpenInference and sent to Arize Phoenix Cloud. This gives us full observability into every decision the agent makes." |
| Highlight: **MCP Loop** | "The Phoenix MCP server runs alongside Sentinel, enabling the agent to query its own past traces, sessions, and evaluation scores as if they were any other tool. This is the self-improvement loop." |
| Highlight: **11 Custom Tools** | "Our 11 tools — from QueryMetrics to AnalyzeDrift to SuggestRemediation — are registered as ADK FunctionTools with their existing Pydantic schemas. No rewrite needed." |

---

## 2:00–2:45 — Real-Time Monitoring (if live model deployed)

| Visual | Audio |
|---|---|
| Screen split: Vertex AI endpoint dashboard + Phoenix traces | **Narrator:** "We've deployed a live sklearn classifier to Vertex AI Prediction, instrumented with OpenInference." |
| Phoenix UI showing new traces appearing every few seconds | "Real inference requests flow into Phoenix as traces — with latency, error status, and model version attributes." |
| Back to Sentinel: "Check live model health" | "Now I can ask Sentinel: 'Give me a health check of our live model.' Instead of synthetic data, it reads real metrics from Phoenix traces." |
| Sentinel displays actual accuracy, latency P99, error rate | "Sentinel's self-improvement context now shows actual past evaluation scores — not demo data — because the Arize MCP client queries real Phoenix span annotations." |

**Fallback (if no live model):**
| Visual | Audio |
|---|---|
| Screen: Phoenix UI showing traces from demo scenarios | **Narrator:** "We've pre-loaded four demo scenarios into Phoenix — latency spikes, drift detection, critical incidents, and health checks — all producing real traces that Sentinel uses for self-improvement." |
| Click on a trace: shows LLM spans, tool calls, annotations | "Each trace stores evaluation scores, so the self-improvement loop reads actual historical data." |

---

## 2:45–3:00 — Impact Statement & Future Work

| Visual | Audio |
|---|---|
| Screen: bullet points animate in | **Narrator:** "Sentinel turns ML observability from reactive dashboards into proactive, self-improving incident response." |
| Bullet 1: "Vertex AI ADK + Arize Phoenix" | "Google Cloud Agent Builder with full Arize observability — a certified combination." |
| Bullet 2: "Self-improvement via MCP" | "Every investigation makes every future investigation better." |
| Bullet 3: "Production-ready" | "Docker + Cloud Run deployment, CI/CD, Secret Manager, and a streaming web UI." |
| Final card: **Try it: github.com/...** | "We're open-sourcing Sentinel today. Try it with your own Phoenix account — and watch your agents get smarter over time." |

---

## Production Notes

- **Screen recording**: 1920x1080, 30fps
- **Font**: SF Mono for terminal, system UI for browser
- **Background music**: Low-volume ambient/coding playlist
- **Voice**: Clear, moderate pace, emphasize technical terms once
- **Captions**: Include for accessibility
- **Resources needed**: Phoenix Cloud account (free), Gemini API key, deployed Cloud Run URL (for web UI demo)
- **Pre-record segments** to avoid live demo failures
