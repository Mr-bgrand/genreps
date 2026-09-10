#!/usr/bin/env python3
"""Build a local, browsable watch inventory from public Dropbox links."""
import argparse
import base64
import csv
import hashlib
import io
import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageOps
from dropbox_public import PublicDropbox, parse_page, uid

ROOT = Path(__file__).resolve().parent
IMAGE_EXTENSIONS = {'.jpg','.jpeg','.png','.webp','.heic','.heif'}


def safe_json(value):
    return json.dumps(value,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')


def choose_cover(photos, override=None):
    if not photos: raise ValueError('No usable photos')
    for photo in photos:
        if photo['id'] == override: return photo, 'Reviewed cover', False
    for photo in photos:
        if re.search(r'(^|[ _-])(cover|front|face|dial)([ _.-]|$)', photo['name'], re.I):
            return photo, 'Named face photo', False
    # These supplied photo sets typically use bag, full watch, then dial close-up.
    # This is a candidate convention, not semantic image recognition.
    return photos[min(2,len(photos)-1)], 'Suggested cover · check face view', True


def load_json(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback


def thumbnail(client, photo, destination):
    if destination.exists(): return
    if client.offline: raise ValueError('Offline photo missing: '+photo['name'])
    url = photo.get('thumbnail')
    if not url:
        parts = urllib.parse.urlsplit(photo['url']); query = dict(urllib.parse.parse_qsl(parts.query)); query['dl']='1'
        url = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))
    raw = client.request(url)
    with Image.open(io.BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img).convert('RGB'); img.thumbnail((1000,1200))
        target = destination.with_suffix('.tmp')
        img.save(target, 'JPEG', quality=88, optimize=True); target.replace(destination)


def process_folder(source, folder, cfg, offline, override, depth=0):
    client = PublicDropbox(ROOT/'cache'/'folders',offline,cfg.get('_resume',False))
    page = client.list_folder(folder['url']); folder = page['folder']
    if depth > 6: raise ValueError('Folder nesting exceeds supported depth')
    photos = [e for e in page['entries'] if not e['is_dir'] and Path(e['name']).suffix.lower() in IMAGE_EXTENSIONS]
    children = [e for e in page['entries'] if e['is_dir']]
    products = []; skipped = []
    if photos:
        product_id = 'watch_'+uid(folder['id'])
        picked, method, review = choose_cover(photos, override.get(product_id))
        from select_covers import fingerprint
        ai = cfg.get('_ai_choices',{}).get(product_id,{})
        if review and ai.get('fingerprint') == fingerprint(photos):
            match = next((p for p in photos if p['id']==ai.get('photo_id')),None)
            if match:
                picked=match;method='AI-selected face' if ai.get('is_face') else 'AI could not confirm a face view'
                review=bool(ai.get('needs_review',True))
        # Keep the complete metadata list; download a small review set plus the selected cover.
        candidates = photos[:cfg.get('candidate_photos',6)]
        if picked not in candidates: candidates.append(picked)
        images_dir = ROOT/'output'/'images'; images_dir.mkdir(parents=True,exist_ok=True)
        with ThreadPoolExecutor(max_workers=2) as downloads:
            tasks = []
            for photo in candidates:
                filename = uid(photo['id']+':'+photo.get('revision',''))+'.jpg'
                photo['local_image']='images/'+filename
                reader = PublicDropbox(ROOT/'cache'/'folders',offline)
                tasks.append(downloads.submit(thumbnail,reader,photo,images_dir/filename))
            for task in tasks: task.result()
        products.append({'id':product_id,'folder_id':folder['id'],'title':folder['name'],
                         'status':source['status'],'source':source['name'],'source_url':source['url'],
                         'folder_url':folder['url'],'photo_count':len(photos),'photos':photos,
                         'cover_id':picked['id'],'cover_image':picked['local_image'],
                         'cover_method':method,'needs_review':review,'price':None,'currency':None})
    if not photos and not children: skipped.append({'source':source['name'],'name':folder['name'],'reason':'No supported images or subfolders'})
    for child in children:
        if child['name'].casefold() in {s.casefold() for s in cfg.get('exclude_folders',[])}:
            skipped.append({'source':source['name'],'name':child['name'],'reason':'Excluded non-watch section'}); continue
        p,s = process_folder(source,child,cfg,offline,override,depth+1);products.extend(p);skipped.extend(s)
    return products,skipped


def build(args):
    cfg = load_json(ROOT/'sources.json',{}); cfg['_resume']=args.resume; cfg['_ai_choices']=load_json(ROOT/'ai-covers.json',{}); override = load_json(ROOT/'covers.json',{})
    out = ROOT/'output';out.mkdir(exist_ok=True)
    previous = load_json(out/'catalog.json',{'products':[]})
    all_products = [];skipped = [];errors = [];source_summary = [];jobs = []
    for source in cfg['sources']:
        try:
            page = PublicDropbox(ROOT/'cache'/'folders',args.offline,args.resume).list_folder(source['url'])
            folders = [e for e in page['entries'] if e['is_dir']]
            source_summary.append({'name':source['name'],'status':source['status'],'folder_title':page['folder']['name'],
                                   'url':source['url'],'top_level_folders':len(folders)})
            print(source['name']+': '+str(len(folders))+' folders',flush=True)
            for folder in folders:
                if folder['name'].casefold() in {s.casefold() for s in cfg.get('exclude_folders',[])}:
                    skipped.append({'source':source['name'],'name':folder['name'],'reason':'Excluded non-watch section'})
                else: jobs.append((source,folder))
        except Exception as e: errors.append({'source':source['name'],'error':str(e)})
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_folder,s,f,cfg,args.offline,override):(s,f) for s,f in jobs}
        for future in as_completed(futures):
            source,folder = futures[future]
            try:
                p,s = future.result();all_products.extend(p);skipped.extend(s)
                print('Read: '+folder['name']+' ('+str(len(p))+' listings)',flush=True)
            except Exception as e:
                errors.append({'source':source['name'],'folder':folder['name'],'error':str(e)})
                print('FAILED: '+folder['name']+': '+str(e),file=sys.stderr,flush=True)
    if errors:
        (out/'last_errors.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
        raise RuntimeError('Import incomplete. Previous catalog preserved. See output/last_errors.json.')
    seen = {}
    for p in all_products:
        if p['id'] in seen:
            if seen[p['id']]['status'] != p['status']: raise RuntimeError('Same folder appears in both statuses: '+p['title'])
        seen[p['id']] = p
    products = sorted(seen.values(),key=lambda p:(p['status']!='in_stock',p['title'].casefold()))
    old = {p['id']:p for p in previous['products']}; new = {p['id']:p for p in products}
    changes = {'added':[p['title'] for k,p in new.items() if k not in old],
               'missing':[p['title'] for k,p in old.items() if k not in new],
               'updated':[p['title'] for k,p in new.items() if k in old and any(p.get(f)!=old[k].get(f) for f in ('title','status','cover_id','cover_image','photo_count'))]}
    now=datetime.now(timezone.utc).isoformat()
    snapshot = {'version':1,'updated_at':previous.get('updated_at',now) if args.offline else now,'generated_at':now,'sources':source_summary,
                'products':products,'skipped':skipped,'changes':changes}
    temp = out/'catalog.json.tmp';temp.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(out/'catalog.json')
    with (out/'inventory.csv').open('w',newline='',encoding='utf-8-sig') as f:
        columns = ['id','title','status','price','currency','photo_count','cover_image','folder_url','needs_review']
        writer = csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for p in products:
            row = dict(p)
            for k,v in row.items():
                if isinstance(v,str) and v.startswith(('=','+','-','@')):row[k]="'"+v
            writer.writerow(row)
    render(snapshot,out)
    (out/'changes.json').write_text(json.dumps(changes,indent=2),encoding='utf-8')
    print('DONE: '+str(len(products))+' listings; '+str(sum(p['needs_review'] for p in products))+' covers need review.',flush=True)
    return snapshot


def render(snapshot, out):
    template = (ROOT/'template.html').read_text(encoding='utf-8')
    # Fully embedded cover preview is portable and works without a server or Dropbox connection.
    embedded = json.loads(json.dumps(snapshot))
    for p in embedded['products']:
        for photo in p['photos']:
            if photo.get('local_image'):
                with Image.open(out/photo['local_image']) as im:
                    im.thumbnail((400,600)); buf=io.BytesIO();im.save(buf,'JPEG',quality=76,optimize=True)
                photo['preview']='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
            photo.pop('thumbnail',None)
    html = template.replace('__CATALOG_DATA__',safe_json(embedded)).replace('__DEFAULT_OVERRIDES__',safe_json(load_json(ROOT/'covers.json',{})))
    (out/'Watch-Catalog.html').write_text(html,encoding='utf-8')
    gallery = json.loads(json.dumps(embedded));gallery['gallery_only']=True
    for p in gallery['products']:
        p['photos']=[photo for photo in p['photos'] if photo['id']==p['cover_id']]
    gallery_html=template.replace('__CATALOG_DATA__',safe_json(gallery)).replace('__DEFAULT_OVERRIDES__','{}')
    (out/'Watch-Gallery.html').write_text(gallery_html,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ai',action='store_true',help='Send unreviewed candidate images to OpenAI for paid face-photo selection')
    parser.add_argument('--vision-model',default='gpt-4.1-mini')
    parser.add_argument('--ai-limit',type=int,default=25,help='Maximum new AI selections per run')
    parser.add_argument('--resume',action='store_true',help='Resume an interrupted import using complete folder listings cached within the past hour')
    parser.add_argument('--offline',action='store_true',help='Rebuild using already downloaded metadata and images')
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--apply-covers',type=Path,help='Merge downloaded cover choices into covers.json before building')
    args=parser.parse_args()
    if args.apply_covers:
        choices=json.loads(args.apply_covers.read_text(encoding='utf-8'))
        if not isinstance(choices,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in choices.items()):
            parser.error('Cover choices must be an object mapping product IDs to image IDs')
        current=load_json(ROOT/'covers.json',{});current.update(choices)
        (ROOT/'covers.json').write_text(json.dumps(current,indent=2),encoding='utf-8')
    if args.ai and not os.environ.get('OPENAI_API_KEY'):parser.error('Optional --ai requires OPENAI_API_KEY in your environment')
    if args.ai_limit<1:parser.error('--ai-limit must be positive')
    try:
        build(args)
        if args.ai:
            from select_covers import select_missing
            select_missing(ROOT,args.vision_model,args.ai_limit)
            args.offline=True;build(args)
    except Exception as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
