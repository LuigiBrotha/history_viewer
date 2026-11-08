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


def _clauses(result, strategic=("strategic",), tactical=("tactical",)):
    text = COMMENT.sub("", REF.sub("", result or ""))
    text = BREAK.sub(" ; ", text).replace("\n", " ; ")
    text = LINK.sub(r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = INNERMOST_TEMPLATE.sub(lambda m: _expand(m.group(1)), text)
    text = tidy(re.sub(r"\{\{.*", "", text, flags=re.DOTALL)).lower()
    clauses = [c.strip() for c in _CLAUSE.split(text) if c.strip()]
    chosen = [c for c in clauses if any(w in c for w in strategic) and not any(w in c for w in tactical)]
    return chosen or clauses


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


# ---- Other languages -------------------------------------------------------------------
# Country codes of the flag templates (German {{DEU-1935}}, Polish {{państwo|DEU|1935}}).
ISO_KAMP = {
    **dict.fromkeys(["DEU", "ITA", "JPN", "HUN", "ROU", "BGR", "FIN", "SVK", "HRV", "THA", "MAN", "ALB"], "as"),
    **dict.fromkeys(["GBR", "USA", "FRA", "CAN", "AUS", "NZL", "ZAF", "IND", "POL", "NLD", "BEL", "NOR",
                     "LUX", "GRC", "YUG", "CSK", "CZE", "BRA", "PHL"], "westers"),
    **dict.fromkeys(["SUN", "SOV", "URS", "MNG"], "sovjet"),
    **dict.fromkeys(["CHN", "ETH", "MEX", "IRN", "IRQ", "DNK", "ESP", "TUR"], "overig"),
}

# Country names as the other Wikipedias link or write them.
LOCAL_COUNTRIES = {
    "nl": {
        **dict.fromkeys(["nazi-duitsland", "duitsland", "duitse rijk", "derde rijk", "wehrmacht", "koninkrijk italië",
                         "italië", "japans keizerrijk", "japan", "hongarije", "roemenië", "finland", "bulgarije"], "as"),
        **dict.fromkeys(["nederland", "verenigd koninkrijk", "verenigde staten", "frankrijk", "polen", "canada",
                         "australië", "nieuw-zeeland", "belgië", "noorwegen", "griekenland", "joegoslavië",
                         "brits-indië", "zuid-afrika", "tsjecho-slowakije", "vrij frankrijk"], "westers"),
        **dict.fromkeys(["sovjet-unie", "rode leger", "mongolië"], "sovjet"),
        **dict.fromkeys(["republiek china", "china"], "overig"),
    },
    "de": {
        **dict.fromkeys(["deutsches reich", "deutschland", "wehrmacht", "königreich italien", "italien",
                         "japanisches kaiserreich", "japan", "ungarn", "rumänien", "finnland", "bulgarien"], "as"),
        **dict.fromkeys(["vereinigtes königreich", "vereinigte staaten", "frankreich", "polen", "kanada",
                         "australien", "neuseeland", "niederlande", "belgien", "norwegen", "griechenland",
                         "jugoslawien", "britisch-indien", "südafrika", "tschechoslowakei"], "westers"),
        **dict.fromkeys(["sowjetunion", "rote armee", "mongolei"], "sovjet"),
        **dict.fromkeys(["republik china", "china"], "overig"),
    },
    "pl": {
        **dict.fromkeys(["iii rzesza", "niemcy", "wehrmacht", "włochy", "królestwo włoch", "japonia",
                         "cesarstwo japonii", "węgry", "rumunia", "finlandia", "bułgaria", "słowacja"], "as"),
        **dict.fromkeys(["2rp", "ii rzeczpospolita", "polska", "wielka brytania", "usa", "stany zjednoczone",
                         "francja", "kanada", "australia", "nowa zelandia", "holandia", "belgia", "norwegia",
                         "grecja", "jugosławia", "czechosłowacja", "polskie siły zbrojne na zachodzie"], "westers"),
        **dict.fromkeys(["zsrr", "związek radziecki", "armia czerwona", "mongolia"], "sovjet"),
        **dict.fromkeys(["chiny", "republika chińska"], "overig"),
    },
}

# The words for a side in a result, with "allied" for the Allies and "axis" for the Axis.
LOCAL_ACTORS = {
    "nl": {
        **dict.fromkeys(["duitse", "duitsers", "nazi-duitsland", "duitsland", "italiaanse", "japanse", "hongaarse",
                         "roemeense", "finse", "bulgaarse", "asmogendheden"], "as"),
        **dict.fromkeys(["nederlandse", "britse", "amerikaanse", "franse", "poolse", "canadese", "australische",
                         "belgische", "noorse", "griekse", "joegoslavische", "nieuw-zeelandse", "zuid-afrikaanse",
                         "indiase", "britten", "amerikanen"], "westers"),
        **dict.fromkeys(["sovjet", "sovjet-", "russische", "rode leger", "sovjets"], "sovjet"),
        **dict.fromkeys(["chinese", "partizanen"], "overig"),
        **dict.fromkeys(["geallieerde", "geallieerden"], "allied"),
        **dict.fromkeys(["as"], "axis"),
    },
    "de": {
        **dict.fromkeys(["deutscher", "deutsche", "deutschen", "wehrmacht", "italienischer", "japanischer",
                         "japaner", "ungarischer", "rumänischer", "finnischer", "finnen"], "as"),
        **dict.fromkeys(["britischer", "briten", "amerikanischer", "us-amerikanischer", "amerikaner",
                         "französischer", "franzosen", "polnischer", "polen", "kanadischer", "australischer",
                         "norwegischer", "niederländischer", "griechischer", "jugoslawischer"], "westers"),
        **dict.fromkeys(["sowjetischer", "sowjetische", "sowjetischen", "roten armee", "rote armee", "sowjets",
                         "russischer"], "sovjet"),
        **dict.fromkeys(["chinesischer", "chinesen", "partisanen"], "overig"),
        **dict.fromkeys(["alliierten", "alliierter", "alliierte"], "allied"),
        **dict.fromkeys(["achsenmächte", "achse"], "axis"),
    },
    "pl": {
        **dict.fromkeys(["niemców", "niemiec", "niemieckie", "niemcy", "iii rzeszy", "wehrmachtu", "japończyków",
                         "japonii", "japońskie", "włochów", "włoskie", "finów", "fińskie", "węgrów"], "as"),
        **dict.fromkeys(["polaków", "polski", "polskie", "wojska polskiego", "brytyjczyków", "brytyjskie",
                         "amerykanów", "amerykańskie", "francuzów", "francuskie", "norwegów"], "westers"),
        **dict.fromkeys(["armii czerwonej", "zsrr", "radzieckie", "sowieckie", "rosjan", "związku radzieckiego",
                         "wojsk radzieckich"], "sovjet"),
        **dict.fromkeys(["chińczyków", "chin", "chińskie", "partyzantów"], "overig"),
        **dict.fromkeys(["aliantów", "alianckie", "alianci"], "allied"),
        **dict.fromkeys(["państw osi", "osi"], "axis"),
    },
    "ru": {
        **dict.fromkeys(["германии", "нацистской германии", "третьего рейха", "немецких войск", "немецкой армии",
                         "немцев", "вермахта", "германских войск", "японии", "японских войск", "японцев", "италии",
                         "итальянских войск", "финляндии", "финских войск", "финнов", "румынии", "румынских войск",
                         "венгрии", "венгерских войск", "немецко-финских войск", "германо-финских войск"], "as"),
        **dict.fromkeys(["сша", "американских войск", "американцев", "великобритании", "британских войск",
                         "британцев", "англичан", "польши", "польских войск", "поляков", "франции", "французских войск",
                         "канадских войск", "австралийских войск", "новозеландских войск", "норвегии",
                         "норвежских войск", "греции", "греческих войск", "югославии", "нидерландов"], "westers"),
        **dict.fromkeys(["ссср", "советского союза", "советских войск", "советской армии", "красной армии", "ркка",
                         "советского флота", "мнр", "монголии"], "sovjet"),
        **dict.fromkeys(["китая", "китайских войск", "партизан", "нoak"], "overig"),
        **dict.fromkeys(["союзников", "союзных войск", "антигитлеровской коалиции"], "allied"),
        **dict.fromkeys(["оси", "войск оси", "стран оси", "стран «оси»"], "axis"),
    },
    "fr": {
        **dict.fromkeys(["allemande", "allemand", "allemands", "allemandes", "allemagne", "nazie", "wehrmacht",
                         "japonaise", "japonais", "japon", "italienne", "italien", "italiens", "italie",
                         "finlandaise", "finlandais", "finlande", "roumaine", "roumains", "hongroise", "germano-italienne",
                         "italo-allemande", "germano-finlandaise"], "as"),
        **dict.fromkeys(["américaine", "américain", "américains", "états-unis", "britannique", "britanniques",
                         "royaume-uni", "anglaise", "anglais", "française", "français", "france", "france libre",
                         "polonaise", "polonais", "pologne", "canadienne", "canadiens", "australienne", "australiens",
                         "néo-zélandaise", "norvégienne", "grecque", "yougoslave", "néerlandaise", "belge",
                         "franco-britannique", "anglo-américaine", "américano-britannique"], "westers"),
        **dict.fromkeys(["soviétique", "soviétiques", "urss", "armée rouge", "union soviétique", "russe", "russes"],
                        "sovjet"),
        **dict.fromkeys(["chinoise", "chinois", "chine", "partisans", "partisane"], "overig"),
        **dict.fromkeys(["alliée", "alliés", "alliées", "allié", "alliés de la seconde guerre mondiale"], "allied"),
        **dict.fromkeys(["axe", "puissances de l'axe"], "axis"),
    },
    "it": {
        **dict.fromkeys(["tedesca", "tedesco", "tedeschi", "tedesche", "germania", "germania nazista", "wehrmacht",
                         "giapponese", "giapponesi", "giappone", "italiana", "italiano", "italiani", "italiane",
                         "italia", "italo-tedesca", "italo-tedesche", "germano-italiana", "finlandese", "finlandesi",
                         "rumena", "rumeni", "ungherese", "ungheresi", "nazista", "nazisti"], "as"),
        **dict.fromkeys(["statunitense", "statunitensi", "americana", "americano", "americani", "stati uniti",
                         "britannica", "britannico", "britannici", "inglese", "inglesi", "regno unito", "francese",
                         "francesi", "francia", "polacca", "polacchi", "polonia", "canadese", "canadesi",
                         "australiana", "australiani", "neozelandese", "norvegese", "greca", "greci", "jugoslava",
                         "olandese", "belga", "anglo-americana", "angloamericana"], "westers"),
        **dict.fromkeys(["sovietica", "sovietico", "sovietici", "sovietiche", "unione sovietica", "urss",
                         "armata rossa", "russa", "russi"], "sovjet"),
        **dict.fromkeys(["cinese", "cinesi", "cina", "partigiani", "partigiana", "jugoslavi"], "overig"),
        **dict.fromkeys(["alleata", "alleati", "alleate", "alleato", "alleati della seconda guerra mondiale"], "allied"),
        **dict.fromkeys(["asse", "potenze dell'asse"], "axis"),
    },
    "ja": {
        **dict.fromkeys(["日本軍", "日本", "大日本帝国", "日本海軍", "日本陸軍", "ドイツ軍", "ドイツ", "独軍", "イタリア軍",
                         "イタリア", "伊軍", "フィンランド軍", "ルーマニア軍", "ハンガリー軍"], "as"),
        **dict.fromkeys(["アメリカ軍", "米軍", "アメリカ", "アメリカ合衆国", "米国", "米海軍", "アメリカ海軍", "イギリス軍",
                         "英軍", "イギリス", "英国", "オーストラリア軍", "豪軍", "オランダ軍", "フランス軍", "仏軍",
                         "ニュージーランド軍", "カナダ軍", "ポーランド軍", "英印軍", "米英軍"], "westers"),
        **dict.fromkeys(["ソ連軍", "ソビエト連邦", "ソビエト軍", "ソ連", "赤軍", "モンゴル軍"], "sovjet"),
        **dict.fromkeys(["中国軍", "中華民国軍", "国民革命軍", "国民党軍", "八路軍", "中国", "中華民国", "国府軍"], "overig"),
        **dict.fromkeys(["連合国軍", "連合軍", "連合国"], "allied"),
        **dict.fromkeys(["枢軸国", "枢軸軍"], "axis"),
    },
}

_A = "(?P<actor>ACTORS)"
# "victoire de l'armée allemande", "des Alliés", "soviétique": what may stand between the word and the side.
# "vittoria delle forze alleate", "dell'Unione Sovietica".
_IT_OF = r"(?:(?:degli|dei|delle|della|dello|dell['’]|del|di)\s*)?(?:(?:forze|truppe|armate|flotta|esercito)\s+)?"
# "победа флота Великобритании": the kind of force before the side.
_RU_FORCE = r"(?:(?:вмс|флота|войск|армии|сил|авиации)\s+)?"
_FR_OF = r"(?:(?:des|du|de\s+la|de\s+l['’]|de|d['’])\s*)?(?:(?:armée|forces|troupes|flotte)\s+)?"
LOCAL_OUTCOMES = {
    "nl": [(rf"{_A}(?:\s+\w+){{0,2}}?\s*overwinning", "win"), (rf"overwinning\s+(?:voor|van)\s+(?:de\s+|het\s+)?{_A}", "win"),
           (rf"{_A}(?:\s+\w+){{0,2}}?\s*nederlaag", "loss"), (rf"nederlaag\s+(?:voor|van)\s+(?:de\s+|het\s+)?{_A}", "loss"),
           (rf"terugtrekking\s+(?:van\s+)?(?:de\s+)?{_A}", "loss")],
    "de": [(rf"{_A}\s+\w*sieg", "win"), (rf"\w*(?:sieg|erfolg)\s+(?:der|des|für\s+die)\s+{_A}", "win"),
           (rf"{_A}\s+niederlage", "loss"), (rf"niederlage\s+(?:der|des)\s+{_A}", "loss"),
           (rf"(?:abzug|rückzug|kapitulation)\s+(?:der|des)\s+{_A}", "loss")],
    "pl": [(rf"zwycięstwo\s+{_A}", "win"), (rf"{_A}\s+zwycięstwo", "win"),
           (rf"(?:klęska|porażka|kapitulacja|odwrót)\s+{_A}", "loss")],
    "ru": [(rf"побед\w*\s+{_RU_FORCE}{_A}", "win"),
           (rf"(?:поражение|разгром|капитуляция|отступление|отход|провал|уничтожение|эвакуация)\s+{_RU_FORCE}{_A}",
            "loss")],
    "it": [(rf"vittoria\s+(?:\w+\s+){{0,2}}?{_IT_OF}{_A}", "win"),
           (rf"successo\s+(?:\w+\s+){{0,2}}?{_IT_OF}{_A}", "win"),
           (rf"(?:sconfitta|fallimento|ritirata|resa|ripiegamento|evacuazione|capitolazione)\s+(?:\w+\s+){{0,2}}?{_IT_OF}{_A}",
            "loss")],
    "ja": [(rf"{_A}の?(?:戦術的|戦略的|決定的|一方的)?な?(?:勝利|大勝)", "win"),
           (rf"{_A}の?(?:戦術的|戦略的|決定的)?な?(?:敗北|撤退|降伏|全滅|失敗|大敗)", "loss")],
    "fr": [(rf"victoire\s+(?:\w+\s+){{0,2}}?{_FR_OF}{_A}", "win"),
           (rf"succès\s+(?:\w+\s+){{0,2}}?{_FR_OF}{_A}", "win"),
           (rf"(?:défaite|échec|retraite|évacuation|capitulation|reddition|repli)\s+(?:\w+\s+){{0,2}}?{_FR_OF}{_A}", "loss")],
}
LOCAL_UNDECIDED = {
    "nl": r"\b(?:onbeslist|onbesliste|patstelling|gelijkspel|wapenstilstand|staakt-het-vuren)\b",
    "de": r"\b(?:unentschieden|patt|waffenstillstand|unentschiedener)\b",
    "pl": r"(?:nierozstrzygnięt|\bremis\b|\brozejm)",
    "ru": r"(?:ничья|ничейн|неопредел[её]нн|безрезультатн|перемири|прекращени\w*\s+огня)",
    "it": r"(?:stallo|indecis|pareggio|inconcludent|nessun vincitore|armistizio)",
    "ja": r"(?:引き分け|痛み分け|決着つかず|膠着|停戦)",
    "fr": r"(?:indécis|non concluant|statu quo|status quo|match nul|cessez-le-feu)",
}
LOCAL_STRATEGIC = {"nl": (("strateg",), ("tactisch",)), "de": (("strategisch",), ("taktisch",)),
                   "pl": (("strategiczn",), ("taktyczn",)), "ru": (("стратегическ",), ("тактическ",)),
                   "fr": (("stratégique", "strategique"), ("tactique",)), "it": (("strategic",), ("tattic",)),
                   "ja": (("戦略",), ("戦術",))}

_LINK_OR_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}|\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_FLAG_FILE = re.compile(r"flag[ _]of[ _](?:the[ _])?(.+?)\.(?:svg|png)", re.IGNORECASE)


def _template_kamp(lang, body):
    name, *arguments = [part.strip() for part in body.split("|")]
    # {{państwo|DEU|1935}} names its country in the arguments, {{DEU-1935}} in its name.
    candidates = [a for a in arguments if "=" not in a] if name.lower() == "państwo" else [name]
    for candidate in candidates:
        code = candidate.split("-")[0].strip()
        if code.upper() in ISO_KAMP and code.isupper():
            return ISO_KAMP[code.upper()]
        if kamp := LOCAL_COUNTRIES.get(lang, {}).get(_normal(candidate)):
            return kamp
    return None


def other_side_kamp(lang, field):
    """The Kamp of the first known country in a side field of another language, or None."""
    text = COMMENT.sub("", REF.sub("", field or ""))
    for match in _LINK_OR_TEMPLATE.finditer(text):
        template, target, label = match.groups()
        if template is not None:
            if kamp := _template_kamp(lang, template):
                return kamp
            continue
        flag = _FLAG_FILE.search(target)
        if flag:
            if kamp := COUNTRIES.get(_normal(flag.group(1).replace("_", " "))):
                return kamp
            continue
        for name in (target, label):
            if name and (kamp := LOCAL_COUNTRIES.get(lang, {}).get(_normal(name)) or COUNTRIES.get(_normal(name))):
                return kamp
    # Otherwise the first Land the side names, in any of the ways tools.countries knows.
    from tools.countries import COUNTRY_KAMP, side_countries

    lands = side_countries(lang, field)
    return COUNTRY_KAMP[lands[0]] if lands else None


def _local_actor_kamp(lang, actor, columns):
    kind = LOCAL_ACTORS[lang][actor]
    if kind == "allied":
        return _actor_kamp("allied", columns)
    if kind == "axis":
        return "as"
    return kind


def _compiled(lang):
    actors = sorted(LOCAL_ACTORS[lang], key=len, reverse=True)
    # A side is a whole word: "оси" is not the start of "осинового".
    pattern = "(?:" + "|".join(re.escape(a) for a in actors) + ")"
    # Japanese writes no spaces, so there a side runs straight into the next word.
    if lang != "ja":
        pattern += r"(?:(?<=-)|(?![\w-]))"
    return [(re.compile(r.replace("ACTORS", pattern)), kind) for r, kind in LOCAL_OUTCOMES[lang]]


_LOCAL_COMPILED = {lang: _compiled(lang) for lang in LOCAL_OUTCOMES}


def _local_clause_winner(lang, clause, columns):
    found = []
    for pattern, kind in _LOCAL_COMPILED[lang]:
        for match in pattern.finditer(clause):
            found.append((match.start(), kind, match.group("actor")))
    if found:
        _, kind, actor = min(found)
        kamp = _local_actor_kamp(lang, actor, columns)
        if kind == "loss":
            if kamp not in columns:
                return None
            other = [k for k in columns if k and k != kamp]
            return [other[0]] if len(other) == 1 else None
        return [kamp]
    if re.search(LOCAL_UNDECIDED[lang], clause):
        both = {k for k in columns if k}
        return [k for k in KAMPEN if k in both] if len(both) == 2 else None
    return None


def other_winner(lang, fields):
    """The Winnaar from an infobox of another language: a list of Kampen, [] when unknown."""
    from tools.wiki_languages import LANGUAGES

    language = LANGUAGES[lang]
    columns = (other_side_kamp(lang, fields.get(language.side1, "")),
               other_side_kamp(lang, fields.get(language.side2, "")))
    strategic, tactical = LOCAL_STRATEGIC[lang]
    for clause in _clauses(fields.get(language.result, ""), strategic, tactical):
        found = _local_clause_winner(lang, clause, columns)
        if found:
            return found
    return []
