-- Example hook: quest hints. The model only picks WHICH hint id; the actual text is written by you here,
-- so the AI can never leak something you did not intend.
local HINTS = {
    heist_1 = 'Fleeca on Route 68 changes guards at 02:00. Bring a drill.',
    drugs_1 = 'Ask for "Mags" behind the Sandy Shores laundromat.',
}

AddEventHandler('jw_ainpc:action', function(src, _, action, hintId)
    if action ~= 'give_hint' then return end
    if not src or src <= 0 then return end -- console test (/ainpc test)
    local text = HINTS[hintId]
    if not text then return end
    TriggerClientEvent('chat:addMessage', src, { args = { 'Note', text } })
    -- e.g. give an item instead: exports.ox_inventory:AddItem(src, 'note', 1, { description = text })
end)
