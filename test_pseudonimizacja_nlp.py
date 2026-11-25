"""Testy adapterów i odbiór rzeczywistych modeli w osobnym profilu CI."""
import os
import pytest
import pseudonimizacja_nlp as nlp
from pseudonimizacja_aktu import Osoba, WymagaWeryfikacji


def test_ner_offsets_and_stride():
    tekst = "Dane: " + "opis " * 200 + "Ewa Nowak"
    a = tekst.index("Ewa")
    def pipe(t, **kw):
        assert t == tekst and kw["stride"] == 32
        return [{"start": a, "end": a+9, "entity_group": "PERSON", "score": .12}]
    wynik = nlp.propozycje_ner(tekst, detektor=pipe)
    assert [(w.poczatek, w.koniec, w.typ) for w in wynik] == [(a, a+9, "OSOBA")]


def test_ner_malformed_response_blocks():
    with pytest.raises(WymagaWeryfikacji, match="LOCAL_NER_FAILED"):
        nlp.propozycje_ner("abc", detektor=lambda *a, **kw: [
            {"start": 0, "end": 999, "entity_group": "PERSON"}])


def test_fleksja_nie_scala_homonimow():
    class Silnik:
        def analyse(self, slowo):
            return []
        def generate(self, slowo):
            formy = {"Jan": "Janowi", "Kowalski": "Kowalskiemu"}
            return [(formy.get(slowo, slowo), slowo, "subst:sg:dat:m1")]
    osoby = (Osoba("a", ("Jan", "Adam"), "Kowalski"),
             Osoba("b", ("Jan",), "Kowalski"))
    tekst = "Janowi Kowalskiemu"
    wynik = nlp.propozycje_fleksji(tekst, osoby, silnik=Silnik())
    assert any(w["kandydaci"] == ["a", "b"] and w["wymaga_potwierdzenia"]
               for w in wynik)


@pytest.mark.skipif(os.getenv("NOTARAI_REAL_PII_TESTS") != "1",
                    reason="requires separately provisioned model and CPU dependencies")
def test_rzeczywisty_model_i_morfeusz():
    tekst = "Jan Kowalski z firmy PKO BP mieszka w Warszawie."
    w = nlp.propozycje_ner(tekst)
    assert any(tekst[z.poczatek:z.koniec] == "Jan Kowalski" and z.typ == "OSOBA" for z in w)
    tekst = "Janowi Kowalskiemu doręczono dokument."
    w = nlp.propozycje_fleksji(tekst, (Osoba("a", ("Jan",), "Kowalski"),))
    assert any(tekst[z["poczatek"]:z["koniec"]] == "Janowi Kowalskiemu" for z in w)
