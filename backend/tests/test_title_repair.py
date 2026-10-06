"""Candidate migration checks use isolated files, never the active database."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import duckdb
from scripts.prepare_title_repair_candidate import prepare, sha256, source_rows, LocalXMLOnly


class TitleRepair(unittest.TestCase):
    def test_entities_nested_text_and_ids_without_author_remapping(self):
        with TemporaryDirectory(prefix='title-repair-') as temp:
            root=Path(temp)
            xml=root/'dblp.xml'
            dtd=root/'dblp.dtd'
            dtd.write_text('<!ENTITY uml "&#252;">',encoding='utf-8')
            xml.write_text('''<?xml version="1.0"?><!DOCTYPE dblp SYSTEM "dblp.dtd"><dblp>
<article key="journals/test/1"><author>M&uml;ller</author><title>Before <i>inside</i> after.</title><year>2020</year></article>
<book key="books/test/2"><title><i>Recovered</i> title.</title><year>2021</year></book></dblp>''',encoding='utf-8')
            rows=list(source_rows(xml.resolve(),dtd.resolve()))
            self.assertEqual(rows[0]['title'],'Before inside after.')
            self.assertEqual(rows[0]['authors'],'Müller')
            source=root/'source.duckdb'
            db=duckdb.connect(str(source))
            db.execute('CREATE TABLE publications(publication_id BIGINT,db_key VARCHAR,title VARCHAR,type VARCHAR,year INTEGER)')
            db.execute("INSERT INTO publications VALUES (1,'journals/test/1','Before','article',2020),(2,'books/test/2','','book',2021)")
            db.execute("CREATE TABLE raw_publications AS SELECT publication_id id,db_key,title,type,year,CASE WHEN publication_id=1 THEN 'M&uml;ller' ELSE '' END authors FROM publications")
            db.execute('CREATE TABLE authors(author_id BIGINT,name VARCHAR)')
            db.execute("INSERT INTO authors VALUES (99,'M&uml;ller')")
            db.close()
            original=sha256(source)
            candidate=root/'candidate.duckdb'
            report=prepare(source,xml,dtd,candidate,batch_size=1)
            self.assertEqual(sha256(source),original)
            self.assertEqual(report['state'],'candidate_review_only')
            self.assertEqual(report['after']['empty_title_exclusions'],0)
            self.assertEqual(report['changed_titles'],2)
            self.assertEqual(report['source_author_string_differences'],1)
            with duckdb.connect(str(candidate),read_only=True) as db:
                self.assertEqual(db.execute('SELECT publication_id,db_key FROM publications ORDER BY publication_id').fetchall(),[(1,'journals/test/1'),(2,'books/test/2')])
                self.assertEqual(db.execute('SELECT * FROM authors').fetchall(),[(99,'M&uml;ller')])
            with self.assertRaises(ValueError):
                prepare(source,xml,dtd,source)
            with self.assertRaises(ValueError):
                prepare(source,xml,dtd,candidate)
            with duckdb.connect(str(source)) as db:
                db.execute("UPDATE publications SET db_key='wrong/key' WHERE publication_id=1")
            rejected=root/'rejected.duckdb'
            with self.assertRaisesRegex(ValueError,'do not match'):
                prepare(source,xml,dtd,rejected,batch_size=1)
            self.assertEqual(json.loads(rejected.with_suffix('.manifest.json').read_text())['state'],'building_not_active')

    def test_resolver_rejects_other_local_files_and_network(self):
        resolver=LocalXMLOnly(Path('allowed.xml'),Path('allowed.dtd'))
        for url in ('https://example.com/dblp.dtd','file:///C:/private.txt','unexpected.dtd'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                resolver.resolve(url,None,None)


if __name__=='__main__':
    unittest.main()
