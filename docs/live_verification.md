# Live Verification Report (`docs/live_verification.md`)

**Execution Mode**: `LIVE GEMINI`  
**Date/Time (UTC)**: `2026-10-19 02:56:03 UTC`  
**Total Spend**: `$0.001581 / $0.50`  
**Total Tokens**: `6890 (5187 in / 1703 out)`  

## Interaction Telemetry

| Turn | Query | Provider | Model | Lat (ms) | In | Out | Cost | Category | Fallback |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Turn 1 | Explain the core architecture of Apache Iceberg and its snapshot metadata tree. | `gemini` | `gemini-2.5-flash` | 9272.9 | 585 | 459 | $0.000363 | `technical` | No |
| Turn 2 | What are the trade-offs between copy-on-write and merge-on-read in Iceberg tables? | `gemini` | `gemini-2.5-flash` | 67751.3 | 3083 | 895 | $0.000999 | `technical` | No |
| Turn 3 | Summarize the key recommendations for data engineers adopting Apache Iceberg. | `gemini` | `gemini-2.5-flash-lite` | 2976.6 | 1519 | 349 | $0.000219 | `technical` | Yes (503 Primary -> gemini-2.5-flash-lite) |

## Resilience & Guardrail Observations
- **Zero Secrets Leaked**: Verification report and logs contain zero credentials.
- **Live Primary Response**: Gemini 2.5 Flash returned valid schema-conforming JSON.
- **Live Fallback Execution**: On simulated 503, safely fell back to Flash Lite.
- **Financial Accounting**: Per-turn tokens and costs tracked within session budget.

✅ Live smoke verification completed successfully.
