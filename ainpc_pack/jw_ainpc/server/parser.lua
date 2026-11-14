-- Parses model output: strips [ACTION:name:arg] tags, keeps only whitelisted & valid ones, enforces length.
AINPC = AINPC or {}

local Parser = {}

local function validateArg(def, arg)
    local kind = def.type or 'none'
    if kind == 'none' then
        return true, nil
    elseif kind == 'number' then
        local n = tonumber(arg)
        if not n then return false end
        n = math.floor(n)
        if def.min and n < def.min then n = def.min end
        if def.max and n > def.max then n = def.max end
        return true, n
    elseif kind == 'enum' then
        for _, v in ipairs(def.values or {}) do
            if v == arg then return true, arg end
        end
        return false
    end
    return false
end

local function listHas(list, value)
    for _, v in ipairs(list or {}) do if v == value then return true end end
    return false
end

local function escapePattern(s)
    return (s:gsub('[%^%$%(%)%%%.%[%]%*%+%-%?]', '%%%0'))
end

-- text: raw model reply.
-- opts: actionDefs (Config.Actions), allowed (action names this NPC may use), maxChars,
--       maxActions (default 1), npcName (stripped if the model prefixes it, e.g. "Vinnie: ...").
-- Returns cleanText, actions ({ {name=, arg=} }).
function Parser.parse(text, opts)
    opts = opts or {}
    if type(text) ~= 'string' then text = '' end
    local actionDefs, allowed, maxChars = opts.actionDefs, opts.allowed, opts.maxChars
    local maxActions = opts.maxActions or 1
    local actions = {}

    for name, arg in text:gmatch('%[ACTION:([%w_]+):?([^%]]*)%]') do
        local def = actionDefs and actionDefs[name]
        if def and listHas(allowed, name) and #actions < maxActions then
            local ok, value = validateArg(def, arg ~= '' and arg or nil)
            if ok then actions[#actions + 1] = { name = name, arg = value } end
        end
    end

    -- Remove every tag (valid or not), plus any half-written tag at the end.
    local clean = text:gsub('%[ACTION:[^%]]*%]', '')
    clean = clean:gsub('%[ACTION[^%]]*$', '')
    if opts.npcName and opts.npcName ~= '' then
        clean = clean:gsub('^%s*%**' .. escapePattern(opts.npcName) .. '%**%s*:%s*', '')
    end
    clean = clean:gsub('%s+', ' '):match('^%s*(.-)%s*$') or ''

    if maxChars and maxChars > 0 then
        clean = AINPC.Util.truncateWords(clean, maxChars)
    end
    return clean, actions
end

AINPC.Parser = Parser
