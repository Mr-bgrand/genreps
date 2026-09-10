import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import select_covers
class VisionTests(unittest.TestCase):
 def test_out_of_range_selection_is_rejected(self):
  with self.assertRaises(ValueError):select_covers.validate_choice({'index':8,'is_face':True,'confidence':.95,'reason':'dial'},3)
 def test_no_face_never_becomes_an_approved_cover(self):
  result=select_covers.validate_choice({'index':0,'is_face':False,'confidence':.95,'reason':'bracelets only'},3)
  self.assertTrue(result['needs_review'])
 def test_low_confidence_needs_review(self):
  self.assertTrue(select_covers.validate_choice({'index':1,'is_face':True,'confidence':.6,'reason':'blur'},3)['needs_review'])
 def test_valid_face_retains_index(self):
  self.assertEqual(select_covers.validate_choice({'index':2,'is_face':True,'confidence':.95,'reason':'clear dial'},3)['index'],2)
