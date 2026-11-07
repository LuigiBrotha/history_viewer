"""The winning Kamp of a Veldslag, read from its infobox (`result`, `combatant1`, `combatant2`).

A Winnaar is a list of 0, 1 or 2 Kampen: [] unknown, one Kamp the winner, two Kampen an
undecided battle (one per side). Strategic results count over tactical ones.
"""

import re

from tools.extract_battles import BREAK, COMMENT, REF, remove_templates, tidy

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
italian east africa, italian libya, italian somaliland, italian eritrea
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
straits settlements, hong kong, british hong kong
"""

_SOVJET = """
soviet union, ussr, red army, soviet navy, soviet air forces, mongolian people's republic,
mongolia, tuvan people's republic
"""

_OVERIG = """
republic of china, china, national revolutionary army, chinese communist party,
eighth route army, new fourth army, yugoslav partisans, chetniks, ethiopian empire, ethiopia,
mexico, iran, imperial state of iran, kingdom of iraq, iraq, spain, francoist spain, turkey,
ireland, kingdom of egypt, egypt, denmark, sweden, switzerland, portugal, vietnam, viet minh,
indonesia, polish underground state, home army, greek resistance, french resistance,
italian resistance movement, kingdom of afghanistan, saudi arabia, siam
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
    "czechoslovak": "westers", "commonwealth": "westers", "filipino": "westers",
    "anglo-american": "westers", "western allied": "westers",
    "soviet": "sovjet", "soviets": "sovjet", "russian": "sovjet", "mongolian": "sovjet",
    "chinese": "overig", "partisan": "overig", "partisans": "overig",
    "yugoslav partisan": "overig", "chetnik": "overig", "ethiopian": "overig",
}
ALLIED = {"allied", "allies", "allied forces"}
AXIS = {"axis", "axis powers"}

_ACTORS = sorted(set(DEMONYMS) | set(COUNTRIES) | ALLIED | AXIS, key=len, reverse=True)
_OUTCOME = re.compile(
    r"(?<![\w.-])(" + "|".join(re.escape(a) for a in _ACTORS) + r")(?![\w-])"
    r"(?:\s+[a-z-]+){0,2}?\s+(victory|victorious|success|defeat|failure)\b"
)
_UNDECIDED = re.compile(r"\b(?:inconclusive|stalemate|indecisive|draw|ceasefire|cease-fire|status quo)\b")
_SIDE = re.compile(
    r"\{\{\s*(?:flag\w*|navy|army|air ?force|naval|ship)\s*\|\s*([^|{}]*)"
    r"|\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]",
    re.IGNORECASE,
)
_FLAG_TEMPLATE = re.compile(r"\{\{\s*(?:flag\w*|navy|army)\s*\|\s*([^|{}]*)[^{}]*\}\}", re.IGNORECASE)
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


def _clauses(result):
    text = COMMENT.sub("", REF.sub("", result or ""))
    text = BREAK.sub("\n", text)
    text = _FLAG_TEMPLATE.sub(lambda m: m.group(1), text)
    text = tidy(remove_templates(text.replace("\n", " ; "))).lower()
    clauses = [c.strip() for c in _CLAUSE.split(text) if c.strip()]
    strategic = [c for c in clauses if "strategic" in c and "tactical" not in c]
    return strategic or clauses


def _clause_winner(clause, columns):
    outcome = _OUTCOME.search(clause)
    if outcome:
        kamp = _actor_kamp(outcome.group(1), columns)
        if kamp is None:
            return None
        if outcome.group(2) in ("defeat", "failure"):
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
