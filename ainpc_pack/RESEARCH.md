# Research (2026-11-14)

All links were opened through search results tonight. Prices are what the pages showed today; they change.

## 1. FiveM platform facts we rely on
| Topic | Finding | Source |
|---|---|---|
| Manifest | `fx_version 'cerulean'`, `game 'gta5'`. `lua54` is deprecated since June 2025 (all Lua is 5.4) but escrow docs still ask for `lua54 'yes'`, so we keep it. | https://docs.fivem.net/docs/scripting-reference/resource-manifest/ |
| HTTP | `PerformHttpRequest(url, cb(status, body, headers, err), method, data, headers)` server-side. No documented timeout option, so we run our own timer. | https://docs.fivem.net/docs/scripting-reference/runtimes/lua/functions/PerformHttpRequest |
| Escrow | Lua/YFT/YDD/YDR are encrypted; `escrow_ignore` keeps files open (we keep config, locales, bridge, examples open). **NUI is not supported by escrow** (html/js ship readable). Escrowed assets only start on servers whose key belongs to the buying Cfx account. Distribution only via Tebex. | https://docs.fivem.net/docs/server-manual/asset-escrow/ , https://support.cfx.re/hc/en-us/articles/8016100729372 |
| Tebex fee | **FiveM sales carry a 15% platform fee** (vs 5% standard), plus gateway fees (PayPal 2.49% + $0.40). | https://docs.tebex.io/creators/pricing-overview/tebex-fees-and-billing-overview |
| Leaks | Cfx.re suspends servers using leaked assets (announced 8 Aug 2025). Leak forums exist and will likely carry our script; escrow is the mitigation. | https://tkscripts.com/guides/free-vs-paid-fivem-scripts |

## 2. Claude API facts we rely on
- Endpoint `POST https://api.anthropic.com/v1/messages`, headers `x-api-key`, `anthropic-version: 2026-10-21`, `content-type: application/json`.
- Default model `claude-haiku-5-5`: **$0.10 / 1M input, $0.50 / 1M output** (Anthropic first-party price, prompts under 100K tokens).
- Current models **reject `temperature`/`top_p`/`top_k` with HTTP 400** on API version 2026-10-21, so we never send them to Claude.
- Haiku 5.5 thinks adaptively by default and thinking tokens count toward `max_tokens`; we send `output_config.effort = "low"` and allow 400 tokens.
- Responses may contain `thinking` blocks and may stop with `stop_reason: "refusal"` and no text; we read only `text` blocks and fall back to an in-character line otherwise.

**Cost estimate (to verify with `/ainpc stats` on a real server):** a typical NPC turn is ~600-1,200 input tokens (persona + lore + 6 remembered exchanges) and ~60-150 output tokens. At Haiku 5.5 prices that is roughly **$0.0002 per message**, about **$2 per 10,000 messages**. The default global cap (3,000 messages/day) bounds worst-case spend at roughly $0.60/day.

## 3. Competitors
| Product | Price seen | AI? | Notes / gaps | Link |
|---|---|---|---|---|
| Intel NPC / nCore NPC PRO (nCore Development) | €30.75 launch (Jun 2026), then €55.35 (€45 ex VAT), now €60 on intelnpc.com; a later page shows "NPC Pro €29.99" (conflicting, unclear which is current) | Launched as "talk to any ped with AI"; current store copy says "every NPC line is authored content" | Huge (~25k lines), ambient "any ped" + trust/gossip/snitch, multi-framework, no escrow, licence per customer for all their servers. **Main competitor.** Gaps: heavy/complex to configure, launch had escrow/delivery confusion in the forum thread, unclear whether free-form LLM chat is still the core. | https://intelnpc.com/ , https://forum.cfx.re/t/intel-npc-talk-to-any-ped-they-remember-they-gossip-they-snitch-no-escrow-lifetime-updates-legacy-enhanced/5412172 |
| Ten30studio (Cfx forum, Sep 2026) | Free pilot, then custom work | Yes, via **their hosted endpoint** | Not a product you own: your player chat goes through a third party's server. Bartender only. | https://forum.cfx.re/t/available-i-build-ai-npcs-for-fivem-55-second-demo-inside-also-available-for-general-scripting/5424178 |
| ViceX Studios NPC Interact | €17, on sale €11.90 | No (dialogue trees) | Cinematic camera, ESX/QB. Gap: scripted only. | https://vicexstudios.tebex.io/package/7131333 |
| Talk To NPC System V4 | $15-20 (store closed to new sales) | No | Dialogue UI. | https://fivem-store.com/product/talk-to-npc-system-v4-dialog-systemstandalone |
| 5scripts NPC Dialogues | Free | No | Branching trees, escrowed. | https://5scripts.com/product/fivem-npc-dialogues-script |
| finalLy134/fivem-chatgpt (GitHub) | Free | Yes (OpenAI + voice) | Author says it is educational, needs Python + voice server, ~10 s replies. | https://github.com/finalLy134/fivem-chatgpt |
| cloodyservices/Npc-systeme (GitHub) | Free, MIT | Voice TTS, scripted dialogue | Not LLM conversation. | https://github.com/cloodyservices/Npc-systeme |
| FiveM Script Creator listings (ai_npc_conversations, mato-npctalk, ai-npc-interaction) | Free | Yes (OpenAI/Gemini) | AI-generated listings of uneven quality; mato-npctalk is QBCore-only with 4 files. | https://www.fivemscriptcreator.org/scripts/mato-npctalk |

### Where we differentiate (must be true in the listing)
1. **You own it, no middleman:** the server calls the AI provider directly with the owner's key. No third-party endpoint (vs Ten30studio).
2. **Provider choice incl. free local models:** Claude, OpenAI, Groq, OpenRouter, or Ollama on your own box (vs OpenAI-only/Gemini-only free scripts).
3. **Safe "actions" with whitelists:** the AI can only request actions you defined; arguments are validated/clamped; it can never give money. Hooks are plain server events.
4. **Hard cost controls built in:** per-player cooldown, daily caps, global per-minute and per-day ceilings, local abuse filter (no tokens spent), live usage stats.
5. **Simple:** 5 NPCs ready, 5-step install, one config file, works on QBCore/Qbox/ESX/standalone and ox_target/qb-target/E-prompt automatically.
6. **Tested:** 80 unit tests, lint, headless boot simulation (most competitors ship none).

We do **not** beat Intel NPC on breadth (ambient peds, trust meters, gossip network). Don't claim to.

## 4. Pricing signals
- AI NPC scripts: €30-60 (Intel NPC trajectory). Non-AI dialogue scripts: free to €20.
- Tebex takes 15% on FiveM sales; a €24.99 sale nets roughly €20.50 before gateway fees and VAT handling.
- See marketing/pricing.md for the proposal.

## 5. Buyer channels
See marketing/outreach_channels.md. Important rule found: **r/FiveM forbids offering paid content/dev services**; r/FiveMServers allows developer self-promotion only with a Tebex link.
