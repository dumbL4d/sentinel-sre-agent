# Live Model Integration Plan

## Recommendation: Option A — Vertex AI Prediction + sklearn

**Why Option A wins for a 3-day timeline:**

| Criterion | A (Vertex AI) | B (Phoenix sandbox) | C (Public API wrapper) |
|---|---|---|---|
| Setup time | ~4 hours | Unknown availability | ~6 hours |
| Real traces to Phoenix | Native via OpenInference | Already there | Requires custom wrapper |
| Self-improvement loop | Works with real data | Works with real data | Partial |
| Control over data | Full | Limited | Partial |
| Demo impact | High (shows end-to-end) | Medium | Medium |

**Option A** lets you deploy a real model, instrument it, and have Sentinel monitor actual production-grade traces — the strongest demo narrative.

---

## Step-by-Step Implementation

### Step 1: Deploy a Model to Vertex AI Prediction

Create `scripts/deploy_model.py`:

```python
"""Deploy a sklearn classifier to Vertex AI Prediction and instrument with OpenInference."""
import json
import os
import tempfile
from google.cloud import aiplatform
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

PROJECT = os.environ["GCP_PROJECT_ID"]
LOCATION = "us-central1"
MODEL_NAME = "sentinel-demo-model-v1"
ENDPOINT_NAME = "sentinel-demo-endpoint"

def train_and_deploy():
    # Train
    X, y = load_iris(return_X_y=True)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=200)),
    ])
    pipeline.fit(X, y)

    # Save
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
        joblib.dump(pipeline, f.name)
        model_path = f.name

    # Upload to Vertex AI
    aiplatform.init(project=PROJECT, location=LOCATION)
    model = aiplatform.Model.upload(
        display_name=MODEL_NAME,
        artifact_uri=model_path,
        serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-2:latest",
    )

    # Deploy to endpoint
    endpoint = aiplatform.Endpoint.create(display_name=ENDPOINT_NAME)
    model.deploy(endpoint=endpoint, machine_type="n1-standard-2", min_replica_count=1)

    print(f"Model deployed to: {endpoint.resource_name}")
    return endpoint

if __name__ == "__main__":
    train_and_deploy()
```

Run:
```bash
pip install google-cloud-aiplatform scikit-learn joblib
python scripts/deploy_model.py
```

### Step 2: Instrument with OpenInference

Create `scripts/inference_proxy.py` — a FastAPI proxy that wraps the Vertex AI endpoint with OpenInference:

```python
"""OpenInference-instrumented inference proxy that sends traces to Phoenix."""
import os
from fastapi import FastAPI
from google.cloud import aiplatform
from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from opentelemetry import trace
from phoenix.otel import register

app = FastAPI()

# Setup Phoenix tracing
tracer_provider = register(
    project_name="sentinel-live-model",
    endpoint=os.environ["PHOENIX_COLLECTOR_ENDPOINT"],
    api_key=os.environ["PHOENIX_API_KEY"],
    auto_instrument=True,
)

tracer = tracer_provider.get_tracer("sentinel-inference-proxy")

@app.post("/predict")
async def predict(features: list[float]):
    with tracer.start_as_current_span("predict") as span:
        span.set_attribute("model_id", "sentinel-demo-model-v1")
        span.set_attribute("input_size", len(features))

        # Call Vertex AI prediction
        endpoint = aiplatform.Endpoint(os.environ["VERTEX_ENDPOINT_ID"])
        prediction = endpoint.predict(instances=[features])

        span.set_attribute("prediction", str(prediction))
        span.set_attribute("output_size", len(predictions))

    return {"prediction": prediction.predictions[0]}
```

### Step 3: Configure Phoenix to Receive Traces

```bash
export PHOENIX_COLLECTOR_ENDPOINT=https://app.phoenix.arize.com
export PHOENIX_API_KEY=px_live_...
export VERTEX_ENDPOINT_ID=projects/.../locations/.../endpoints/...
uvicorn scripts.inference_proxy:app --port 8081
```

### Step 4: Update Sentinel's QueryMetrics for Live Data

Modify `src/sentinel/tools/query.py` to add a `QueryLiveMetrics` tool:

```python
class QueryLiveMetrics(BaseTool):
    """Query live inference proxy for real-time metrics."""

    name = "query_live_metrics"

    def execute(self, model_id: str, ...):
        # Hit the inference proxy's metrics endpoint
        import httpx
        proxy_url = os.environ.get("INFERENCE_PROXY_URL", "http://localhost:8081")
        resp = httpx.get(f"{proxy_url}/metrics")
        return resp.text
```

### Step 5: Generate Traffic

Run a script that sends requests every few seconds so Phoenix accumulates real traces:

```python
"""Generate synthetic traffic to the live model."""
import time
import random
import requests

PROXY_URL = "http://localhost:8081/predict"

while True:
    features = [random.uniform(4.0, 8.0) for _ in range(4)]
    try:
        resp = requests.post(PROXY_URL, json={"features": features}, timeout=5)
        print(f"Prediction: {resp.json()}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(random.uniform(1, 5))
```

---

## How Sentinel Discovers Live Data

1. Sentinel's `self_introspect` tool calls `ArizeMCPClient.get_evaluation_scores()` which queries real Phoenix span annotations
2. The `QueryLiveMetrics` tool hits the inference proxy for real-time metrics
3. Phoenix traces from the proxy appear in `QueryPhoenixTraces` automatically
4. The self-improvement loop reads actual past evaluation scores from Phoenix annotations

---

## 3-Day Timeline

| Day | Task |
|---|---|
| Day 1 AM | Deploy sklearn model to Vertex AI Prediction |
| Day 1 PM | Build inference proxy with OpenInference instrumentation |
| Day 2 AM | Verify traces flowing to Phoenix Cloud |
| Day 2 PM | Update Sentinel tools to read live data |
| Day 3 AM | Generate traffic, test self-improvement loop with real data |
| Day 3 PM | Demo recording with live traces |
