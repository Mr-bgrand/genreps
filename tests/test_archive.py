import copy,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import archive

def watch(title='Daytona VSF G12345',folder='folder1',status='in_stock'):
 return {'id':folder,'folder_id':folder,'title':title,'status':status,'cover':{'id':'face','name':'cover','preview':'data:image/jpeg;base64,YQ=='},'photos':[{'id':'back','preview':'/images/abc.jpg'}],'photo_count':2}

class ArchiveTests(unittest.TestCase):
 def test_missing_watch_keeps_only_cover(self):
  old=watch();result=archive.reconcile([old],[],'today')[0]
  self.assertEqual(result['status'],'sold');self.assertEqual(result['photos'],[]);self.assertEqual(result['photo_count'],1)
  self.assertEqual(result['cover'],old['cover']);self.assertEqual(old['status'],'in_stock')
 def test_move_between_sources_and_folder_ids_matches_stock(self):
  old=watch(status='inbound');new=watch(folder='moved')
  result=archive.reconcile([old],[new],'today')
  self.assertEqual(len(result),1);self.assertEqual(result[0]['status'],'in_stock')
 def test_reappearing_watch_returns_to_active(self):
  old=watch(status='sold');old['archived_at']='yesterday'
  result=archive.reconcile([old],[watch()],'today')[0]
  self.assertNotIn('archived_at',result);self.assertEqual(result['status'],'in_stock')
 def test_same_folder_new_stock_number_archives_old_watch(self):
  result=archive.reconcile([watch()],[watch(title='Daytona VSF G99999')],'today')
  self.assertEqual(len(result),2);self.assertEqual(sum(p['status']=='sold' for p in result),1)
 def test_existing_folder_without_photos_is_not_sold(self):
  f={'folder_id':'folder1','name':'Daytona VSF G12345','status':'in_stock'}
  self.assertEqual(archive.reconcile([watch()],[],'today',[f])[0]['status'],'in_stock')
 def test_old_archive_date_is_preserved(self):
  old=watch(status='sold');old['archived_at']='yesterday'
  self.assertEqual(archive.reconcile([old],[],'today')[0]['archived_at'],'yesterday')
 def test_no_stock_number_uses_folder_id(self):
  self.assertEqual(archive.identity(watch(title='Vintage watch')),'folder:folder1')
 def test_duplicate_stock_number_stops_refresh(self):
  with self.assertRaises(ValueError):archive.reconcile([],[watch(),watch(folder='other')],'today')
 def test_brand_model_grouping(self):
  self.assertEqual(archive.classify('Batgirl VSF 6X07A829'),('Rolex','GMT-Master II'))
  self.assertEqual(archive.classify('PP 5167r 330 DDF G07271'),('Patek Philippe','Aquanaut'))
  self.assertEqual(archive.classify('Omega SMP Summer Blue G07035'),('Omega','Seamaster'))

class FirstSeenTests(unittest.TestCase):
 def test_new_watch_gets_detection_date(self):
  for status in ('in_stock','inbound'):
   self.assertEqual(archive.reconcile([],[watch(status=status)],'2026-09-11T19:00:00Z')[0]['first_seen_at'],'2026-09-11T19:00:00Z')
 def test_existing_inventory_is_not_marked_new(self):
  self.assertIsNone(archive.reconcile([watch()],[watch()],'now')[0]['first_seen_at'])
 def test_date_survives_moves_sale_and_return(self):
  old=watch(status='inbound');old['first_seen_at']='2026-09-01T00:00:00Z'
  moved=archive.reconcile([old],[watch(folder='moved')],'later')[0]
  sold=archive.reconcile([moved],[],'later')[0]
  returned=archive.reconcile([sold],[watch()],'later')[0]
  self.assertEqual(returned['first_seen_at'],old['first_seen_at'])
