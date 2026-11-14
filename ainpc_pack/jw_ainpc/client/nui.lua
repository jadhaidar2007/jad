-- Chat window: open/close, send to server, receive replies.
local open = false
local current = nil

local WEATHER_HASHES = {}
for _, w in ipairs({ 'CLEAR', 'EXTRASUNNY', 'CLOUDS', 'OVERCAST', 'RAIN', 'CLEARING', 'THUNDER', 'SMOG',
    'FOGGY', 'XMAS', 'SNOW', 'SNOWLIGHT', 'BLIZZARD', 'HALLOWEEN', 'NEUTRAL' }) do
    WEATHER_HASHES[joaat(w)] = w:lower()
end

local function worldContext()
    return { hour = GetClockHours(), weather = WEATHER_HASHES[GetPrevWeatherTypeHashName()] }
end

local function close()
    if not open then return end
    open = false
    SetNuiFocus(false, false)
    SendNUIMessage({ action = 'close' })
    local ped = current and AINPC.GetPed(current.id)
    if ped then ClearPedTasks(PlayerPedId()) end
    AINPC.SetActive(nil)
    current = nil
end

function AINPC.OpenChat(npc)
    if open then return end
    open = true
    current = npc
    AINPC.SetActive(npc.id)
    local ped = AINPC.GetPed(npc.id)
    if ped then
        TaskTurnPedToFaceEntity(PlayerPedId(), ped, 1000)
        TaskLookAtEntity(ped, PlayerPedId(), -1, 2048, 3)
    end
    SetNuiFocus(true, true)
    SendNUIMessage({
        action = 'open',
        npcId = npc.id,
        name = npc.name,
        role = npc.role,
        maxChars = (Config.Limits or {}).maxInputChars or 200,
        strings = AINPC.LocaleTable(),
    })
end

RegisterNUICallback('send', function(data, cb)
    cb('ok')
    if not open or not current then return end
    local msg = type(data) == 'table' and data.message
    if type(msg) ~= 'string' then return end
    msg = AINPC.Util.sanitize(msg, (Config.Limits or {}).maxInputChars or 200)
    if msg == '' then return end
    TriggerServerEvent('jw_ainpc:ask', current.id, msg, worldContext())
end)

RegisterNUICallback('close', function(_, cb)
    cb('ok')
    close()
end)

RegisterNetEvent('jw_ainpc:reply', function(npcId, text)
    if not open or not current or current.id ~= npcId then return end
    SendNUIMessage({ action = 'reply', npcId = npcId, text = text })
end)

-- Auto-close if the player walks away or dies mid-conversation.
CreateThread(function()
    while true do
        Wait(500)
        if open and current then
            local pos = GetEntityCoords(PlayerPedId())
            local c = current.coords
            if #(pos - vector3(c.x, c.y, c.z)) > Config.InteractDistance + 3.0 or IsEntityDead(PlayerPedId()) then
                close()
            end
        end
    end
end)

AddEventHandler('onResourceStop', function(res)
    if res == GetCurrentResourceName() and open then SetNuiFocus(false, false) end
end)
