# Legitimate free vision options - checked17November2026

Create credentials in your own provider account and enter them only in the app.
No shared/public keys, credential scraping, account creation or billing setup is
performed by StudyFrame. Free eligibility/limits can change; confirm your own
console. The options below are candidates, not a measured quality ranking.

| Option | Current documented offering | Key / setup | StudyFrame v0.3 |
| --- | --- | --- | --- |
| OpenRouter | Free router chooses a compatible model, including image support;50requests/day without purchased credits and20/min; failures can consume quota. Availability varies. | [Own key](https://openrouter.ai/settings/keys) | Implemented/offline tested; live compatibility unverified |
| Google Gemini | Free-tier text/image models; current pricing lists Gemini4Hydrogen with free input/output, with model/account limits. Free-tier content may improve products. | [AI Studio keys](https://aistudio.google.com/api-keys) | Researched, adapter not yet implemented |
| Groq | Vision guide lists qwen/qwen3.8-27b. Published free limits:30RPM,1000RPD,8000TPM,200000TPD; whichever limit is hit first applies. Images consume tokens, so request caps alone overstate capacity. | [Own key](https://console.groq.com/keys) | Researched, adapter not yet implemented |
| Local Ollama | Gemma3:4b supports image input; listed download3.4GB. No hosted API key needed for a local runtime. Local hardware determines usable speed/memory; model terms still apply. | [Model](https://ollama.com/library/gemma3:4b) | Researched, adapter not yet implemented; nothing installed |

Start with OpenRouter for modest public-study experiments because the supported
route has zero-price ceilings and no paid fallback. This is an implementation
choice, not a claim that its random model is best. A provider refusing the requested
data-collection policy can make the free route unavailable. No automatic relaxation.
For a steady long-running screen session, evaluate local vision against your
hardware before assuming cloud-free quotas can sustain it. Open weights and free
hosting are different; an open model is not automatically an unrestricted license.

## Official evidence

- [Free model router](https://openrouter.ai/docs/guides/routing/routers/free-router)
- [Free models and limits](https://openrouter.ai/collections/free-models/)
- [Responses contract](https://openrouter.ai/docs/api_reference/responses/overview)
- [Provider price/data/fallback controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Gemini pricing and free-tier data use](https://aistudio.google.com/docs/pricing)
- [Gemini model modalities](https://aistudio.google.com/docs/models/gemini-4-hydrogen)
- [Groq vision](https://console.groq.com/docs/vision) and [limits](https://console.groq.com/docs/rate-limits)
- [Ollama vision API](https://docs.ollama.com/capabilities/vision)

No live model call, paid charge, personal image transmission or account access was
performed. Never paste keys in chat/issues/Git. Use the masked session field. A
synthetic live question and checked answer are still needed before claiming quality.
