from tools.liberation_articles import read_article
from tools.liberation_rules.el import RULE as EL


def test_greek_genitive_months_give_occupation_and_liberation():
    text = ("Το χωριό καταλήφθηκε από τους Γερμανούς στις 27 Απριλίου 1941. "
            "Η πόλη απελευθερώθηκε στις 12 Οκτωβρίου 1944.")
    assert read_article(EL, text) == ("1941-04-27", "1944-10-12")


def test_the_liberation_of_the_balkan_wars_is_not_counted():
    text = "Η πόλη απελευθερώθηκε στις 26 Οκτωβρίου 1912. Το 1944 κάηκε από τους Γερμανούς."
    assert read_article(EL, text) == (None, None)


def test_a_town_north_of_the_greek_border_is_left_out():
    from tools.liberation_rules.el import adjust
    from tools.liberations import Bevrijding

    def at(lat, lng):
        return Bevrijding(place="X", title="X", lang="el", country="Griekenland", liberated="1944-10-26",
                          lat=lat, lng=lng, source="el-articles")
    assert adjust(at(40.27, 22.51)) is not None   # Katerini
    assert adjust(at(41.10, 23.55)) is not None   # Serres
    assert adjust(at(41.35, 21.55)) is None       # Prilep
    assert adjust(at(41.33, 19.82)) is None       # Tirana
    assert adjust(at(41.65, 25.37)) is None       # Kardzhali
