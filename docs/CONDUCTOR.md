# The ONNX Conductor — Interface Contract

## What it is

The ONNX Conductor is the routing layer that sits between memory retrieval and generation.

Without it, the stack is:
```
User query → lean_api /search → fragments → you decide what to do next
```

With it, the stack is:
```
User query → Conductor → [domain, model, temperature, k] → lean_api /search → generation
```

The Conductor makes the routing decision automatically:
- Which knowledge domain does this query belong to?
- Which inference model should respond?
- How many memory fragments to retrieve?
- What generation temperature fits this query type?

It is the thalamus of the CBGT architecture — the structure that routes signals
to the right subsystem at the right moment. In the biological system, the thalamus
does not think. It routes. Routing done right is what makes everything else work.

---

## Why it exists

At small scale — a few hundred queries a day, one person typing — you can route manually.
You know which domain to query. You know which model to use.

At larger scale — continuous operation, telemetry feeds, anomaly alerts, voice queries —
manual routing is the bottleneck. The Conductor removes it.

More importantly: the Conductor learns **your** routing patterns. Over time it reflects
how you actually think — which topics you associate with which knowledge areas,
which query types you want short fast answers to versus long exploratory ones.

That learning is what makes it personal. A generic classifier routes by topic.
A trained Conductor routes by **you**.

---

## The interface contract

This is the full specification. Any implementation that satisfies this contract
plugs into the Mindfield stack.

### Input

```json
{
  "query":   "string — the raw user query",
  "context": [
    {"role": "user",      "content": "previous turn text"},
    {"role": "assistant", "content": "previous response text"}
  ],
  "domains":  ["list", "of", "available", "domain", "names"],
  "chat_id":  "string — session identifier for working memory continuity"
}
```

- `query` — required
- `context` — optional, last 2–4 turns, enables working memory continuity
- `domains` — optional, list of available lean_api domains; conductor chooses from these
- `chat_id` — optional, passed through to lean_api for RWKV blend activation

### Output

```json
{
  "domain":      "string — which domain lean_api to query (or 'main')",
  "model":       "string — which inference model to use",
  "temperature": 0.4,
  "k":           10,
  "instrument":  "string — cognitive mode for this query",
  "confidence":  0.87
}
```

| Field | Type | Description |
|---|---|---|
| `domain` | string | Domain name from your `DOMAINS` config, or `"main"` for the root memory field |
| `model` | string | Model hint — e.g. `"seven_v3_q4"`, `"mamba_direct"`, `"qwen_small"` |
| `temperature` | float [0,1] | Generation temperature — lower for factual, higher for exploratory |
| `k` | int | Number of memory fragments to retrieve from lean_api |
| `instrument` | string | Query mode — `"factual"`, `"exploratory"`, `"technical"`, `"creative"` |
| `confidence` | float [0,1] | Conductor's confidence in this routing decision |

### Instrument values

The `instrument` field shapes how the generation layer handles the retrieved fragments:

| Value | Meaning |
|---|---|
| `"factual"` | Direct answer expected — low temperature, tight k |
| `"technical"` | Precise domain answer — medium temperature, domain-scoped |
| `"exploratory"` | Open-ended synthesis — higher temperature, broad k |
| `"procedural"` | Step-by-step output — low temperature, procedures domain |
| `"diagnostic"` | Anomaly / fault analysis — low temperature, FMEA domain |

---

## How it plugs into the stack

```
                    ┌─────────────────────────────────┐
  User query ──────►│         ONNX Conductor          │
                    │  input:  query + context         │
                    │  output: domain, model, k, temp  │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │   lean_api /search               │
                    │   domain: :18001-18010 or :8018  │
                    │   k: from conductor output       │
                    │   where: optional SQL filter     │
                    └──────────────┬──────────────────┘
                                   │  top-k fragments
                    ┌──────────────▼──────────────────┐
                    │   Generation layer               │
                    │   model:       from conductor    │
                    │   temperature: from conductor    │
                    │   prompt:      fragments + query │
                    └─────────────────────────────────┘
```

The lean_api `/search` endpoint already accepts the fields the conductor populates:

```python
POST /search
{
  "query":   req.query,
  "k":       conductor_output["k"],
  "where":   optional_filter,
  "chat_id": req.chat_id    # activates RWKV blend if server is running
}
```

The `domain` field from the conductor selects which lean_api port to route to.
`"main"` routes to the root memory field on `:8018`.
Named domains route to their configured ports (`:18001`–`:18010` etc.)

---

## What the Conductor is technically

An ONNX model. Small — inference runs in single-digit milliseconds.

**Inputs at inference time:**
- Embedded query vector (768-dim from nomic-embed-text-v1.5)
- Compressed context vector (last N turns, mean-pooled)

**Outputs:**
- Domain classification logits → softmax → domain name
- Model selection logits → softmax → model name
- Temperature regression → scalar
- k regression → integer
- Instrument classification logits → softmax → instrument name

The ONNX format means it runs on any hardware without a Python ML framework at inference time.
`onnxruntime` is the only dependency. CPU inference is fast enough for real-time use.

---

## Building your own

The architecture of the Conductor is straightforward. The value is entirely in the training signal.

**What to train on:**
- Your own query history: what did you ask, what domain was correct, did the result satisfy you?
- Your own routing corrections: when you overrode the default routing, that is the training signal
- Your own interaction patterns: which queries you follow up, which you accept, which you rephrase

**The training signal is personal.** A Conductor trained on your queries routes differently
from one trained on someone else's. That is the point. A generic classifier routes by topic.
A trained Conductor routes by the person who built it.

**Minimum viable training set:**
- 500+ labelled query → (domain, model, instrument) examples from your own use
- Generated from your own query history + corrections

**Architecture reference (what works):**
- Small transformer encoder (4–8 layers) or fine-tuned sentence encoder
- Multi-head output: one head per decision (domain, model, instrument, temperature, k)
- Trained jointly — routing decisions are correlated
- Export to ONNX with `torch.onnx.export` or `tf2onnx`

**Training details are intentionally not provided here.** The architecture above
is enough for someone with ML experience to build their own. The weights of any
specific trained Conductor are the private cognitive property of the person who trained it.
They should never be published.

---

## The stub implementation

If you do not yet have a trained Conductor, a rule-based stub covers the same interface:

```python
# conductor_stub.py — rule-based routing, no ML required
# Drop-in for a trained Conductor during development.

DOMAIN_KEYWORDS = {
    "telemetry":     ["sensor", "anomaly", "out of limit", "telemetry", "data"],
    "procedures":    ["procedure", "checklist", "protocol", "how to", "steps"],
    "fmea":          ["failure", "fault", "anomaly", "root cause", "lessons learned"],
    "propulsion":    ["thruster", "propellant", "burn", "delta-v", "propulsion"],
    "astrodynamics": ["orbit", "trajectory", "maneuver", "rendezvous", "debris"],
    "life_support":  ["CO2", "oxygen", "water", "ECLSS", "atmosphere", "pressure"],
    "comms":         ["signal", "antenna", "link", "bandwidth", "frequency"],
    "science":       ["instrument", "calibration", "observation", "measurement"],
    "regulations":   ["standard", "requirement", "certification", "safety", "NASA-STD"],
    "planetary":     ["Mars", "Europa", "Titan", "planet", "atmosphere", "surface"],
}

def route(query: str, domains: list = None) -> dict:
    query_lower = query.lower()
    scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domains and domain not in domains:
            continue
        scores[domain] = sum(1 for kw in keywords if kw.lower() in query_lower)

    best_domain = max(scores, key=scores.get) if any(scores.values()) else "main"
    is_procedural = any(w in query_lower for w in ["how", "steps", "procedure", "checklist"])
    is_diagnostic  = any(w in query_lower for w in ["why", "cause", "failure", "anomaly"])

    return {
        "domain":      best_domain,
        "model":       "main",
        "temperature": 0.3 if (is_procedural or is_diagnostic) else 0.6,
        "k":           6 if is_procedural else 10,
        "instrument":  "procedural" if is_procedural else ("diagnostic" if is_diagnostic else "factual"),
        "confidence":  0.5,   # stub — always 0.5
    }
```

The stub gives you the full routing behaviour with no training required.
Replace it with a trained ONNX model when you have enough interaction history to train on.

---

## The larger architecture

The Conductor is documented in [ARCHITECTURE.md](ARCHITECTURE.md) as part of the
full CBGT circuit:

```
LanceDB           ↔  CA3 (hippocampus)      — fast associative retrieval
ONNX Conductor    ↔  Thalamus               — routing signal to right subsystem
RWKV blend        ↔  Working memory         — bridges temporal gaps
Mamba CORE        ↔  Cerebellum             — timing, pattern completion, voice
GGUF generation   ↔  Cortex                 — language output
```

The Conductor is the piece that makes the rest function as a circuit rather than
a collection of parts. Without routing, you have components. With routing, you have cognition.

---

*The weights of a trained Conductor are the cognitive property of the person who trained it.
They are the shape of how one mind routes its attention.
Publish the interface. Keep the weights.*
