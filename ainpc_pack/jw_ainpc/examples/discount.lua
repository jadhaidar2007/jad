-- Example hook: shop discount. The NPC grants a % discount on the player's NEXT purchase.
-- Your shop script reads it with:  local pct = exports.jw_ainpc:ConsumeDiscount(source)
-- Not escrowed: edit or delete freely.
local discounts = {} -- src -> { pct, expires }

AddEventHandler('jw_ainpc:action', function(src, npcId, action, pct)
    if action ~= 'discount' then return end
    if not src or src <= 0 then return end -- console test (/ainpc test)
    discounts[src] = { pct = pct, expires = os.time() + 600, npc = npcId }
    local text = ('You earned %d%% off your next purchase (10 min).'):format(pct)
    TriggerClientEvent('chat:addMessage', src, { args = { 'Shop', text } })
end)

exports('ConsumeDiscount', function(src)
    local d = discounts[src]
    discounts[src] = nil
    if d and d.expires > os.time() then return d.pct end
    return 0
end)

AddEventHandler('playerDropped', function() discounts[source] = nil end)
