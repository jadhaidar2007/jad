--[[
    jw_ainpc configuration. This file is NOT escrowed: edit freely.
    Every option is documented in CONFIG.md.

    The API key is NOT set here. Put it in server.cfg:
        set jw_ainpc_key "sk-ant-..."
    (`set`, not `setr`/`sets`, so it is never replicated to players.)
]]
Config = {}

Config.Debug = false
Config.Locale = 'en'              -- en, ar, de, es, fr (see locales/)
Config.Framework = 'auto'         -- auto | standalone | qb | qbx | esx
Config.Interaction = 'auto'       -- auto | ox_target | qb-target | prompt

Config.Provider = {
    type = 'anthropic',           -- anthropic | openai_compat
    model = 'claude-haiku-5-5',   -- fast and cheap; any Claude model id works
    maxTokens = 200,
    temperature = 0.8,
    -- url = 'https://api.anthropic.com/v1/messages',
    --
    -- OpenAI-compatible examples (set type = 'openai_compat'):
    --   OpenAI:     url = 'https://api.openai.com/v1/chat/completions',       model = 'gpt-4o-mini'
    --   Groq:       url = 'https://api.groq.com/openai/v1/chat/completions',  model = 'llama-3.1-8b-instant'
    --   OpenRouter: url = 'https://openrouter.ai/api/v1/chat/completions',    model = '...'
    --   Ollama:     url = 'http://127.0.0.1:11434/v1/chat/completions',       model = 'llama3.1' (no key needed)
}
Config.ApiKeyConvar = 'jw_ainpc_key'
Config.RequestTimeoutSeconds = 15

Config.DefaultLanguage = 'English'
Config.MaxReplyChars = 300
Config.MemoryExchanges = 6        -- remembered question/answer pairs per player per NPC

Config.Persistence = {
    enabled = false,              -- requires oxmysql; table is created automatically
    table = 'jw_ainpc_memory',
}

Config.Limits = {
    cooldownSeconds = 4,          -- per player, between messages
    dailyPerPlayer = 80,          -- messages per player per day (0 = unlimited)
    globalPerMinute = 40,         -- all players combined
    globalPerDay = 3000,          -- hard daily ceiling for the whole server (0 = unlimited)
    maxInputChars = 200,
}

Config.ProfanityFilter = true
Config.BlockedWords = { 'nigger', 'faggot', 'retard', 'kys' }

Config.SpawnDistance = 100.0
Config.InteractDistance = 2.5
Config.ServerDistanceCheck = 6.0  -- server rejects messages from players further than this (needs OneSync)

-- Lines used when the NPC can't (or won't) answer. Never shows players an error.
Config.Fallbacks = {
    error = { "Sorry, my head's somewhere else today. Ask me again in a bit.", "Hm? Say that again later, I'm swamped." },
    cooldown = { 'Slow down, one thing at a time.', 'Easy, let me finish my thought.' },
    limit = { "I've talked enough for today. Come back tomorrow.", "I'm done chatting for today, friend." },
    busy = { 'Hold on, I am still thinking about what you said.' },
    abuse = { "Watch your mouth. I don't talk to people like that.", "Keep that up and you're out." },
    empty = { 'You going to say something?' },
}

-- Lore every NPC knows. Keep it short: each line costs tokens on every message.
Config.ServerLore = {
    'The city is Los Santos. The mayor is rarely seen in public.',
    'Locals complain that the LSPD is understaffed at night.',
}

--[[ Whitelisted actions. The model can only *request* these; the server validates them and fires
     TriggerEvent('jw_ainpc:action', playerSrc, npcId, actionName, arg). Hook it in your own resources
     (see examples/). The model can never give money or run code.
     type: none | number (min/max, clamped) | enum (values) ]]
Config.Actions = {
    discount = { type = 'number', min = 5, max = 20,
        description = 'the player haggled well or was very polite; N is the percent discount on their next purchase' },
    give_hint = { type = 'enum', values = { 'heist_1', 'drugs_1' },
        description = 'the player earned your trust and asked about work; X picks which hint' },
    call_cops = { type = 'none',
        description = 'the player threatens you, confesses to a serious crime, or tries to rob you' },
}

--[[ NPCs. Coordinates are vanilla GTA V positions taken from commonly published shop/location data.
     VERIFY THEM IN GAME before going live (MLOs move interiors). Use /ainpc coords in game to print yours. ]]
Config.NPCs = {
    {
        id = 'unicorn_bartender',
        name = 'Vinnie',
        role = 'the bartender at the Vanilla Unicorn strip club',
        model = 's_m_y_barman_01',
        coords = vector4(128.86, -1283.68, 29.27, 120.0), -- TODO verify in game
        scenario = 'WORLD_HUMAN_STAND_IMPATIENT',
        persona = 'Fifty-something, seen everything, dry humor. Loves gossip but never gives it away for free. '
            .. 'Calls everyone "pal". Protective of the dancers.',
        knowledge = {
            'A crew in a black Sultan has been asking about the Fleeca bank on Route 68.',
            'Drinks: beer $10, whiskey $25, the "Unicorn Special" $40.',
        },
        actions = { 'give_hint', 'call_cops' },
        blip = false,
    },
    {
        id = 'pillbox_nurse',
        name = 'Nurse Okafor',
        role = 'a triage nurse at Pillbox Hill Medical Center reception',
        model = 's_f_y_scrubs_01',
        coords = vector4(308.2, -595.1, 43.28, 70.0), -- TODO verify (depends on your Pillbox MLO)
        scenario = 'WORLD_HUMAN_CLIPBOARD',
        persona = 'Calm, kind, very busy, slightly sarcastic about people who get shot every week. '
            .. 'Gives general first-aid style advice in character, never real medical advice.',
        knowledge = { 'Visiting hours end at 22:00.', 'The doctors on shift tonight are short-staffed.' },
        actions = {},
        blip = false,
    },
    {
        id = 'legion_informant',
        name = 'Rat',
        role = 'a jittery street informant who hangs around Legion Square',
        model = 'a_m_m_tramp_01',
        coords = vector4(195.17, -933.77, 30.69, 144.0), -- TODO verify in game
        scenario = 'WORLD_HUMAN_SMOKING',
        persona = 'Paranoid, talks fast, always looking over his shoulder. Sells information, '
            .. 'but only to people who seem trustworthy. Lies to cops.',
        knowledge = {
            'Someone is moving product out of a garage in Sandy Shores.',
            'The Ballas and the Vagos have a truce that will not last.',
        },
        actions = { 'give_hint' },
        blip = false,
    },
    {
        id = 'lspd_desk',
        name = 'Officer Daniels',
        role = 'the front desk officer at Mission Row police station',
        model = 's_m_y_cop_01',
        coords = vector4(441.0, -978.9, 30.69, 180.0), -- TODO verify (depends on your MRPD MLO)
        scenario = 'WORLD_HUMAN_COP_IDLES',
        persona = 'Professional, tired, by the book. Takes reports, explains how to file a complaint, '
            .. 'never reveals active investigations.',
        knowledge = { 'Impounded vehicles are released at the impound lot with ID and a fee.' },
        actions = { 'call_cops' },
        blip = false,
    },
    {
        id = 'ammunation_clerk',
        name = 'Bud',
        role = 'the clerk at the Ammu-Nation store on Adam\'s Apple Boulevard',
        model = 's_m_y_ammucity_01',
        coords = vector4(22.65, -1105.53, 29.80, 160.0), -- TODO verify in game
        scenario = 'WORLD_HUMAN_STAND_IMPATIENT',
        persona = 'Gruff patriot, loves to haggle, respects confidence and hates time-wasters. '
            .. 'Never sells to anyone who seems drunk or threatening.',
        knowledge = { 'Pistol $2500, body armor $800, ammo box $150. A license is required for firearms.' },
        actions = { 'discount', 'call_cops' },
        blip = true,
    },
}
