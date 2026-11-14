-- Example hook: the NPC calls the police. Plug in your dispatch resource here.
AddEventHandler('jw_ainpc:action', function(src, npcId, action)
    if action ~= 'call_cops' then return end
    local npc = AINPC.core and AINPC.core:getNpc(npcId)
    local c = npc and npc.coords
    print(('[jw_ainpc] %s called the cops on player %s'):format(npcId, src))
    -- Generic event other resources can listen to:
    TriggerEvent('jw_ainpc:policeAlert', { npcId = npcId, playerSrc = src, coords = c })
    -- ps-dispatch example (uncomment if you use it):
    -- TriggerClientEvent('ps-dispatch:client:...', ...)
end)
