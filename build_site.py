"""Fetch a complete inventory at build time; publish only after a successful sync."""
import argparse
import json
import shutil
from pathlib import Path
import catalog

ROOT = Path(__file__).resolve().parent

def main():
    cfg = json.loads((ROOT / 'sources.json').read_text())
    cfg['candidate_photos'] = 0  # Public gallery needs only the chosen face.
    (ROOT / 'sources.json').write_text(json.dumps(cfg, indent=2))
    snapshot = catalog.build(argparse.Namespace(offline=False, resume=False, workers=8))
    if not snapshot['products']:
        raise RuntimeError('Refusing to publish an empty inventory.')
    public = ROOT / 'public'
    public.mkdir(exist_ok=True)
    html = (ROOT / 'output' / 'Watch-Gallery.html').read_text()
    html = html.replace('<footer>', '<footer><p><a href="/refresh.html">Refresh inventory (owner)</a></p>')
    (public / 'index.html').write_text(html)
    shutil.copyfile(ROOT / 'refresh.html', public / 'refresh.html')
    print('Published gallery contains', len(snapshot['products']), 'watches.')

if __name__ == '__main__':
    main()
