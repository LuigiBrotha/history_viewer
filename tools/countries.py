"""The Landen of a Veldslag: every known country on its sides, under one Dutch name.

Infoboxes name a country in many ways: flag templates ({{flag|Nazi Germany}}), country codes
({{DEU-1935}}, {{państwo|DEU|1935}}), links in any language ([[nazi-Duitsland]]), flag files
([[File:Flag of the Netherlands.svg]]) and armed forces ([[Royal Navy]]). Each spelling below
leads to one Land, which belongs to one Kamp.
"""

import re

from tools.battle_winner import COMMENT, REF, _normal

# Land (Dutch name) → (Kamp, spellings). Spellings are compared lower case, without parentheses.
_TABLE = {
    "Duitsland": ("as", "nazi germany, germany, german reich, greater german reich, wehrmacht, kriegsmarine, luftwaffe, "
                        "heer, waffen-ss, ger, deu, nazi-duitsland, duitsland, duitse rijk, derde rijk, deutsches reich, "
                        "deutschland, iii rzesza, niemcy, wehrmachtu"),
    "Italië": ("as", "kingdom of italy, italy, italian social republic, fascist italy, regia marina, regia aeronautica, "
                     "royal italian army, ita, koninkrijk italië, italië, königreich italien, italien, włochy, królestwo włoch, "
                     "italian east africa, italian libya, italian somaliland, italian eritrea"),
    "Japan": ("as", "empire of japan, japan, imperial japanese navy, imperial japanese army, imperial japanese army air service, "
                    "jpn, japans keizerrijk, japanisches kaiserreich, japonia, cesarstwo japonii"),
    "Hongarije": ("as", "kingdom of hungary, hungary, hun, hongarije, ungarn, węgry"),
    "Roemenië": ("as", "kingdom of romania, romania, rou, roemenië, rumänien, rumunia"),
    "Bulgarije": ("as", "kingdom of bulgaria, bulgaria, bgr, bulgarije, bulgarien, bułgaria"),
    "Finland": ("as", "finland, fin, finnland, finlandia"),
    "Slowakije": ("as", "slovak republic, slovakia, first slovak republic, svk, slowakije, slowakei, słowacja"),
    "Kroatië": ("as", "independent state of croatia, croatia, hrv, kroatië, kroatien, chorwacja"),
    "Thailand": ("as", "thailand, siam, tha, tajlandia"),
    "Vichy-Frankrijk": ("as", "vichy france, french state, vichy-frankrijk"),
    "Mantsjoekwo": ("as", "manchukuo, man, mantsjoekwo, mandschukuo, mandżukuo"),
    "Albanië": ("as", "kingdom of albania, albania, albanian kingdom, alb, albanië, albanien, albania"),
    "Verenigd Koninkrijk": ("westers", "united kingdom, uk, ukgbni, britain, great britain, british empire, royal navy, "
                                       "royal air force, british army, gbr, verenigd koninkrijk, vereinigtes königreich, "
                                       "wielka brytania"),
    "Verenigde Staten": ("westers", "united states, usa, us, united states of america, united states navy, "
                                   "united states army, united states army air forces, united states marine corps, "
                                   "verenigde staten, vereinigte staaten, stany zjednoczone"),
    "Frankrijk": ("westers", "france, french third republic, free france, free french, free french forces, "
                             "provisional government of the french republic, fra, frankrijk, vrij frankrijk, frankreich, francja"),
    "Canada": ("westers", "canada, royal canadian navy, can, kanada"),
    "Australië": ("westers", "australia, royal australian navy, aus, australië, australien"),
    "Nieuw-Zeeland": ("westers", "new zealand, dominion of new zealand, nzl, nieuw-zeeland, neuseeland, nowa zelandia"),
    "Zuid-Afrika": ("westers", "union of south africa, south africa, zaf, zuid-afrika, südafrika"),
    "Brits-Indië": ("westers", "british raj, india, british india, ind, brits-indië, britisch-indien"),
    "Polen": ("westers", "poland, second polish republic, polish government-in-exile, polish armed forces in the west, pol, "
                         "polen, 2rp, ii rzeczpospolita, polska, polskie siły zbrojne na zachodzie"),
    "Nederland": ("westers", "netherlands, dutch east indies, dutch government-in-exile, nld, nederland, niederlande, holandia"),
    "België": ("westers", "belgium, bel, belgië, belgien, belgia"),
    "Noorwegen": ("westers", "norway, nor, noorwegen, norwegen, norwegia"),
    "Luxemburg": ("westers", "luxembourg, lux, luxemburg"),
    "Griekenland": ("westers", "kingdom of greece, greece, greek government-in-exile, grc, griekenland, griechenland, grecja"),
    "Joegoslavië": ("westers", "kingdom of yugoslavia, yugoslavia, yug, joegoslavië, jugoslawien, jugosławia"),
    "Tsjechoslowakije": ("westers", "czechoslovakia, czechoslovak government-in-exile, csk, cze, tsjecho-slowakije, "
                                    "tschechoslowakei, czechosłowacja"),
    "Brazilië": ("westers", "brazil, vargas era, bra, brazilië, brasilien, brazylia"),
    "Filipijnen": ("westers", "philippines, commonwealth of the philippines, phl, filipijnen"),
    "Sovjet-Unie": ("sovjet", "soviet union, ussr, red army, soviet navy, soviet air forces, ukrainian ssr, byelorussian ssr, "
                              "sun, sov, urs, sovjet-unie, rode leger, sowjetunion, rote armee, zsrr, związek radziecki, "
                              "armia czerwona"),
    "Mongolië": ("sovjet", "mongolian people's republic, mongolia, mng, mongolië, mongolei, mongolia"),
    "China": ("overig", "republic of china, china, national revolutionary army, chn, republiek china, republik china, chiny, "
                        "republika chińska"),
    "Chinese communisten": ("overig", "chinese communist party, eighth route army, new fourth army"),
    "Joegoslavische partizanen": ("overig", "yugoslav partisans, democratic federal yugoslavia"),
    "Ethiopië": ("overig", "ethiopian empire, ethiopia, eth"),
    "Mexico": ("overig", "mexico, mex"),
    "Iran": ("overig", "iran, imperial state of iran, pahlavi iran, irn"),
    "Irak": ("overig", "kingdom of iraq, iraq, irq"),
    "Denemarken": ("overig", "denmark, dnk"),
    "Spanje": ("overig", "spain, francoist spain, esp"),
    "Turkije": ("overig", "turkey, tur"),
    "Egypte": ("overig", "kingdom of egypt, egypt"),
    "Viet Minh": ("overig", "viet minh, north vietnam"),
}

# Russian (also the genitive of the flag templates, {{Флаг Третьего рейха}}) and French spellings.
_MORE = {
    "Duitsland": "ナチス・ドイツ, ドイツ国, ドイツ, germania nazista, germania, terzo reich, reich tedesco, нацистская германия, германия, германский рейх, третий рейх, третьего рейха, германии, вермахт, "
                 "кригсмарине, люфтваффе, войска сс, allemagne nazie, allemagne, troisième reich, reich allemand, "
                 "wehrmacht, iiie reich",
    "Italië": "イタリア王国, イタリア, regno d'italia, italia, repubblica sociale italiana, rsi, italia fascista, королевство италия, италия, италии, итальянская социальная республика, фашистская италия, "
              "royaume d'italie, italie, république sociale italienne, italie fasciste",
    "Japan": "大日本帝国, 日本, impero giapponese, giappone, impero del giappone, японская империя, япония, японии, empire du japon, japon",
    "Hongarije": "ハンガリー王国, ハンガリー, regno d'ungheria, ungheria, королевство венгрия, венгрия, венгрии, royaume de hongrie, hongrie",
    "Roemenië": "ルーマニア王国, ルーマニア, regno di romania, romania, королевство румыния, румыния, румынии, royaume de roumanie, roumanie",
    "Bulgarije": "regno di bulgaria, bulgaria, третье болгарское царство, болгария, болгарии, royaume de bulgarie, bulgarie",
    "Finland": "フィンランド, finlandia, финляндия, финляндии, finlande",
    "Slowakije": "repubblica slovacca, slovacchia, первая словацкая республика, словакия, словакии, république slovaque, slovaquie",
    "Kroatië": "stato indipendente di croazia, ndh, croazia, независимое государство хорватия, хорватия, état indépendant de croatie, croatie",
    "Thailand": "タイ王国, タイ, таиланд, thaïlande",
    "Vichy-Frankrijk": "ヴィシー政権, ヴィシー・フランス, francia di vichy, fravichy, regime di vichy, режим виши, французское государство, régime de vichy, état français, vichy",
    "Mantsjoekwo": "満州国, manciukuò, manciukuo, маньчжоу-го, mandchoukouo",
    "Albanië": "албания, albanie",
    "Verenigd Koninkrijk": "イギリス, 大英帝国, イギリス帝国, 英国, regno unito, regno unito di gran bretagna e irlanda, impero britannico, gbr impero, великобритания, великобритании, британская империя, соединённое королевство, "
                           "royaume-uni, empire britannique, royal navy, royaume-uni de grande-bretagne et d'irlande",
    "Verenigde Staten": "アメリカ合衆国, アメリカ, stati uniti, stati uniti d'america, сша, соединённые штаты америки, соединённые штаты, сша (48 звёзд), états-unis, usa",
    "Frankrijk": "フランス, 自由フランス, フランス第三共和政, francia, francia libera, fralib, terza repubblica francese, governo provvisorio della repubblica francese, франция, франции, третья французская республика, сражающаяся франция, свободная франция, "
                 "france, france libre, troisième république, gouvernement provisoire de la république française, "
                 "république française, forces françaises libres, forces françaises de l'intérieur",
    "Canada": "カナダ, canada, канада, канады, canada",
    "Australië": "オーストラリア, australia, австралия, австралии, australie",
    "Nieuw-Zeeland": "ニュージーランド, nuova zelanda, dominion della nuova zelanda, новая зеландия, новой зеландии, nouvelle-zélande",
    "Zuid-Afrika": "unione sudafricana, sudafrica, южно-африканский союз, юас, юас (1928), afrique du sud, union d'afrique du sud",
    "Brits-Indië": "イギリス領インド帝国, 英領インド, india britannica, raj britannico, bin, британская индия, индия, raj britannique, empire des indes",
    "Polen": "ポーランド, ポーランド亡命政府, polonia, governo in esilio della polonia, seconda repubblica di polonia, польша, польши, польская республика, вторая речь посполитая, правительство польши в изгнании, "
             "армия крайова, польское подпольное государство, польши (1928—1980), pologne, "
             "deuxième république, gouvernement polonais en exil, armée polonaise de l'ouest",
    "Nederland": "オランダ, オランダ領東インド, paesi bassi, olanda, нидерланды, нидерландов, pays-bas",
    "België": "belgio, бельгия, бельгии, belgique",
    "Noorwegen": "norvegia, норвегия, норвегии, norvège",
    "Luxemburg": "люксембург, luxembourg",
    "Griekenland": "regno di grecia, grecia, governo in esilio della grecia, королевство греция, греция, греции, royaume de grèce, grèce",
    "Joegoslavië": "regno di jugoslavia, jugoslavia, королевство югославия, югославия, югославии, royaume de yougoslavie, yougoslavie",
    "Tsjechoslowakije": "cecoslovacchia, governo in esilio della cecoslovacchia, чехословакия, чехословацкое правительство в изгнании, правительство чехословакии в изгнании, "
                        "tchécoslovaquie, gouvernement provisoire tchécoslovaque",
    "Brazilië": "бразилия, brésil",
    "Filipijnen": "フィリピン・コモンウェルス, フィリピン, филиппины, commonwealth des philippines, philippines",
    "Sovjet-Unie": "ソビエト連邦, ソ連, unione sovietica, urss, armata rossa, ссср, союз советских социалистических республик, советский союз, красная армия, ркка, "
                   "украинская сср, белорусская сср, urss, union soviétique, "
                   "union des républiques socialistes soviétiques, armée rouge, urss 1923-1955",
    "Mongolië": "モンゴル人民共和国, モンゴル, repubblica popolare mongola, mongolia, монгольская народная республика, мнр, монголия, république populaire mongole, mongolie",
    "China": "中華民国, 中国, 国民革命軍, repubblica di cina, cina, kuomintang, китайская республика, китай, китая, république de chine, chine",
    "Joegoslavische partizanen": "partigiani jugoslavi, народно-освободительная армия югославии, partisans yougoslaves",
    "Ethiopië": "impero d'etiopia, etiopia, эфиопская империя, эфиопия, empire éthiopien, éthiopie",
    "Iran": "иран, iran",
    "Irak": "ирак, irak",
    "Denemarken": "дания, danemark",
    "Spanje": "франкистская испания, испания, espagne",
    "Turkije": "турция, turquie",
    "Egypte": "египет, royaume d'égypte, égypte",
    "Viet Minh": "вьетминь, демократическая республика вьетнам, việt minh, viet minh",
    "Chinese communisten": "中国共産党, 八路軍, 新四軍, partito comunista cinese",
}
_TABLE = {land: (kamp, spellings + ", " + _MORE[land] if land in _MORE else spellings)
          for land, (kamp, spellings) in _TABLE.items()}

COUNTRY_KAMP = {land: kamp for land, (kamp, _) in _TABLE.items()}
_SPELLINGS = {_normal(spelling): land for land, (_, spellings) in _TABLE.items() for spelling in spellings.split(",")}

_LINK_OR_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}|\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_FLAG_FILE = re.compile(r"flag[ _]of[ _](?:the[ _])?(.+?)\.(?:svg|png)", re.IGNORECASE)
# DEU-1935 (Polish), DEU 1933-1945 (Italian), GBR.
_COUNTRY_CODE = re.compile(r"^([A-Z]{3})(?:[- ]?\d{4}(?:-\d{4})?)?$")
_FLAG_TEMPLATE = re.compile(r"^(?:flag\w*|navy|army|air ?force|naval|ship|флаг|флагификация|drapeau|drapeau2|pays|bandiera)$",
                            re.IGNORECASE)
# A template named after its country, with a year or variant: {{Allemagne (1933)}}, {{Флаг СССР}},
# {{URSS 1923-1955}}, {{JPN-d}}.
_NAMED_FLAG = re.compile(r"^(?:флаг\s+)?(.+?)(?:\s*\d{4}\s*[-–—]\s*\d{4})?(?:-d)?$", re.IGNORECASE)


def _template_names(body):
    name, *arguments = [part.strip() for part in body.split("|")]
    positional = [a for a in arguments if "=" not in a]
    if name.lower() == "państwo":
        return positional
    if _FLAG_TEMPLATE.match(name):
        return positional[:1]
    code = _COUNTRY_CODE.match(name.removesuffix("-d"))
    if code:
        return [code.group(1)]
    named = _NAMED_FLAG.match(name)
    return [named.group(1)] if named else []


def land_of(name):
    """The Land a spelling stands for, or None. A year range or "-d" after it is left out:
    "SUN 1923-1955" and "JPN-d" are codes as well."""
    name = name.replace("_", " ")
    if land := _SPELLINGS.get(_normal(name)):
        return land
    bare = re.sub(r"(?:[- ]?\d{4}(?:\s*[-–—]\s*\d{4})?|-d)$", "", name.strip())
    return _SPELLINGS.get(_normal(bare)) if bare != name.strip() else None


def side_countries(lang, field):
    """The Landen named in a side field of an infobox, in order, each once."""
    text = COMMENT.sub("", REF.sub("", field or ""))
    found = []
    for match in _LINK_OR_TEMPLATE.finditer(text):
        template, target, label = match.groups()
        if template is not None:
            names = _template_names(template)
        else:
            flag = _FLAG_FILE.search(target)
            names = [flag.group(1)] if flag else [target, label or ""]
        for name in names:
            land = land_of(name) if name else None
            if land and land not in found:
                found.append(land)
                break
    return found
