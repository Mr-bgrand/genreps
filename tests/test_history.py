import json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build_site

class HistoryTests(unittest.TestCase):
 def test_legacy_gallery_is_migrated_without_losing_cover(self):
  data={'products':[{'title':'Watch','cover_id':'face','photos':[{'id':'face','preview':'data:image/jpeg;base64,YQ=='}]}]}
  html='<script id="catalog-data" type="application/json">'+json.dumps(data)+'</script>'
  error=HTTPError('https://example/catalog.json',404,'missing',{},None)
  with patch.object(build_site,'fetch',side_effect=[error,html.encode()]):
   result=build_site.load_previous()
  self.assertEqual(result['products'][0]['cover']['id'],'face')
 def test_auth_failure_cannot_reset_history(self):
  with patch.object(build_site,'fetch',side_effect=HTTPError('https://example',401,'auth',{},None)):
   with self.assertRaises(HTTPError):build_site.load_previous()
 def test_missing_saved_cover_stops_build(self):
  with patch.object(build_site,'fetch',return_value=json.dumps({'products':[{'title':'Watch','cover_id':'x','photos':[]}]}).encode()):
   with self.assertRaises(RuntimeError):build_site.load_previous()
 def test_empty_prior_inventory_stops_build(self):
  with patch.object(build_site,'fetch',return_value=b'{"products":[]}'):
   with self.assertRaises(RuntimeError):build_site.load_previous()
