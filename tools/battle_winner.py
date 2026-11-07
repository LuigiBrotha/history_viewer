"""The winning Kamp of a Veldslag, read from its infobox (`result`, `combatant1`, `combatant2`).

A Winnaar is a list of 0, 1 or 2 Kampen: [] unknown, one Kamp the winner, two Kampen an
undecided battle (one per side). Strategic results count over tactical ones.
"""

import re

from tools.extract_battles import BREAK, COMMENT, INNERMOST_TEMPLATE, LINK, REF, tidy

KAMPEN = ("as", "westers", "sovjet", "overig")

_AS = """
nazi germany, germany, german reich, greater german reich, wehrmacht, kriegsmarine, luftwaffe,
heer, waffen-ss, kingdom of italy, italy, italian social republic, fascist italy, regia marina,
regia aeronautica, royal italian army, empire of japan, japan, imperial japanese navy,
imperial japanese army, imperial japanese army air service, kingdom of hungary, hungary,
kingdom of romania, romania, kingdom of bulgaria, bulgaria, slovak republic, slovakia,
first slovak republic, independent state of croatia, croatia, finland, thailand,
vichy france, french state, manchukuo, mengjiang, reorganized national government of china,
wang jingwei regime, azad hind, indian national army, kingdom of albania, albania,
italian east africa, italian libya, italian somaliland, italian eritrea, ger,
second philippine republic, government of national salvation, hellenic state,
protectorate of bohemia and moravia, albanian kingdom
"""

_WESTERS = """
united kingdom, britain, great britain, british empire, royal navy, royal air force,
british army, united states, usa, united states navy, united states army,
united states army air forces, united states marine corps, france, french third republic,
free france, free french forces, provisional government of the french republic, canada,
royal canadian navy, australia, royal australian navy, new zealand, dominion of new zealand,
union of south africa, south africa, british raj, india, british india, newfoundland,
dominion of newfoundland, poland, second polish republic, polish government-in-exile,
polish armed forces in the west, netherlands, dutch east indies, belgium, norway, luxembourg,
kingdom of greece, greece, kingdom of yugoslavia, yugoslavia, czechoslovakia,
czechoslovak government-in-exile, brazil, vargas era, philippines,
commonwealth of the philippines, southern rhodesia, burma, british burma, malaya,
straits settlements, hong kong, british hong kong, uk, ukgbni, us, united states of america,
pol, free french, dutch government-in-exile, greek government-in-exile, gold coast, kenya,
northern rhodesia, fiji, nigeria, nyasaland, british somaliland, uganda, belgian congo,
gilbert and ellice islands, british ceylon, ceylon, jordan, emirate of transjordan,
mandatory palestine, anglo-egyptian sudan, french lebanon
"""

_SOVJET = """
soviet union, ussr, red army, soviet navy, soviet air forces, mongolian people's republic,
mongolia, tuvan people's republic, ukrainian ssr, byelorussian ssr
"""

_OVERIG = """
republic of china, china, national revolutionary army, chinese communist party,
eighth route army, new fourth army, yugoslav partisans, chetniks, ethiopian empire, ethiopia,
mexico, iran, imperial state of iran, kingdom of iraq, iraq, spain, francoist spain, turkey,
ireland, kingdom of egypt, egypt, denmark, sweden, switzerland, portugal, vietnam, viet minh,
indonesia, polish underground state, home army, greek resistance, french resistance,
italian resistance movement, kingdom of afghanistan, saudi arabia, siam,
democratic federal yugoslavia, north vietnam, panama, nepal, pahlavi iran
"""


def _table():
    table = {}
    for kamp, names in (("as", _AS), ("westers", _WESTERS), ("sovjet", _SOVJET), ("overig", _OVERIG)):
        for name in names.split(","):
            if name.strip():
                table[_normal(name)] = kamp
    return table


def _normal(name):
    name = re.sub(r"\([^)]*\)", " ", name)
    return re.sub(r"[\s_]+", " ", name).strip().lower()


COUNTRIES = _table()

# Words used in `result` for a side. "allied" and "axis" are resolved against the columns.
DEMONYMS = {
    "german": "as", "germans": "as", "nazi": "as", "italian": "as", "italians": "as",
    "japanese": "as", "hungarian": "as", "romanian": "as", "bulgarian": "as", "finnish": "as",
    "slovak": "as", "croatian": "as", "thai": "as", "vichy french": "as", "vichy": "as",
    "british": "westers", "american": "westers", "americans": "westers", "us": "westers",
    "u.s.": "westers", "french": "westers", "free french": "westers", "canadian": "westers",
    "australian": "westers", "new zealand": "westers", "indian": "westers", "polish": "westers",
    "dutch": "westers", "belgian": "westers", "norwegian": "westers", "greek": "westers",
    "yugoslav": "westers", "brazilian": "westers", "south african": "westers",
    "czechoslovak": "westers", "czech": "westers", "commonwealth": "westers", "filipino": "westers",
    "anglo-american": "westers", "western allied": "westers",
    "soviet": "sovjet", "soviets": "sovjet", "russian": "sovjet", "mongolian": "sovjet",
    "chinese": "overig", "partisan": "overig", "partisans": "overig",
    "yugoslav partisan": "overig", "chetnik": "overig", "ethiopian": "overig",
    "indonesian": "overig", "francoist": "overig",
}
ALLIED = {"allied", "allies", "allied forces"}
AXIS = {"axis", "axis powers"}

_ACTORS = sorted(set(DEMONYMS) | set(COUNTRIES) | ALLIED | AXIS, key=len, reverse=True)
_LOSS = ("defeat", "failure", "withdrawal", "retreat", "surrender")
_OUTCOME = re.compile(
    r"(?<![\w.-])(" + "|".join(re.escape(a) for a in _ACTORS) + r")(?!\w)(?:-[\w]+)*"
    r"(?:\s+[a-z-]+){0,2}?\s+(victory|victorious|success|" + "|".join(_LOSS) + r")\b"
)
_UNDECIDED = re.compile(r"\b(?:inconclusive|stalemate|indecisive|draw|ceasefire|cease-fire|status quo)\b")
_SIDE = re.compile(
    r"\{\{\s*(?:flag\w*|navy|army|air ?force|naval|ship)\s*\|\s*([^|{}]*)"
    r"|\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]",
    re.IGNORECASE,
)
_LIST_TEMPLATES = {
    "ubl", "ublist", "unbulleted list", "plainlist", "plain list", "indented plainlist", "blist",
    "bulleted list", "flatlist", "hlist", "longitem", "nowrap", "nwr", "nobr", "small", "center",
}
_CLAUSE = re.compile(r"[,;\n*•]|\s+but\s+|\s+and\s+(?=strategic)")


def side_kamp(field):
    """The Kamp of the first known country in a combatant field, or None."""
    text = COMMENT.sub("", REF.sub("", field or ""))
    for match in _SIDE.finditer(text):
        for name in match.groups():
            if name and (kamp := COUNTRIES.get(_normal(name))):
                return kamp
    return None


def _actor_kamp(actor, columns):
    if actor in AXIS:
        return "as"
    if actor in ALLIED:
        known = [k for k in columns if k]
        if "as" in known:
            others = [k for k in known if k != "as"]
            if len(others) == 1:
                return others[0]
        return "westers"
    return DEMONYMS.get(actor) or COUNTRIES.get(actor)


def _expand(body):
    """Keep the items of list templates and the country of flag templates; drop the rest."""
    name, *arguments = [part.strip() for part in body.split("|")]
    name = re.sub(r"[\s_]+", " ", name.lower())
    arguments = [a for a in arguments if "=" not in a]
    if name in _LIST_TEMPLATES:
        return " ; ".join(arguments)
    if (name.startswith("flag") or name in ("navy", "army")) and arguments:
        return arguments[0]
    return ""


def _clauses(result):
    text = COMMENT.sub("", REF.sub("", result or ""))
    text = BREAK.sub(" ; ", text).replace("\n", " ; ")
    text = LINK.sub(r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = INNERMOST_TEMPLATE.sub(lambda m: _expand(m.group(1)), text)
    text = tidy(re.sub(r"\{\{.*", "", text, flags=re.DOTALL)).lower()
    clauses = [c.strip() for c in _CLAUSE.split(text) if c.strip()]
    strategic = [c for c in clauses if "strategic" in c and "tactical" not in c]
    return strategic or clauses


def _clause_winner(clause, columns):
    outcome = _OUTCOME.search(clause)
    if outcome:
        kamp = _actor_kamp(outcome.group(1), columns)
        if kamp is None:
            return None
        if outcome.group(2) in _LOSS:
            if kamp not in columns:
                return None
            other = [k for k in columns if k and k != kamp]
            return [other[0]] if len(other) == 1 else None
        return [kamp]
    if _UNDECIDED.search(clause):
        both = {k for k in columns if k}
        if len(both) == 2:
            return [k for k in KAMPEN if k in both]
        return None
    return None


def winner(fields):
    """The Winnaar of a Veldslag from its infobox fields: a list of Kampen."""
    columns = (side_kamp(fields.get("combatant1", "")), side_kamp(fields.get("combatant2", "")))
    for clause in _clauses(fields.get("result", "")):
        found = _clause_winner(clause, columns)
        if found:
            return found
    return []
