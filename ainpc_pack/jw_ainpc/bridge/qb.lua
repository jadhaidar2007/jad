-- QBCore bridge.
AINPC = AINPC or {}
AINPC.Bridges = AINPC.Bridges or {}

local QBCore
local function core()
    if not QBCore then QBCore = exports['qb-core']:GetCoreObject() end
    return QBCore
end

local function playerData(src)
    local p = core().Functions.GetPlayer(src)
    return p and p.PlayerData
end

AINPC.Bridges.qb = {
    name = 'qb',
    resource = 'qb-core',
    getIdentifier = function(src)
        local pd = playerData(src)
        return pd and pd.citizenid or AINPC.Bridges.standalone.getIdentifier(src)
    end,
    getContext = function(src)
        local pd = playerData(src)
        if not pd then return AINPC.Bridges.standalone.getContext(src) end
        local ci = pd.charinfo or {}
        local money = pd.money or {}
        return {
            playerName = ((ci.firstname or '') .. ' ' .. (ci.lastname or '')):match('^%s*(.-)%s*$'),
            job = pd.job and (pd.job.label or pd.job.name),
            moneyAmount = (money.cash or 0) + (money.bank or 0),
        }
    end,
}
