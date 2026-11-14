-- Anthropic Messages API provider. https://docs.anthropic.com/en/api/messages
AINPC = AINPC or {}
AINPC.Providers = AINPC.Providers or {}

local Anthropic = {}

-- Returns url, method, body (string), headers. json: encoder table with .encode/.decode.
function Anthropic.buildRequest(pcfg, apiKey, prompt, json)
    local body = {
        model = pcfg.model or 'claude-haiku-5-5',
        max_tokens = pcfg.maxTokens or 200,
        system = prompt.system,
        messages = prompt.messages,
    }
    if pcfg.temperature then body.temperature = pcfg.temperature end
    local headers = {
        ['Content-Type'] = 'application/json',
        ['x-api-key'] = apiKey,
        ['anthropic-version'] = pcfg.apiVersion or '2023-06-01',
    }
    local url = pcfg.url or 'https://api.anthropic.com/v1/messages'
    return url, 'POST', json.encode(body), headers
end

-- Returns ok, text, usage {input=, output=}, errorMessage
function Anthropic.parseResponse(status, body, json)
    local ok, data = pcall(json.decode, body or '')
    if not ok or type(data) ~= 'table' then
        return false, nil, nil, ('HTTP %s, unreadable body'):format(tostring(status))
    end
    if status ~= 200 then
        local msg = data.error and data.error.message or 'unknown error'
        return false, nil, nil, ('HTTP %s: %s'):format(tostring(status), msg)
    end
    local text = {}
    for _, block in ipairs(data.content or {}) do
        if block.type == 'text' and type(block.text) == 'string' then text[#text + 1] = block.text end
    end
    if #text == 0 then return false, nil, nil, 'empty reply' end
    local usage = data.usage or {}
    return true, table.concat(text, ' '), {
        input = tonumber(usage.input_tokens) or 0,
        output = tonumber(usage.output_tokens) or 0,
    }
end

AINPC.Providers.anthropic = Anthropic
