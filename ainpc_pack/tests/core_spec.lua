local H = require('helper')

describe('Core pipeline', function()
    before_each(H.reset)

    it('answers through the provider and returns clean text', function()
        local core, calls = H.newCore()
        local r = H.ask(core, 'unicorn_bartender', 'Got any gossip?')
        assert.equal('Hey pal.', r.text)
        assert.equal(1, r.calls)
        assert.equal(1, #calls)
        local body = json.decode(calls[1].body)
        assert.truthy(body.system:find('Vinnie', 1, true))
        assert.equal('Got any gossip?', body.messages[#body.messages].content)
        assert.equal('test-key', calls[1].headers['x-api-key'])
    end)

    it('keeps memory between messages so the NPC remembers', function()
        local clock = H.clock()
        local core, calls = H.newCore({ clock = clock })
        H.ask(core, 'unicorn_bartender', 'My name is Tony.')
        clock.t = clock.t + 10
        H.ask(core, 'unicorn_bartender', 'Remember me?')
        local body = json.decode(calls[2].body)
        assert.equal(3, #body.messages)
        assert.equal('My name is Tony.', body.messages[1].content)
        assert.equal('assistant', body.messages[2].role)
    end)

    it('fires whitelisted actions and strips the tags', function()
        local core, _, actions = H.newCore({ responder = function()
            return H.anthropicOk('Alright, for you. [ACTION:discount:10]')
        end })
        local r = H.ask(core, 'ammunation_clerk', 'Can I get a deal?')
        assert.equal('Alright, for you.', r.text)
        assert.same({ { src = 1, npc = 'ammunation_clerk', name = 'discount', arg = 10 } }, actions)
    end)

    it('does not fire actions the NPC is not allowed to use', function()
        local core, _, actions = H.newCore({ responder = function()
            return H.anthropicOk('Sure. [ACTION:discount:10]')
        end })
        local r = H.ask(core, 'unicorn_bartender', 'discount?')
        assert.equal('Sure.', r.text)
        assert.same({}, actions)
    end)

    it('replies in character when the API fails, never with an error', function()
        local core = H.newCore({ responder = function() return 500, '{"error":{"message":"overloaded"}}' end })
        local r = H.ask(core, 'unicorn_bartender', 'hi')
        assert.is_string(r.text)
        assert.falsy(r.text:find('overloaded', 1, true))
        assert.truthy(r.meta.error)
        assert.equal(1, core.stats.failures)
    end)

    it('times out and falls back if the HTTP callback never comes', function()
        local timers = {}
        local core, calls = H.newCore({
            responder = function() return nil end, -- never responds
            setTimeout = function(ms, fn) timers[#timers + 1] = { ms = ms, fn = fn } end,
        })
        local r = H.ask(core, 'unicorn_bartender', 'hi')
        assert.is_nil(r.text)
        assert.equal(15000, timers[1].ms)
        timers[1].fn()
        assert.is_string(r.text)
        assert.equal('timeout', r.meta.error:match('timeout'))
        -- a late HTTP response after the timeout must not reply twice
        calls[1].cb(H.anthropicOk('late'))
        assert.equal(1, r.calls)
    end)

    it('blocks a second message while the first is in flight', function()
        local core = H.newCore({ responder = function() return nil end })
        H.ask(core, 'unicorn_bartender', 'one')
        local r = H.ask(core, 'unicorn_bartender', 'two')
        assert.equal('busy', r.meta.blocked)
    end)

    it('applies the cooldown without calling the API', function()
        local core, calls = H.newCore()
        H.ask(core, 'unicorn_bartender', 'one')
        local r = H.ask(core, 'unicorn_bartender', 'two')
        assert.equal('cooldown', r.meta.blocked)
        assert.equal(1, #calls)
        assert.is_string(r.text)
    end)

    it('applies the daily cap', function()
        Config.Limits.dailyPerPlayer = 2
        Config.Limits.cooldownSeconds = 0
        local core, calls = H.newCore()
        H.ask(core, 'unicorn_bartender', 'one'); H.ask(core, 'unicorn_bartender', 'two')
        local r = H.ask(core, 'unicorn_bartender', 'three')
        assert.equal('daily', r.meta.blocked)
        assert.equal(2, #calls)
    end)

    it('filters abuse locally without spending tokens', function()
        local core, calls = H.newCore()
        local r = H.ask(core, 'unicorn_bartender', 'shut up retard')
        assert.equal('abuse', r.meta.blocked)
        assert.equal(0, #calls)
    end)

    it('ignores empty messages and unknown NPCs', function()
        local core, calls = H.newCore()
        assert.equal('empty', H.ask(core, 'unicorn_bartender', '   \n ').meta.blocked)
        assert.equal('unknown_npc', H.ask(core, 'nope', 'hi').meta.error)
        assert.equal(0, #calls)
    end)

    it('refuses to call the API without a key (anthropic)', function()
        local core, calls, _, logs = H.newCore({ key = false })
        local r = H.ask(core, 'unicorn_bartender', 'hi')
        assert.equal('no_key', r.meta.error)
        assert.equal(0, #calls)
        assert.truthy(logs[1].msg:find('jw_ainpc_key', 1, true))
    end)

    it('allows keyless openai_compat (local Ollama)', function()
        Config.Provider = { type = 'openai_compat', url = 'http://127.0.0.1:11434/v1/chat/completions', model = 'llama3.1' }
        local core, calls = H.newCore({ key = false, responder = function()
            return 200, H.json.encode({ choices = { { message = { content = 'Howdy.' } } } })
        end })
        local r = H.ask(core, 'unicorn_bartender', 'hi')
        assert.equal('Howdy.', r.text)
        assert.is_nil(calls[1].headers.Authorization)
    end)

    it('truncates the player message to maxInputChars before sending', function()
        local core, calls = H.newCore()
        H.ask(core, 'unicorn_bartender', string.rep('a', 1000))
        local body = json.decode(calls[1].body)
        assert.equal(200, #body.messages[1].content)
    end)

    it('tracks token usage stats', function()
        Config.Limits.cooldownSeconds = 0
        local core = H.newCore({ responder = function() return H.anthropicOk('ok', 100, 25) end })
        H.ask(core, 'unicorn_bartender', 'a'); H.ask(core, 'pillbox_nurse', 'b')
        assert.equal(2, core.stats.requests)
        assert.equal(200, core.stats.inputTokens)
        assert.equal(50, core.stats.outputTokens)
        assert.truthy(core:statsLine():find('2 requests', 1, true))
    end)

    it('loads and saves memory through persistence when enabled', function()
        Config.Persistence.enabled = true
        local saved = {}
        local persistence = {
            load = function(id, npcId, cb)
                assert.equal('license:p1', id); assert.equal('unicorn_bartender', npcId)
                cb({ { role = 'user', content = 'I am Tony' }, { role = 'assistant', content = 'Hi Tony' } })
            end,
            save = function(id, npcId, list) saved[#saved + 1] = { id = id, npc = npcId, list = list } end,
        }
        local core, calls = H.newCore({ persistence = persistence })
        H.ask(core, 'unicorn_bartender', 'Remember me?')
        local body = json.decode(calls[1].body)
        assert.equal('I am Tony', body.messages[1].content)
        assert.equal(1, #saved)
        assert.equal(4, #saved[1].list)
    end)

    it('applyConfig resets memory, limits and NPC index', function()
        local core = H.newCore()
        H.ask(core, 'unicorn_bartender', 'hi')
        local cfg = Config
        cfg.NPCs = { { id = 'only', name = 'Solo', role = 'x' } }
        core:applyConfig(cfg)
        assert.is_nil(core:getNpc('unicorn_bartender'))
        assert.is_not_nil(core:getNpc('only'))
        assert.equal(0, #core.memory:get('license:p1', 'unicorn_bartender'))
    end)
end)

describe('API key convar', function()
    before_each(H.reset)
    local function convar(v) return function(_, default) return v or default end end

    it('reads the key', function()
        assert.equal('sk-ant-123', AINPC.Core.readApiKey(convar('  sk-ant-123 '), 'jw_ainpc_key'))
    end)
    it('treats empty and placeholder values as missing', function()
        assert.is_nil(AINPC.Core.readApiKey(convar(nil)))
        assert.is_nil(AINPC.Core.readApiKey(convar('your-key-here')))
        assert.is_nil(AINPC.Core.readApiKey(convar('changeme')))
    end)
    it('uses the configured convar name', function()
        local asked
        AINPC.Core.readApiKey(function(name, d) asked = name; return d end, 'my_key')
        assert.equal('my_key', asked)
    end)
end)

describe('Config sanity', function()
    before_each(H.reset)
    it('has 5 example NPCs with unique ids and required fields', function()
        local seen = {}
        assert.equal(5, #Config.NPCs)
        for _, npc in ipairs(Config.NPCs) do
            assert.is_nil(seen[npc.id]); seen[npc.id] = true
            assert.is_string(npc.name); assert.is_string(npc.model); assert.is_string(npc.persona)
            assert.is_number(npc.coords.x); assert.is_number(npc.coords.w)
            for _, a in ipairs(npc.actions or {}) do assert.is_table(Config.Actions[a], npc.id .. ' unknown action ' .. a) end
        end
    end)
    it('never contains an API key', function()
        local f = assert(io.open('jw_ainpc/config.lua'))
        local src = f:read('a'); f:close()
        assert.falsy(src:find('sk%-ant%-%w'))
        assert.falsy(src:find('sk%-%w%w%w%w%w%w%w%w%w%w'))
    end)
end)
