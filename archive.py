"""Identity matching and single-photo sold archive reconciliation."""
import copy
import re

def stock_number(title):
    matches = re.findall(r'\b(?:G\d{4,}|\d[A-Z0-9]{5,}|\d+\.\d+\.\d+)\b', title.upper())
    return next((m for m in reversed(matches) if not m.isdigit()), '')

def identity(p):
    sku=stock_number(p['title'])
    return 'sku:'+sku if sku else 'folder:'+p.get('folder_id',p['id'])

def classify(title):
    t=title.upper()
    brands=[(r'\bOMEGA\b','Omega'),(r'\bBREITLING\b','Breitling'),(r'\b(CARTIER|SANTOS|BAIGNOIRE)\b','Cartier'),(r'\b(AP|AUDEMARS)\b','Audemars Piguet'),(r'\b(PP|PATEK)\b','Patek Philippe'),(r'\b(PAM|PANERAI)\b','Panerai'),(r'\bTUDOR\b','Tudor'),(r'\bIWC\b','IWC'),(r'\bTAG\b','TAG Heuer')]
    brand=next((b for pattern,b in brands if re.search(pattern,t)),None)
    if not brand and re.search(r'\b(ROLEX|DAYTONA|DATEJUST|SUB|SUBMARINER|EXPLORER|OP|YM|SD43|GMT|BATGIRL|BATIGIRL|BATMAN|PEPSI|ROOTBEER|SPRITE|COKE|BW)\b',t): brand='Rolex'
    models={
      'Rolex':[(r'DAYTONA','Daytona'),(r'DATEJUST','Datejust'),(r'\bSUB','Submariner'),(r'EXPLORER','Explorer'),(r'\bOP\b','Oyster Perpetual'),(r'\bYM\b','Yacht-Master'),(r'\bSD43\b','Sea-Dweller'),(r'GMT|BATGIRL|BATIGIRL|BATMAN|PEPSI|ROOTBEER|SPRITE|COKE|\bBW\b','GMT-Master II')],
      'Omega':[(r'NTTD|SMP|SEAMASTER|SPECTRE','Seamaster'),(r'\bAT\b|AQUA TERRA','Aqua Terra'),(r'SPEEDMASTER','Speedmaster')],
      'Cartier':[(r'SANTOS','Santos'),(r'BAIGNOIRE','Baignoire'),(r'TANK','Tank')],
      'Breitling':[(r'CHRONOM','Chronomat'),(r'NAVITIMER','Navitimer')],
      'Audemars Piguet':[(r'OFFSHORE|26420','Royal Oak Offshore'),(r'ROYAL OAK|15510|15500','Royal Oak')],
      'Patek Philippe':[(r'5167|5168|AQUANAUT','Aquanaut'),(r'5711|NAUTILUS','Nautilus')],
      'Tudor':[(r'CHRONO','Black Bay Chrono'),(r'BB54|BB 54|BLACK BAY 54','Black Bay 54')],
      'IWC':[(r'INGEN','Ingenieur')], 'TAG Heuer':[(r'AQUARACER','Aquaracer')]
    }
    if brand=='Panerai':
        m=re.search(r'PAM\s*(\d+)',t)
        return brand,'PAM '+m[1] if m else 'Other models'
    return brand or 'Other brands',next((m for pattern,m in models.get(brand,[]) if re.search(pattern,t)),'Other models')

def reconcile(previous,current,now,present_folders=()):
    previous_by_id={identity(p):p for p in previous}
    active={identity(p):copy.deepcopy(p) for p in current}
    for key,p in active.items():
        p['first_seen_at']=previous_by_id[key].get('first_seen_at') if key in previous_by_id else now
    if len(active)!=len(current): raise ValueError('Duplicate stock number; resolve before publishing.')
    present={identity({'id':f['folder_id'],'folder_id':f['folder_id'],'title':f['name']}):f for f in present_folders if f.get('folder_id')}
    for p in previous:
        key=identity(p)
        if key in active: continue
        old=copy.deepcopy(p)
        if key in present:
            old['status']=present[key]['status']; old['photos']=[];old['photo_count']=1
            old['photo_note']='Folder is present; retaining its last available cover.'
        else:
            old['status']='sold';old['archived_at']=old.get('archived_at',now)
            old['photos']=[];old['photo_count']=1;old.pop('photo_note',None)
        # Never retain original legacy photo metadata or additional archive images.
        old['cover']={k:old['cover'][k] for k in ('id','name','preview') if k in old['cover']}
        active[key]=old
    result=[]
    for key,p in active.items():
        p['identity']=key;p['stock_number']=stock_number(p['title']);p['brand'],p['model']=classify(p['title'])
        if p['status']!='sold': p.pop('archived_at',None)
        result.append(p)
    return sorted(result,key=lambda p:(p['status']=='sold',p['brand'],p['model'],p['title']))
