# Pricing proposal

## What the market shows (RESEARCH.md, 2026-11-14)
- Intel NPC / nCore NPC PRO, the closest AI competitor: €30.75 launch, then €55.35, now listed at €60 (one page shows €29.99; unclear). It has far more features (ambient peds, trust, gossip).
- Non-AI dialogue scripts: free (5scripts) to €11.90-€20 (ViceX, Talk To NPC V4).
- Tebex keeps 15% of FiveM sales, plus gateway fees.

## Proposal
| Tier | Price | What | Why |
|---|---|---|---|
| **Launch (first 2 weeks)** | €19.99 | Escrowed, updates for 1.x | Below every AI competitor, buys early reviews. Nets about €17 after Tebex's 15%. |
| **Standard** | €24.99 | Escrowed; config, locales, bridge, hooks and UI open; updates for 1.x | Mid-way between non-AI dialogue scripts (≤€20) and Intel NPC (€55-60), matching our smaller but cleaner scope. |
| **Open Source** | €44.99 | Full unencrypted Lua for teams that want to modify the core | Common pattern (e.g. IC3D sells escrow and open-source variants). Higher price offsets the higher leak risk. |

## Where I disagree with the original plan
The plan suggested "Standard + persistence" as its own tier. I recommend **against** it:
- Persistence is ~60 lines that already ship and are tested. Locking it behind a tier means a second build to maintain and support tickets like "why don't my NPCs remember?".
- Buyers compare against Intel NPC, which includes memory. Withholding it makes us look weaker for no real saving.
Split on **escrowed vs open source** instead: that is a real cost difference (leak risk), and it is how the market already sells.

"Lifetime updates" as a separate tier also adds little. Put "free 1.x updates" in Standard and decide on 2.0 pricing later.

All numbers are proposals. Jad decides; nothing is published.
