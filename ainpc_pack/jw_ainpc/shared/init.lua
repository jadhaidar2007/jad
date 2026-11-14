-- Single resource-wide namespace. Everything else hangs off AINPC so we never leak other globals.
AINPC = AINPC or {}
AINPC.VERSION = '1.0.0'
AINPC.RESOURCE = 'jw_ainpc'

local Util = {}
AINPC.Util = Util

-- Strip control characters, collapse whitespace, cap length. Used on every player-supplied string.
function Util.sanitize(text, maxLen)
    if type(text) ~= 'string' then return '' end
    text = text:gsub('[%c]', ' ')
    text = text:gsub('[<>]', '')
    text = text:gsub('%s+', ' ')
    text = text:match('^%s*(.-)%s*$') or ''
    maxLen = maxLen or 200
    if #text > maxLen then
        text = Util.utf8Cut(text, maxLen)
    end
    return text
end

-- Cut a string to at most maxBytes without splitting a UTF-8 sequence (Arabic, accents, etc.).
function Util.utf8Cut(text, maxBytes)
    if #text <= maxBytes then return text end
    local cut = maxBytes
    -- step back while the byte after the cut is a continuation byte (10xxxxxx)
    while cut > 0 do
        local nextByte = text:byte(cut + 1)
        if not nextByte or nextByte < 0x80 or nextByte >= 0xC0 then break end
        cut = cut - 1
    end
    return text:sub(1, cut)
end

-- Truncate on a word boundary and add an ellipsis.
function Util.truncateWords(text, maxChars)
    if #text <= maxChars then return text end
    local cut = Util.utf8Cut(text, maxChars)
    local lastSpace = cut:match('.*()%s')
    if lastSpace and lastSpace > maxChars * 0.6 then
        cut = cut:sub(1, lastSpace - 1)
    end
    cut = cut:gsub('[%s%p]+$', '')
    return cut .. '...'
end

function Util.containsBlockedWord(text, words)
    if not words or #words == 0 then return false end
    local lower = ' ' .. text:lower():gsub('[^%w]', ' ') .. ' '
    for _, w in ipairs(words) do
        if lower:find(' ' .. w:lower() .. ' ', 1, true) then return true end
    end
    return false
end

function Util.moneyBracket(amount, brackets)
    amount = tonumber(amount)
    if not amount then return 'unknown' end
    for _, b in ipairs(brackets) do
        if amount < b.below then return b.label end
    end
    return brackets[#brackets] and brackets[#brackets].final or 'wealthy'
end

function Util.shallowCopy(t)
    local out = {}
    for k, v in pairs(t) do out[k] = v end
    return out
end
