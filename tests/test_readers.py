from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import readers
import butler

class ReaderTests(unittest.TestCase):
    def test_later_pdf_page_is_read(self):
        pages = [MagicMock() for _ in range(7)]
        for p in pages: p.get_text.return_value = ''
        pages[5].get_text.return_value = 'Digital electronics lecture about binary to Gray code conversion and combinational logic. ' * 3
        doc = MagicMock();doc.needs_pass=False;doc.__len__.return_value=7;doc.__getitem__.side_effect=lambda i:pages[i]
        with patch('pymupdf.open') as opened:
            opened.return_value.__enter__.return_value=doc
            with patch.object(readers,'ocr_png') as ocr:
                result=readers.extract(Path('sample.pdf'))
                self.assertIn('Gray code',result['text']);self.assertEqual(result['method'],'PDF text');self.assertIn(6,result['pages']);ocr.assert_not_called()

    def test_scan_uses_ocr_and_labels_source_pages(self):
        page=MagicMock();page.get_text.return_value=''
        doc=MagicMock();doc.needs_pass=False;doc.__len__.return_value=2;doc.__getitem__.return_value=page
        with patch('pymupdf.open') as opened, patch.object(readers,'render_page',return_value=b'image'), patch.object(readers,'ocr_png',return_value='Digital electronics examination paper'):
            opened.return_value.__enter__.return_value=doc
            result=readers.extract(Path('scan.pdf'))
        self.assertEqual(result['method'],'PDF OCR');self.assertEqual(result['pages'],[1,2]);self.assertIn('examination',result['text'])

    def test_image_ocr(self):
        doc=MagicMock();doc.needs_pass=False
        with patch('pymupdf.open') as opened, patch.object(readers,'render_page',return_value=b'image'), patch.object(readers,'ocr_png',return_value='Electricity bill for October 2026'):
            opened.return_value.__enter__.return_value=doc
            result=readers.extract(Path('screenshot.png'))
        self.assertEqual(result['method'],'Image OCR');self.assertIn('Electricity',result['text'])

    def test_empty_ocr_does_not_claim_readable_text(self):
        doc=MagicMock();doc.needs_pass=False;doc.__len__.return_value=1;doc.__getitem__.return_value.get_text.return_value=''
        with patch('pymupdf.open') as opened, patch.object(readers,'render_page',return_value=b'image'), patch.object(readers,'ocr_png',return_value=''):
            opened.return_value.__enter__.return_value=doc
            result=readers.extract(Path('blank.pdf'))
        self.assertEqual(result['text'],'')

    def test_file_type_placement_and_undo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();p=root/'installer.dmg';p.write_bytes(b'demo installer')
            old=butler.DB_PATH;butler.DB_PATH=root/'journal.db'
            try:
                row=dict(id='r',original=p.name,name=p.name,hash=butler.digest(p),status='file_type',category='Installers')
                butler.save('plans','p',dict(root=str(root),rows=[row],state='preview'))
                op=butler.apply_plan('p',[dict(id='r',name=p.name,category='Installers')])
                self.assertTrue((root/'Organized'/'Installers'/p.name).exists())
                self.assertEqual(butler.undo(op['id'])['state'],'undone');self.assertEqual(p.read_bytes(),b'demo installer')
            finally:butler.DB_PATH=old

    def test_cache_separates_models_and_preserves_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=butler.DB_PATH;butler.DB_PATH=Path(tmp)/'db'
            try:
                result={'message':{'content':'{"name":"Binary Search Notes","category":"Study & research","reason":"Binary search lecture","confidence":0.8}'}}
                with patch.object(butler,'request',return_value=result) as request:
                    butler.suggest(Path('a.txt'),'Lecture about binary search','one')
                    cached=butler.suggest(Path('b.md'),'Lecture about binary search','one')
                    self.assertEqual(request.call_count,1);self.assertTrue(cached['cached']);self.assertTrue(cached['name'].endswith('.md'))
                    butler.suggest(Path('a.txt'),'Lecture about binary search','two');self.assertEqual(request.call_count,2)
            finally:butler.DB_PATH=old

    def test_generic_model_name_is_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=butler.DB_PATH;butler.DB_PATH=Path(tmp)/'db'
            try:
                invalid={'message':{'content':'{"name":"Document","category":"Documents","confidence":0.9}'}}
                valid={'message':{'content':'{"name":"Electricity Bill","category":"Bills & receipts","confidence":0.9}'}}
                with patch.object(butler,'request',side_effect=[invalid,valid]) as request:
                    result=butler.suggest(Path('a.txt'),'Electricity bill for October','one')
                    self.assertEqual(request.call_count,2);self.assertEqual(result['name'],'Electricity Bill.txt')
            finally:butler.DB_PATH=old

class CategoryChecks(unittest.TestCase):
    def test_exam_mislabeled_as_bill_is_flagged(self):
        result=butler.check_category(dict(category='Bills & receipts',reason='Exam paper',confidence=.9),
                                    'Degree examinations. Answer all questions. Maximum marks: 100',Path('a.pdf'))
        self.assertEqual(result['category'],'Study & research');self.assertTrue(result['category_checked']);self.assertLessEqual(result['confidence'],.7)

    def test_digital_logic_is_not_source_code(self):
        result=butler.check_category(dict(category='Code',reason='Binary code converters',confidence=.9),
                                    'Digital circuits and binary to gray code converters',Path('notes.pdf'))
        self.assertEqual(result['category'],'Study & research')

class CategoryBoundaries(unittest.TestCase):
    def test_recipe_is_not_code(self):
        result=butler.check_category(dict(category='Code',reason='Recipe',confidence=.9),'Ingredients: chickpeas. Simmer for 15 minutes.',Path('note.txt'))
        self.assertEqual(result['category'],'Documents');self.assertTrue(result['category_checked'])

    def test_text_notes_are_not_audio(self):
        result=butler.check_category(dict(category='Audio & video',reason='Lecture',confidence=.9),'Lecture notes: binary search. Course: Algorithms.',Path('note.md'))
        self.assertEqual(result['category'],'Study & research')

if __name__=='__main__':unittest.main()
