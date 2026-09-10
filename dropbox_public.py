"""Anonymous adapter for Dropbox's public shared-folder web pages.
Uses public page metadata, not the authenticated Dropbox API. Page schema can change.
"""
import base64
import hashlib
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def wire_fields(data):
    def varint(pos):
        value = shift = 0
        while pos < len(data) and shift < 70:
            byte = data[pos]; pos += 1
            value |= (byte & 127) << shift
            if byte < 128: return value, pos
            shift += 7
        raise ValueError('Invalid protobuf varint')
    out = []; pos = 0
    while pos < len(data):
        key, pos = varint(pos); number, kind = key >> 3, key & 7
        if not number: raise ValueError('Invalid field number')
        if kind == 0: value, pos = varint(pos)
        elif kind in (1, 2, 5):
            if kind == 2: length, pos = varint(pos)
            else: length = 8 if kind == 1 else 4
            if length > len(data) - pos: raise ValueError('Truncated protobuf')
            value = data[pos:pos + length]; pos += length
        else: raise ValueError('Unsupported protobuf wire type')
        out.append((number, value))
    return out


def unpack(data): return dict(wire_fields(data))
def txt(value): return value.decode('utf-8') if isinstance(value, bytes) else str(value)
def wrapped(data): return txt(unpack(data).get(1, b'')) if data else ''
def uid(value): return hashlib.sha256(value.encode()).hexdigest()[:24]


def parse_page(html):
    for key, payload in re.findall(r'registerStreamedPrefetch\("([A-Za-z0-9+/=]*)",\s*"([A-Za-z0-9+/=]*)"', html):
        if b'SharedContentLinkFolderEntriesPropsPrefetch' not in base64.b64decode(key): continue
        fields = wire_fields(base64.b64decode(payload)); top = dict(fields)
        def folder(raw):
            d = unpack(raw)
            return {'is_dir': True, 'name': txt(d[2]), 'url': txt(d[4]),
                    'id': wrapped(d.get(9)) or uid(txt(d[4]))}
        entries = []
        for number, raw in fields:
            if number != 5: continue
            item = unpack(raw)
            if 2 in item: entries.append(folder(item[2])); continue
            if 1 not in item: raise ValueError('Unknown Dropbox entry type')
            d = unpack(item[1]); preview = unpack(d.get(7, b''))
            entries.append({'is_dir': False, 'name': txt(d[3]), 'url': txt(d[6]),
                            'id': txt(d.get(11, b'')) or uid(txt(d[6])),
                            'revision': txt(d.get(17, b'')),
                            'thumbnail': txt(preview.get(2, b'')), 'bytes': d.get(2, 0)})
        token = unpack(top[4])
        if token.get(3) != 1: raise ValueError('Unsupported Dropbox share type')
        return {'folder': folder(top[1]), 'entries': entries, 'has_more': bool(top.get(6, 0)),
                'voucher': wrapped(top.get(11)), 'token': {
                    'link_key': txt(token[2]), 'link_type': 'c',
                    'secure_hash': wrapped(token.get(4)), 'sub_path': wrapped(token.get(5)),
                    'rlkey': wrapped(token.get(6))}}
    raise ValueError('No public folder metadata found. Link may be unavailable or Dropbox changed its page format.')


def walk_strings(value):
    if isinstance(value, str): yield value
    elif isinstance(value, dict):
        for v in value.values(): yield from walk_strings(v)
    elif isinstance(value, list):
        for v in value: yield from walk_strings(v)


def parse_json_entry(d):
    result = {'is_dir': bool(d['is_dir']), 'name': d['filename'], 'url': d['href'],
              'id': d.get('folder_id') or d.get('file_id') or uid(d['href'])}
    if not result['is_dir']:
        thumbs = [s for s in walk_strings(d.get('preview', {})) if s.startswith('https://') and '/p/thumb/' in s]
        result.update(revision=str(d.get('revision_id') or d.get('sjid') or ''),
                      thumbnail=thumbs[0] if thumbs else '', bytes=d.get('bytes', 0))
    return result


class PublicDropbox:
    def __init__(self, cache, offline=False, resume=False):
        self.cache = Path(cache); self.cache.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.resume = resume
        self.jar = http.cookiejar.CookieJar()
        self.http = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def request(self, url, data=None, headers=None, limit=30_000_000):
        host = urllib.parse.urlparse(url).hostname or ''
        if not (host == 'dropbox.com' or host.endswith('.dropbox.com') or host.endswith('.dropboxusercontent.com')):
            raise ValueError('Unexpected Dropbox URL host')
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, data=data, headers={'User-Agent':'Mozilla/5.0 WatchCatalog/1.0', **(headers or {})})
                with self.http.open(request, timeout=45) as response:
                    body = response.read(limit + 1)
                    if len(body) > limit: raise ValueError('Dropbox response exceeds size limit')
                    return body
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == 2: raise
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2: raise
            time.sleep(1 + attempt * 2)
    def list_folder(self, url):
        cache_file = self.cache / (uid(url) + '.json')
        if self.offline or (self.resume and cache_file.exists() and time.time()-cache_file.stat().st_mtime < 3600):
            if not cache_file.exists(): raise ValueError('Offline folder metadata is missing')
            return json.loads(cache_file.read_text())
        page = parse_page(self.request(url).decode('utf-8'))
        seen = set(); count = 0
        while page['has_more']:
            voucher = page['voucher']
            if not voucher or voucher in seen: raise ValueError('Missing or repeated pagination cursor; refusing partial listing')
            seen.add(voucher); count += 1
            if count > 200: raise ValueError('Pagination limit reached; refusing partial listing')
            csrf = next((c.value for c in self.jar if c.name == 't'), '')
            data = urllib.parse.urlencode({**page['token'], 'voucher': voucher, 't': csrf}).encode()
            response = json.loads(self.request('https://www.dropbox.com/list_shared_link_folder_entries', data,
                                  {'Referer':url, 'X-Requested-With':'XMLHttpRequest'}))
            if 'entries' not in response or 'has_more_entries' not in response:
                raise ValueError('Unexpected Dropbox pagination response')
            page['entries'].extend(parse_json_entry(e) for e in response['entries'])
            page['has_more'] = response['has_more_entries']; page['voucher'] = response.get('next_request_voucher')
        # Never publish a partial page as a complete cache entry.
        unique = {}; [unique.setdefault(e['id'], e) for e in page['entries']]
        page['entries'] = list(unique.values())
        cache_file.write_text(json.dumps(page, ensure_ascii=False), encoding='utf-8')
        return page
