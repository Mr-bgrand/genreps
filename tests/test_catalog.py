import base64, json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import catalog

def vi(x):
 b=bytearray()
 while x>127:b.append((x&127)|128);x>>=7
 b.append(x);return bytes(b)
def pb(n,v):
 if isinstance(v,int):return vi(n<<3)+vi(v)
 if isinstance(v,str):v=v.encode()
 return vi((n<<3)|2)+vi(len(v))+v

def fixture():
 folder=pb(1,1)+pb(2,'A & B')+pb(4,'https://www.dropbox.com/scl/fo/root/hash/A')+pb(9,pb(1,'stable-folder'))
 photo=pb(3,'front.jpg')+pb(6,'https://www.dropbox.com/photo')+pb(7,pb(2,'https://x.dropboxusercontent.com/thumb'))+pb(11,'file-id')+pb(17,'revision')
 token=pb(2,'root')+pb(3,1)+pb(4,pb(1,'hash'))+pb(6,pb(1,'key'))
 body=pb(1,folder)+pb(4,token)+pb(5,pb(1,photo))+pb(6,1)+pb(11,pb(1,'opaque-cursor'))
 key=base64.b64encode(b'SharedContentLinkFolderEntriesPropsPrefetch').decode()
 return 'Edison.registerStreamedPrefetch("'+key+'", "'+base64.b64encode(body).decode()+'", false)'

class CatalogTests(unittest.TestCase):
 def test_public_metadata_keeps_ids_and_pagination(self):
  x=catalog.parse_page(fixture())
  self.assertEqual(x['folder']['id'],'stable-folder')
  self.assertEqual(x['entries'][0]['name'],'front.jpg')
  self.assertEqual(x['voucher'],'opaque-cursor')
  self.assertTrue(x['has_more'])
 def test_changed_page_fails_instead_of_returning_empty_catalog(self):
  with self.assertRaises(ValueError):catalog.parse_page('<html>Sign in</html>')
 def test_override_survives_new_photos(self):
  photos=[{'id':'new','name':'cover.jpg'},{'id':'old','name':'IMG_12.jpg'}]
  self.assertEqual(catalog.choose_cover(photos,'old')[0]['id'],'old')
 def test_unknown_photos_require_review(self):
  photos=[{'id':str(i),'name':f'IMG_{i}.jpg'} for i in range(4)]
  self.assertTrue(catalog.choose_cover(photos)[2])
 def test_explicit_front_name_wins(self):
  photos=[{'id':'back','name':'IMG_1.jpg'},{'id':'face','name':'front.jpg'}]
  self.assertEqual(catalog.choose_cover(photos)[0]['id'],'face')
 def test_untrusted_title_cannot_escape_embedded_json(self):
  raw=catalog.safe_json({'title':'</script><script>alert(1)</script>'})
  self.assertNotIn('</script>',raw)
  self.assertEqual(json.loads(raw)['title'],'</script><script>alert(1)</script>')
if __name__=='__main__':unittest.main()
