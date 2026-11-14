-- Per player, per NPC conversation memory (in RAM). Persistence is layered on top in persistence.lua.
AINPC = AINPC or {}

local Memory = {}
Memory.__index = Memory

function Memory.new(maxExchanges)
    local self = setmetatable({}, Memory)
    self.maxMessages = math.max(1, maxExchanges or 6) * 2
    self.store = {}
    self.loaded = {}
    return self
end

local function bucket(self, playerKey, npcId)
    self.store[playerKey] = self.store[playerKey] or {}
    self.store[playerKey][npcId] = self.store[playerKey][npcId] or {}
    return self.store[playerKey][npcId]
end

-- Keeps the newest messages. Always starts on a 'user' turn because the Anthropic API rejects
-- a conversation whose first message is from the assistant.
function Memory:trim(list)
    while #list > self.maxMessages do table.remove(list, 1) end
    while list[1] and list[1].role ~= 'user' do table.remove(list, 1) end
    return list
end

function Memory:add(playerKey, npcId, role, content)
    local list = bucket(self, playerKey, npcId)
    list[#list + 1] = { role = role, content = content }
    self:trim(list)
end

function Memory:get(playerKey, npcId)
    local list = bucket(self, playerKey, npcId)
    local out = {}
    for i, m in ipairs(list) do out[i] = { role = m.role, content = m.content } end
    return out
end

-- Replace history (used when loading from the database). Ignores malformed entries.
function Memory:set(playerKey, npcId, list)
    local clean = {}
    if type(list) == 'table' then
        for _, m in ipairs(list) do
            if type(m) == 'table' and (m.role == 'user' or m.role == 'assistant') and type(m.content) == 'string' then
                clean[#clean + 1] = { role = m.role, content = m.content }
            end
        end
    end
    self.store[playerKey] = self.store[playerKey] or {}
    self.store[playerKey][npcId] = self:trim(clean)
    self:markLoaded(playerKey, npcId)
end

function Memory:isLoaded(playerKey, npcId)
    return self.loaded[playerKey .. '|' .. npcId] == true
end

function Memory:markLoaded(playerKey, npcId)
    self.loaded[playerKey .. '|' .. npcId] = true
end

function Memory:forgetPlayer(playerKey)
    self.store[playerKey] = nil
    for k in pairs(self.loaded) do
        if k:sub(1, #playerKey + 1) == playerKey .. '|' then self.loaded[k] = nil end
    end
end

function Memory:clear()
    self.store = {}
    self.loaded = {}
end

AINPC.Memory = Memory
