# Live Verification Report (`docs/live_verification.md`)

**Execution Mode**: `LIVE GEMINI`  
**Date/Time (UTC)**: `2026-10-27 18:18:35 UTC`  
**Total Spend**: `$0.000461 / $0.50`  
**Total Tokens**: `3552 (2689 in / 863 out)`  

## Interaction Telemetry

| Turn | Query | Provider | Model | Lat (ms) | In | Out | Cost | Category | Fallback |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Turn 1 | Explain the core architecture of Apache Iceberg and its snapshot metadata tree. | `gemini` | `gemini-3.5-flash-lite` | 13955.7 | 585 | 318 | $0.000139 | `technical` | Yes (fallback to gemini-3.5-flash-lite) |
| Turn 2 | What are the trade-offs between copy-on-write and merge-on-read in Iceberg tables? | `gemini` | `gemini-3.5-flash-lite` | 19524.8 | 886 | 317 | $0.000162 | `technical` | Yes (fallback to gemini-3.5-flash-lite) |
| Turn 3 | Summarize the key recommendations for data engineers adopting Apache Iceberg. | `gemini` | `gemini-3.5-flash-lite` | 5204.1 | 1218 | 228 | $0.000160 | `technical` | Yes (503 Primary -> gemini-3.5-flash-lite) |

## Resilience & Guardrail Observations
- **Zero Secrets Leaked**: Verification report and logs contain zero credentials.
- **Live Model Response**: Gemini (gemini-3.5-flash-lite) returned valid schema-conforming JSON.
- **Live Fallback Execution**: Resilient router retried on 429 with exponential backoff and safely fell back to Flash Lite; on simulated 503, immediately switched without retries.
- **Financial Accounting**: Per-turn tokens and costs tracked within session budget ($0.50).

✅ Live smoke verification completed successfully.
