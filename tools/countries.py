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

COUNTRY_KAMP = {land: kamp for land, (kamp, _) in _TABLE.items()}
_SPELLINGS = {_normal(spelling): land for land, (_, spellings) in _TABLE.items() for spelling in spellings.split(",")}

_LINK_OR_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}|\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
_FLAG_FILE = re.compile(r"flag[ _]of[ _](?:the[ _])?(.+?)\.(?:svg|png)", re.IGNORECASE)
_COUNTRY_CODE = re.compile(r"^([A-Z]{3})(?:-\d+)?$")
_FLAG_TEMPLATE = re.compile(r"^(?:flag\w*|navy|army|air ?force|naval|ship)$", re.IGNORECASE)


def _template_names(body):
    name, *arguments = [part.strip() for part in body.split("|")]
    positional = [a for a in arguments if "=" not in a]
    if name.lower() == "państwo":
        return positional
    if _FLAG_TEMPLATE.match(name):
        return positional[:1]
    code = _COUNTRY_CODE.match(name)
    return [code.group(1)] if code else []


def land_of(name):
    """The Land a spelling stands for, or None."""
    return _SPELLINGS.get(_normal(name.replace("_", " ")))


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
