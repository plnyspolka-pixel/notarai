"""Kontrola rejestru zgód. Nie weryfikuje tożsamości osób ani treści opinii."""
import sys, json, hashlib
from pathlib import Path
from datetime import date

def validate(path):
    path=Path(path).resolve()
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    errors=[]
    episodes=data.get('episodes',[])
    if {e.get('id') for e in episodes}!={f'E{i:02}' for i in range(1,9)} or len(episodes)!=8:
        errors.append('Rejestr musi zawierać dokładnie E01–E08.')
    for ep in episodes:
        eid=ep.get('id','?')
        def fail(message): errors.append(f'{eid}: {message}')
        if not ep.get('product_build'): fail('brak wersji produktu')
        if ep.get('variant') not in ('BAZOWY','PLANOWANY'): fail('brak zatwierdzonego wariantu')
        required=set(data.get('required_checks',[]))
        if len(required)!=72: fail('niepełny wykaz wymaganych kontroli')
        checks=ep.get('checks',{})
        for code in sorted(required):
            item=checks.get(code,{})
            if item.get('status')=='PASS' and item.get('reviewer') and item.get('evidence'):
                target=(path.parent/item['evidence']).resolve()
                if not target.is_file(): fail('brak dowodu kontroli: '+code)
            elif item.get('status')=='NA' and item.get('reviewer') and item.get('reason'):
                pass
            else: fail('kontrola niezamknięta: '+code)
        if not ep.get('evidence'): fail('brak dowodów testów i kontroli')
        for rel in ep.get('evidence',[]):
            target=(path.parent/rel).resolve()
            if not target.is_file(): fail('brak pliku dowodu: '+str(rel))
        for kind in ('video','mail','landing'):
            asset=ep.get('assets',{}).get(kind,{})
            if not asset.get('path') or not asset.get('sha256'): fail('brak finalnego materiału i hash: '+kind);continue
            target=(path.parent/asset['path']).resolve()
            if not target.is_file(): fail('brak pliku: '+kind);continue
            if hashlib.sha256(target.read_bytes()).hexdigest()!=asset['sha256']: fail('zmieniony plik: '+kind)
        for role in ('product','notary','legal','production'):
            ap=ep.get('approvals',{}).get(role,{})
            if ap.get('status')!='PASS' or not ap.get('name') or ap.get('conditions','').strip(): fail('brak bezwarunkowej zgody: '+role)
            try:
                signed=date.fromisoformat(ap.get('signed_at','')[:10]);valid=date.fromisoformat(ap.get('valid_until','')[:10])
                if signed>date.today() or valid<date.today() or valid<signed: fail('zgoda nieważna czasowo: '+role)
            except (ValueError,TypeError): fail('brak prawidłowych dat zgody: '+role)
    return errors

if __name__=='__main__':
    path=sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).with_name('REJESTR_AUTORYZACJI_V4.json'))
    try: errors=validate(path)
    except Exception as exc: print('BLOCK: nie można sprawdzić rejestru:',str(exc));sys.exit(2)
    if errors:
        print('BLOCK — publikacja zablokowana')
        print('\n'.join(errors));sys.exit(2)
    print('PASS — rejestr kompletny; tożsamości i treść zgód wymagają kontroli osoby publikującej.')
