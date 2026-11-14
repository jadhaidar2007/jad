-- Qbox bridge. Same PlayerData shape as QBCore, accessed through qbx_core exports.
AINPC = AINPC or {}
AINPC.Bridges = AINPC.Bridges or {}

local function playerData(src)
    local p = exports.qbx_core:GetPlayer(src)
    return p and p.PlayerData
end

AINPC.Bridges.qbx = {
    name = 'qbx',
    resource = 'qbx_core',
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
