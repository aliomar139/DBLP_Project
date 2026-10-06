"""Migration invariants and independently expected classification results."""
from collections import defaultdict, Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import duckdb

from scripts.extend_repair_candidate import author_rows, stage_author_changes, rebuild_classifications


class CandidateExtension(unittest.TestCase):
    def test_source_entities_literal_text_and_collisions_preserve_ids(self):
        with TemporaryDirectory(prefix='author-repair-') as directory:
            root=Path(directory)
            dtd=root/'dblp.dtd'
            dtd.write_text('<!ENTITY uml "&#252;">',encoding='utf-8')
            xml=root/'dblp.xml'
            xml.write_text('''<!DOCTYPE dblp SYSTEM "dblp.dtd"><dblp>
<article key="p/1"><author>M&uml;ller</author></article>
<article key="p/2"><author>M&#252;ller</author></article>
<article key="p/3"><author>X&uml;</author></article>
<article key="p/4"><author>X&amp;uml;</author></article></dblp>''',encoding='utf-8')
            with duckdb.connect(':memory:') as db:
                db.execute('CREATE TABLE publications(publication_id BIGINT)')
                db.execute('INSERT INTO publications VALUES (1),(2),(3),(4)')
                db.execute('CREATE TABLE raw_publications(id BIGINT,db_key VARCHAR,authors VARCHAR)')
                db.executemany('INSERT INTO raw_publications VALUES (?,?,?)',[(1,'p/1','M&uml;ller'),(2,'p/2','Müller'),(3,'p/3','X&uml;'),(4,'p/4','X&uml;')])
                db.execute('CREATE TABLE authors(author_id BIGINT,name VARCHAR)')
                db.executemany('INSERT INTO authors VALUES (?,?)',[(1,'M&uml;ller'),(2,'Müller'),(3,'X&uml;')])
                result=stage_author_changes(db,xml,dtd,batch_size=1)
                self.assertEqual(result['changed_author_names'],1)
                self.assertEqual(result['ambiguous_author_ids_preserved'],1)
                self.assertEqual(result['collision_name_groups'],1)
                self.assertEqual(result['collision_author_ids'],2)
                self.assertEqual(db.execute('SELECT * FROM authors ORDER BY author_id').fetchall(),[(1,'Müller'),(2,'Müller'),(3,'X&uml;')])
                self.assertEqual(db.execute('SELECT authors FROM raw_publications ORDER BY id').fetchall(),[('Müller',),('Müller',),('Xü',),('X&uml;',)])

    def test_source_mismatch_is_rejected_before_name_update(self):
        with TemporaryDirectory(prefix='author-mismatch-') as directory:
            root=Path(directory)
            (root/'dblp.dtd').write_text('<!ENTITY uml "&#252;">')
            (root/'dblp.xml').write_text('<!DOCTYPE dblp SYSTEM "dblp.dtd"><dblp><article key="p/1"><author>X&uml;</author></article></dblp>')
            with duckdb.connect(':memory:') as db:
                db.execute('CREATE TABLE publications(publication_id BIGINT)')
                db.execute('INSERT INTO publications VALUES (1)')
                db.execute('CREATE TABLE raw_publications(id BIGINT,db_key VARCHAR,authors VARCHAR)')
                db.execute("INSERT INTO raw_publications VALUES (1,'wrong/key','X&uml;')")
                with self.assertRaisesRegex(ValueError,'does not match'):
                    stage_author_changes(db,root/'dblp.xml',root/'dblp.dtd',1)

    def test_classification_distinct_pairs_ties_filters_and_missing_data(self):
        with duckdb.connect(':memory:') as db:
            db.execute('CREATE TABLE publications(publication_id BIGINT,title VARCHAR,year INTEGER,venue_id BIGINT)')
            db.executemany('INSERT INTO publications VALUES (?,?,?,?)',[
                (1,'neural vision',2020,1),(2,'neural vision',2021,1),(3,'neural',1969,1),
                (4,'neural',None,1),(5,'neural',2027,1),(6,'100% literal',2020,1),
                (7,'1000 literal',2020,1)])
            db.execute('CREATE TABLE topics(topic_id BIGINT,topic_name VARCHAR,category VARCHAR,description VARCHAR,first_seen_year INTEGER,latest_activity_year INTEGER,publication_count BIGINT,growth_rate FLOAT)')
            db.executemany('INSERT INTO topics VALUES (?,?,?,?,?,?,?,?)',[(i,f'Topic {i}','Project','not evidence',1970,2026,999,999) for i in (1,2,3,4,5)])
            db.execute('CREATE TABLE topic_keywords(topic_id BIGINT,keyword VARCHAR,weight FLOAT)')
            db.executemany('INSERT INTO topic_keywords VALUES (?,?,?)',[(1,'neural',1),(1,'vision',1),(2,'vision',1),(3,'vision',1),(5,'100%',1)])
            db.execute('CREATE TABLE publication_topics(publication_id BIGINT,topic_id BIGINT,confidence_score FLOAT)')
            db.execute('CREATE TABLE topic_year_stats(topic_id BIGINT,year INTEGER,publication_count BIGINT)')
            db.execute('CREATE TABLE publication_authors(publication_id BIGINT,author_id BIGINT)')
            db.execute('INSERT INTO publication_authors VALUES (1,1),(1,1),(2,1),(5,1),(6,1)')
            db.execute('CREATE TABLE author_topics(author_id BIGINT,topic_id BIGINT,publication_count BIGINT,share_percentage DOUBLE)')
            db.execute('CREATE TABLE venue_topics(venue_id BIGINT,topic_id BIGINT,publication_count BIGINT,share_percentage DOUBLE)')
            db.execute('CREATE TABLE authors(author_id BIGINT,name VARCHAR)')
            db.execute("INSERT INTO authors VALUES (1,'Decoded Name'),(2,'Other')")
            db.execute('CREATE TABLE author_stats(author_id BIGINT,name VARCHAR,publication_count BIGINT)')
            db.execute('CREATE TABLE author_collaboration_dashboard(author1_id BIGINT,author2_id BIGINT,weight BIGINT)')
            db.execute('INSERT INTO author_collaboration_dashboard VALUES(1,2,7)')
            db.execute('CREATE TABLE author_collaboration_dashboard_named(author1 VARCHAR,author2 VARCHAR,weight BIGINT)')
            db.execute('CREATE TABLE author_momentum(author_id BIGINT,name VARCHAR,primary_topic VARCHAR,explanation VARCHAR,momentum_score DOUBLE)')
            db.execute("INSERT INTO author_momentum VALUES (1,'Old','Wrong','Wrong',12.3)")
            rebuild_classifications(db)
            self.assertEqual(db.execute('SELECT publication_id,topic_id FROM publication_topics ORDER BY 1,2').fetchall(),[(1,1),(1,2),(2,1),(2,2),(5,1),(6,5)])
            self.assertEqual(db.execute('SELECT publication_count FROM topics WHERE topic_id=1').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT first_seen_year,latest_activity_year,publication_count,growth_rate FROM topics WHERE topic_id=4').fetchone(),(None,None,0,None))
            self.assertEqual(db.execute('SELECT sum(publication_count) FROM topic_year_stats WHERE topic_id=1').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT topic_id,publication_count FROM author_topics ORDER BY topic_id').fetchall(),[(1,3),(2,2)])
            self.assertEqual(db.execute('SELECT publication_count FROM author_stats').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT * FROM author_collaboration_dashboard_named').fetchone(),('Decoded Name','Other',7))
            self.assertEqual(db.execute('SELECT momentum_score FROM author_momentum').fetchone()[0],12.3)
            first=db.execute('SELECT * FROM publication_topics ORDER BY 1,2').fetchall()
            rebuild_classifications(db)
            self.assertEqual(first,db.execute('SELECT * FROM publication_topics ORDER BY 1,2').fetchall())


if __name__=='__main__':unittest.main()
