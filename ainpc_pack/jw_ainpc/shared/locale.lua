-- UI string lookup. NPC replies follow each NPC's `language` instead; this is only for the interface.
AINPC = AINPC or {}
AINPC.Locales = AINPC.Locales or {}

function AINPC.LocaleTable()
    local lang = (Config and Config.Locale) or 'en'
    return AINPC.Locales[lang] or AINPC.Locales.en or {}
end

function AINPC.Locale(key)
    local t = AINPC.LocaleTable()
    return t[key] or (AINPC.Locales.en and AINPC.Locales.en[key]) or key
end
