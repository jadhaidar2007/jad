-- The conversation pipeline. No FiveM natives in here: everything game-specific is injected via deps,
-- so the whole flow (limits -> prompt -> HTTP -> parse -> memory -> actions) is unit-testable.
AINPC = AINPC or {}

local Core = {}
Core.__index = Core

--[[ deps:
  config      : the Config table
  json        : { encode, decode }
  getApiKey   : function() -> string|nil
  http        : function(url, method, body, headers, cb(status, body))  (cb must be called exactly once)
  setTimeout  : function(ms, fn) or nil
  log         : function(level, msg)
  onAction    : function(playerSrc, npcId, actionName, arg)
  persistence : optional { load(identifier, npcId, cb(list)), save(identifier, npcId, list) }
  clock       : optional clock for the rate limiter
]]
function Core.new(deps)
    local self = setmetatable({}, Core)
    self.deps = deps
    self:applyConfig(deps.config)
    return self
end

function Core:applyConfig(config)
    self.config = config
    self.deps.config = config
    local limits = config.Limits or {}
    self.limiter = AINPC.RateLimiter.new(limits, self.deps.clock)
    self.memory = AINPC.Memory.new(config.MemoryExchanges or 6)
    self.npcs = {}
    for _, npc in ipairs(config.NPCs or {}) do self.npcs[npc.id] = npc end
    self.inFlight = {}
    self:resetStats()
end

function Core:resetStats()
    self.stats = { day = os.date('%Y-%m-%d'), requests = 0, failures = 0, blocked = 0, inputTokens = 0, outputTokens = 0 }
end

function Core:_statsRoll()
    local today = os.date('%Y-%m-%d')
    if self.stats.day ~= today then
        self.deps.log('info', self:statsLine())
        self:resetStats()
    end
end

function Core:statsLine()
    local s = self.stats
    return ('usage %s: %d requests, %d failed, %d blocked by limits, %d input tokens, %d output tokens')
        :format(s.day, s.requests, s.failures, s.blocked, s.inputTokens, s.outputTokens)
end

function Core:fallback(npc, key)
    local lines = (npc and npc.fallbacks and npc.fallbacks[key]) or (self.config.Fallbacks or {})[key]
    if type(lines) == 'table' and #lines > 0 then return lines[math.random(#lines)] end
    if type(lines) == 'string' then return lines end
    return '...'
end

function Core:getNpc(id) return self.npcs[id] end

--[[ req:
  src        : player server id (or 0 for console)
  identifier : stable player identifier (license / citizenid) used for memory + limits
  npcId, message
  ctx        : player/world context for the prompt
  reply      : function(text, meta) -- always called exactly once
]]
function Core:ask(req)
    self:_statsRoll()
    local reply = req.reply
    local npc = self.npcs[req.npcId]
    if not npc then return reply(nil, { error = 'unknown_npc' }) end

    local cfg = self.config
    local message = AINPC.Util.sanitize(req.message, (cfg.Limits or {}).maxInputChars or 200)
    if message == '' then return reply(self:fallback(npc, 'empty'), { blocked = 'empty' }) end

    if cfg.ProfanityFilter and AINPC.Util.containsBlockedWord(message, cfg.BlockedWords) then
        self.stats.blocked = self.stats.blocked + 1
        return reply(self:fallback(npc, 'abuse'), { blocked = 'abuse' })
    end

    local playerKey = req.identifier or tostring(req.src)
    local started = self.inFlight[playerKey]
    -- A request older than timeout + 15 s is considered lost (e.g. a DB callback that never came back).
    if started and os.time() - started < (cfg.RequestTimeoutSeconds or 15) + 15 then
        return reply(self:fallback(npc, 'busy'), { blocked = 'busy' })
    end

    local ok, reason = self.limiter:check(playerKey)
    if not ok then
        self.stats.blocked = self.stats.blocked + 1
        return reply(self:fallback(npc, reason == 'cooldown' and 'cooldown' or 'limit'), { blocked = reason })
    end

    local apiKey = self.deps.getApiKey()
    local pcfg = cfg.Provider or {}
    local provider = AINPC.Providers[pcfg.type or 'anthropic']
    if not provider then
        self.deps.log('error', 'unknown provider type: ' .. tostring(pcfg.type))
        return reply(self:fallback(npc, 'error'), { error = 'provider' })
    end
    if (not apiKey or apiKey == '') and pcfg.type ~= 'openai_compat' then
        self.deps.log('error', 'no API key set. Add: set jw_ainpc_key "your-key" to server.cfg')
        return reply(self:fallback(npc, 'error'), { error = 'no_key' })
    end

    self.limiter:record(playerKey)
    self.inFlight[playerKey] = os.time()

    local function proceed()
        local history = self.memory:get(playerKey, npc.id)
        local prompt = AINPC.Prompt.build(npc, req.ctx, history, message, cfg)
        local url, method, body, headers = provider.buildRequest(pcfg, apiKey, prompt, self.deps.json)

        local done = false
        local function finish(status, respBody)
            if done then return end
            done = true
            self.inFlight[playerKey] = nil
            self.stats.requests = self.stats.requests + 1

            local good, text, usage, err = provider.parseResponse(status, respBody, self.deps.json)
            if not good then
                self.stats.failures = self.stats.failures + 1
                self.deps.log('warn', ('provider error for npc %s: %s'):format(npc.id, tostring(err)))
                return reply(self:fallback(npc, 'error'), { error = err })
            end
            self.stats.inputTokens = self.stats.inputTokens + usage.input
            self.stats.outputTokens = self.stats.outputTokens + usage.output

            local clean, actions = AINPC.Parser.parse(text, {
                actionDefs = cfg.Actions, allowed = npc.actions, npcName = npc.name,
                maxChars = npc.maxReplyChars or cfg.MaxReplyChars or 300,
            })
            if clean == '' then clean = self:fallback(npc, 'error') end

            self.memory:add(playerKey, npc.id, 'user', message)
            self.memory:add(playerKey, npc.id, 'assistant', clean)
            if self.deps.persistence and cfg.Persistence and cfg.Persistence.enabled and req.identifier then
                self.deps.persistence.save(req.identifier, npc.id, self.memory:get(playerKey, npc.id))
            end

            for _, a in ipairs(actions) do
                self.deps.log('info', ('action %s(%s) from npc %s for player %s')
                    :format(a.name, tostring(a.arg), npc.id, tostring(req.src)))
                self.deps.onAction(req.src, npc.id, a.name, a.arg)
            end
            reply(clean, { actions = actions, usage = usage })
        end

        if self.deps.setTimeout then
            self.deps.setTimeout((cfg.RequestTimeoutSeconds or 15) * 1000, function()
                if not done then finish(0, '{"error":{"message":"timeout"}}') end
            end)
        end
        self.deps.http(url, method, body, headers, finish)
    end

    local persist = self.deps.persistence
    if persist and cfg.Persistence and cfg.Persistence.enabled and req.identifier
        and not self.memory:isLoaded(playerKey, npc.id) then
        persist.load(req.identifier, npc.id, function(list)
            if not self.memory:isLoaded(playerKey, npc.id) then self.memory:set(playerKey, npc.id, list) end
            proceed()
        end)
    else
        self.memory:markLoaded(playerKey, npc.id)
        proceed()
    end
end

-- Reads the API key from a server convar. Returns nil when unset or obviously a placeholder.
function Core.readApiKey(getConvar, convarName)
    local key = getConvar(convarName or 'jw_ainpc_key', '')
    if type(key) ~= 'string' then return nil end
    key = key:match('^%s*(.-)%s*$')
    if key == '' or key:find('your', 1, true) or key == 'changeme' then return nil end
    return key
end

AINPC.Core = Core
