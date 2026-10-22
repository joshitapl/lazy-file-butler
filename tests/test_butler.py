from pathlib import Path
import tempfile, unittest, uuid, sys, os
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import butler

class ButlerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name).resolve();self.root=self.base/'mess';self.root.mkdir();self.old=butler.DB_PATH;butler.DB_PATH=self.base/'test.db'
 def tearDown(self):butler.DB_PATH=self.old;self.temp.cleanup()
 def plan(self,names=('one.txt','two.txt')):
  rows=[]
  for name in names:
   p=self.root/name;p.write_text('Content '+name);rows.append(dict(id=uuid.uuid4().hex,original=name,hash=butler.digest(p),status='suggested',name='Readable '+name,category='Documents'))
  plan=dict(id=uuid.uuid4().hex,state='preview',root=str(self.root),rows=rows);butler.save('plans',plan['id'],plan)
  return plan,[dict(id=r['id'],name=r['name'],category=r['category']) for r in rows]
 def test_apply_undo_preserves_contents(self):
  p,e=self.plan();op=butler.apply_plan(p['id'],e);self.assertEqual(op['state'],'applied');self.assertFalse((self.root/'one.txt').exists())
  for m in op['moves']:self.assertEqual(butler.digest(Path(m['destination'])),m['hash'])
  self.assertEqual(butler.undo(op['id'])['state'],'undone');self.assertEqual((self.root/'one.txt').read_text(),'Content one.txt');self.assertEqual(butler.undo(op['id'])['state'],'undone')
 def test_changed_source_blocks_all_moves(self):
  p,e=self.plan();(self.root/'two.txt').write_text('Edited')
  with self.assertRaisesRegex(ValueError,'changed since'):butler.apply_plan(p['id'],e)
  self.assertTrue((self.root/'one.txt').exists());self.assertFalse((self.root/'Organized').exists())
 def test_duplicate_targets_block_all_moves(self):
  p,e=self.plan();e[1]['name']=e[0]['name'].upper()
  with self.assertRaisesRegex(ValueError,'duplicated'):butler.apply_plan(p['id'],e)
  self.assertTrue((self.root/'one.txt').exists())
 def test_undo_protects_user_edits(self):
  p,e=self.plan();op=butler.apply_plan(p['id'],e);Path(op['moves'][0]['destination']).write_text('User edits')
  with self.assertRaisesRegex(ValueError,'protect your edits'):butler.undo(op['id'])
  self.assertEqual(Path(op['moves'][0]['destination']).read_text(),'User edits');self.assertFalse((self.root/'two.txt').exists())
 def test_undo_protects_new_file_at_old_path(self):
  p,e=self.plan();op=butler.apply_plan(p['id'],e);(self.root/'one.txt').write_text('New file')
  with self.assertRaisesRegex(ValueError,'exists in its old'):butler.undo(op['id'])
  self.assertEqual((self.root/'one.txt').read_text(),'New file')
 def test_symlink_destination_rejected(self):
  p,e=self.plan();outside=self.base/'outside';outside.mkdir();(self.root/'Organized').symlink_to(outside,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'Symbolic'):butler.apply_plan(p['id'],e)
  self.assertEqual(list(outside.iterdir()),[])
 def test_partial_failure_can_undo(self):
  p,e=self.plan();real=butler.move_exclusive;calls=[]
  def move(src,dst):
   calls.append(src)
   if len(calls)==2:raise OSError('Simulated failure')
   real(src,dst)
  with patch.object(butler,'move_exclusive',side_effect=move):op=butler.apply_plan(p['id'],e)
  self.assertEqual(op['state'],'partial');self.assertEqual(butler.undo(op['id'])['state'],'undone');self.assertTrue((self.root/'one.txt').exists());self.assertTrue((self.root/'two.txt').exists())
 def test_interrupted_link_can_undo(self):
  p,e=self.plan(('one.txt',));src=self.root/'one.txt';dst=self.root/'Organized'/'Documents'/'name.txt';dst.parent.mkdir(parents=True);os.link(src,dst)
  op=dict(id='interrupted',root=str(self.root),state='applying',moves=[dict(original=str(src),destination=str(dst),hash=butler.digest(src),state='moving')]);butler.save('history',op['id'],op)
  self.assertEqual(butler.undo(op['id'])['state'],'undone');self.assertTrue(src.exists());self.assertFalse(dst.exists())
 def test_exclusive_move_never_overwrites(self):
  src=self.root/'a';dst=self.root/'b';src.write_text('a');dst.write_text('b')
  with self.assertRaises(FileExistsError):butler.move_exclusive(src,dst)
  self.assertEqual(dst.read_text(),'b');self.assertEqual(src.read_text(),'a')
 def test_analysis_skips_unsupported_and_organized(self):
  (self.root/'note.txt').write_text('Lecture on binary search');(self.root/'image.bin').write_bytes(b'image');(self.root/'Organized').mkdir();(self.root/'Organized'/'old.txt').write_text('Already organized');butler.JOBS['test']={'state':'running'}
  with patch.object(butler,'suggest',return_value=dict(name='Binary search.txt',category='Study & research',reason='Lecture topic',confidence=.9)):butler.analyze('test',str(self.root),True,'test-model')
  p=butler.get('plans','test');self.assertEqual(len(p['rows']),2);self.assertEqual(sum(r['status']=='suggested' for r in p['rows']),1);self.assertTrue((self.root/'note.txt').exists())
 def test_names_cannot_escape_folder(self):
  self.assertNotIn('/',butler.safe_name('../../outside.txt','.txt'));self.assertNotIn('\\',butler.safe_name('..\\outside.txt','.txt'));self.assertEqual(butler.safe_name('Title.pdf','.pdf'),'Title.pdf')
if __name__=='__main__':unittest.main()
