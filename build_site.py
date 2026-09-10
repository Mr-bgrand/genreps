"""Build active photo galleries and retain the previous deployment's sold archive."""
import argparse,base64,io,json,re,shutil,urllib.error,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
import archive,catalog
ROOT=Path(__file__).resolve().parent
PRODUCTION='https://watch-collection-mrbgrands-projects.vercel.app'

def fetch(url):
    request=urllib.request.Request(url,headers={'Cache-Control':'no-cache','User-Agent':'GenREPS-Build/1.1'})
    with urllib.request.urlopen(request,timeout=60) as response:
        if response.url.split('/')[2]!=url.split('/')[2]: raise RuntimeError('Previous catalog redirected; check deployment access.')
        data=response.read(64*1024*1024+1)
    if len(data)>64*1024*1024: raise RuntimeError('Archive exceeds 64 MiB; migrate archive storage.')
    return data

def load_previous(path=None):
    if path: data=json.loads(Path(path).read_text())
    else:
        try: data=json.loads(fetch(PRODUCTION+'/catalog.json'))
        except urllib.error.HTTPError as error:
            if error.code!=404: raise
            html=fetch(PRODUCTION+'/').decode()
            match=re.search(r'<script id="catalog-data" type="application/json">(.*?)</script>',html,re.S)
            if not match: raise RuntimeError('Cannot migrate previous gallery. Refusing to reset archive.')
            data=json.loads(match[1])
    if not isinstance(data.get('products'),list) or not data['products']: raise RuntimeError('Invalid previous inventory. Refusing to reset archive.')
    for p in data['products']:
        if not p.get('cover'): p['cover']=next((x for x in p['photos'] if x['id']==p['cover_id']),None)
        if not p['cover'] or not p['cover'].get('preview','').startswith('data:image/jpeg;base64,'): raise RuntimeError('Previous cover is not self-contained: '+p['title'])
    return data

def cover_data(path):
    with Image.open(path) as im:
        im.thumbnail((576,1024));buf=io.BytesIO();im.convert('RGB').save(buf,'JPEG',quality=82,optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--offline',action='store_true');parser.add_argument('--previous',type=Path)
    args=parser.parse_args();previous=load_previous(args.previous)
    snapshot=catalog.build(argparse.Namespace(offline=args.offline,resume=False,workers=8,all_photos=True,skip_render=True))
    if not snapshot['products']: raise RuntimeError('Refusing empty import; previous site remains available.')
    public=ROOT/'public'
    if public.exists(): shutil.rmtree(public)
    (public/'images').mkdir(parents=True)
    current=[]
    for source in snapshot['products']:
        p={k:source[k] for k in ('id','folder_id','title','status','folder_url','photo_count','cover_id','needs_review')}
        p['cover']={'id':source['cover_id'],'name':'Cover','preview':cover_data(ROOT/'output'/source['cover_image'])}
        p['photos']=[]
        for photo in source['photos']:
            if photo['id']==source['cover_id']: continue
            relative=photo['local_image'];shutil.copyfile(ROOT/'output'/relative,public/relative)
            p['photos'].append({'id':photo['id'],'name':photo['name'],'preview':'/'+relative})
        current.append(p)
    now=datetime.now(timezone.utc).isoformat()
    products=archive.reconcile(previous['products'],current,now,snapshot['skipped'])
    data={'version':2,'updated_at':now,'products':products,'sources':snapshot['sources']}
    (public/'catalog.json').write_text(catalog.safe_json(data))
    for name in ('index.html','gallery.js','gallery.css','refresh.html'): shutil.copyfile(ROOT/name,public/name)
    archived=sum(p['status']=='sold' for p in products)
    print(f'Published {len(products)-archived} active watches and {archived} archived watches; one cover per archive entry.')
if __name__=='__main__': main()
