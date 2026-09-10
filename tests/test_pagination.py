import json,tempfile,unittest
from pathlib import Path
from test_catalog import fixture
from dropbox_public import PublicDropbox
class FixtureDropbox(PublicDropbox):
 def __init__(self,path,pages):super().__init__(path);self.pages=iter(pages)
 def request(self,*args,**kwargs):return next(self.pages)
class PaginationTests(unittest.TestCase):
 def test_reads_second_page_and_saves_complete_cache(self):
  second={'entries':[{'is_dir':True,'filename':'Second watch','href':'https://www.dropbox.com/second','folder_id':'second-id'}], 'has_more_entries':False}
  with tempfile.TemporaryDirectory() as directory:
   client=FixtureDropbox(directory,[fixture().encode(),json.dumps(second).encode()])
   listing=client.list_folder('https://www.dropbox.com/root')
   self.assertEqual([e['id'] for e in listing['entries']],['file-id','second-id'])
   self.assertFalse(listing['has_more'])
   self.assertEqual(len(list(Path(directory).glob('*.json'))),1)
 def test_repeated_cursor_rejects_partial_catalog(self):
  page={'entries':[],'has_more_entries':True,'next_request_voucher':'opaque-cursor'}
  with tempfile.TemporaryDirectory() as directory:
   client=FixtureDropbox(directory,[fixture().encode(),json.dumps(page).encode()])
   with self.assertRaisesRegex(ValueError,'repeated'):client.list_folder('https://www.dropbox.com/root')
   self.assertEqual(list(Path(directory).glob('*.json')),[])
