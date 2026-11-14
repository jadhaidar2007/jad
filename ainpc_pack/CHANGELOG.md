# Changelog

## 1.0.0 (2026-11-14)
- First release: AI conversations with configurable NPCs (5 examples).
- Providers: Anthropic Claude (default `claude-haiku-5-5`), OpenAI-compatible (OpenAI, Groq, OpenRouter, Ollama).
- Bridges: QBCore, Qbox, ESX, standalone (auto-detect). Interaction: ox_target, qb-target, E prompt (auto).
- Memory per player per NPC, optional oxmysql persistence.
- Whitelisted action tags with validated arguments and a server event hook; 3 example hooks.
- Cost and safety controls: cooldown, per-player daily cap, global per-minute and per-day caps, abuse filter, timeout, in-character fallbacks, prompt-injection guard, server-side distance check.
- Admin commands: stats, list, test, reload, forget. `/ainpc_coords` helper.
- NUI chat panel; UI in en, ar (RTL), de, es, fr.
