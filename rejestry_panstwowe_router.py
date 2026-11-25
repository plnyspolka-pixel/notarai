"""Wyłącznie indywidualne sesje kancelarii. Brak dostępu serwisowego i demo."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
import httpx
import autoryzacja
import stanowiska
import rejestry_panstwowe as rp

router=APIRouter(prefix="/api/rejestry-panstwowe",tags=["rejestry państwowe"])

def _uprawniony(request):
    if not autoryzacja.MULTI or getattr(request.state,"komputer",None) or getattr(request.state,"serwis",False):
        raise HTTPException(403,"Wymagana indywidualna sesja członka kancelarii.")
    k=getattr(request.state,"kancelaria",None)
    e=getattr(request.state,"email",None)
    if not k or not e:
        raise HTTPException(401,"Zaloguj się.")
    osoba=autoryzacja._osoba_w_kancelarii(k,e)
    if not osoba or "rejestry" not in stanowiska.uprawnienia(osoba):
        raise HTTPException(403,"Brak uprawnień do rejestrów.")

@router.get("/katalog")
def katalog(request:Request):
    _uprawniony(request)
    return {"rejestry":rp.katalog()}

class Zapytanie(BaseModel):
    identyfikator:str=Field(min_length=1,max_length=64)
    data:str=Field(default="",max_length=10)
    rejestr:str=Field(default="P",max_length=1)
    potwierdzam:bool=False

@router.post("/publiczne/{usluga}")
def publiczne(usluga:str,dane:Zapytanie,request:Request):
    _uprawniony(request)
    if not dane.potwierdzam:
        raise HTTPException(400,"Potwierdź pojedyncze zapytanie do rejestru.")
    if usluga not in ("uldk","krs","vat"):
        raise HTTPException(404,"Brak takiego publicznego adaptera.")
    try:
        with httpx.Client(trust_env=False) as c:
            if usluga=="uldk":
                return rp.dzialka(dane.identyfikator,c)
            if usluga=="krs":
                return rp.krs(dane.identyfikator,c,dane.rejestr)
            return rp.vat(dane.identyfikator,dane.data,c)
    except ValueError as e:
        raise HTTPException(400,str(e)) from None
    except rp.Niedostepny as e:
        raise HTTPException(502,str(e)) from None
