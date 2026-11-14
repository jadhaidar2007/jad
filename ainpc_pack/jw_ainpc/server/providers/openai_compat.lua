-- OpenAI-compatible Chat Completions provider: OpenAI, Groq, OpenRouter, local Ollama, LM Studio...
AINPC = AINPC or {}
AINPC.Providers = AINPC.Providers or {}

local OpenAICompat = {}

function OpenAICompat.buildRequest(pcfg, apiKey, prompt, json)
    local messages = { { role = 'system', content = prompt.system } }
    for _, m in ipairs(prompt.messages) do messages[#messages + 1] = { role = m.role, content = m.content } end
    local body = {
        model = pcfg.model or 'gpt-4o-mini',
        max_tokens = pcfg.maxTokens or 200,
        messages = messages,
    }
    if pcfg.temperature then body.temperature = pcfg.temperature end
    local headers = { ['Content-Type'] = 'application/json' }
    -- Local servers like Ollama need no key.
    if apiKey and apiKey ~= '' then headers['Authorization'] = 'Bearer ' .. apiKey end
    local url = pcfg.url or 'https://api.openai.com/v1/chat/completions'
    return url, 'POST', json.encode(body), headers
end

function OpenAICompat.parseResponse(status, body, json)
    local ok, data = pcall(json.decode, body or '')
    if not ok or type(data) ~= 'table' then
        return false, nil, nil, ('HTTP %s, unreadable body'):format(tostring(status))
    end
    if status ~= 200 then
        local msg = type(data.error) == 'table' and data.error.message or tostring(data.error or 'unknown error')
        return false, nil, nil, ('HTTP %s: %s'):format(tostring(status), msg)
    end
    local choice = data.choices and data.choices[1]
    local text = choice and choice.message and choice.message.content
    if type(text) ~= 'string' or text == '' then return false, nil, nil, 'empty reply' end
    local usage = data.usage or {}
    return true, text, {
        input = tonumber(usage.prompt_tokens) or 0,
        output = tonumber(usage.completion_tokens) or 0,
    }
end

AINPC.Providers.openai_compat = OpenAICompat
