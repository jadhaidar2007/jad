-- ESX (Legacy) bridge.
AINPC = AINPC or {}
AINPC.Bridges = AINPC.Bridges or {}

local ESX
local function esx()
    if not ESX then ESX = exports.es_extended:getSharedObject() end
    return ESX
end

AINPC.Bridges.esx = {
    name = 'esx',
    resource = 'es_extended',
    getIdentifier = function(src)
        local x = esx().GetPlayerFromId(src)
        return x and x.identifier or AINPC.Bridges.standalone.getIdentifier(src)
    end,
    getContext = function(src)
        local x = esx().GetPlayerFromId(src)
        if not x then return AINPC.Bridges.standalone.getContext(src) end
        local bank = x.getAccount and x.getAccount('bank')
        return {
            playerName = x.getName and x.getName() or GetPlayerName(src),
            job = x.job and (x.job.label or x.job.name),
            moneyAmount = (x.getMoney and x.getMoney() or 0) + (bank and bank.money or 0),
        }
    end,
}
