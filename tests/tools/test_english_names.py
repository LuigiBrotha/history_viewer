import bz2
import gzip

from tools.english_names import english_titles


def files(tmp_path):
    index = tmp_path / "ruwiki-index.txt.bz2"
    index.write_bytes(bz2.compress("\n".join([
        "100:1:Жуков, Георгий Константинович",
        "100:2:Жуков",
        "200:3:Сталинградская битва",
        "200:4:Без английской статьи",
    ]).encode("utf-8") + b"\n"))
    redirect = tmp_path / "ruwiki-redirect.sql.gz"
    redirect.write_bytes(gzip.compress(
        "INSERT INTO `redirect` VALUES (2,0,'Жуков,_Георгий_Константинович','',''),(9,0,'X','','');\n".encode()))
    langlinks = tmp_path / "ruwiki-langlinks.sql.gz"
    langlinks.write_bytes(gzip.compress(
        "INSERT INTO `langlinks` VALUES (1,'en','Georgy Zhukov'),(1,'de','Georgi Konstantinowitsch Schukow'),"
        "(3,'en','Battle of Stalingrad');\n".encode()))
    return index, redirect, langlinks


def test_titles_and_redirects_lead_to_the_english_article(tmp_path):
    found = english_titles(*files(tmp_path), ["Жуков, Георгий Константинович", "Жуков", "Сталинградская битва",
                                                "Без английской статьи", "Нет такой страницы"])
    assert found == {
        "Жуков, Георгий Константинович": "Georgy Zhukov",
        "Жуков": "Georgy Zhukov",
        "Сталинградская битва": "Battle of Stalingrad",
    }


def test_a_link_with_underscores_or_a_small_first_letter_still_matches(tmp_path):
    found = english_titles(*files(tmp_path), ["сталинградская_битва"])
    assert found == {"сталинградская_битва": "Battle of Stalingrad"}
