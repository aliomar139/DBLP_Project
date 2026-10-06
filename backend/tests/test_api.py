"""API regression tests on an isolated, deterministic DuckDB fixture."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import date
from unittest import TestCase, main
from unittest.mock import patch
import duckdb
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.duckdb import clear_cache, query


class IntelligenceAPI(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(prefix='dblp-test-', dir=Path(__file__).parent)
        cls.path = Path(cls.temp.name) / 'fixture.duckdb'
        cls.env = patch.dict(os.environ, {'DBLP_DB_PATH': str(cls.path)})
        cls.env.start()
        cls.end = date.today().year - 1
        cls.start = cls.end - 9
        c = duckdb.connect(str(cls.path))
        c.execute('CREATE TABLE authors(author_id BIGINT, name VARCHAR)')
        c.execute("INSERT INTO authors VALUES (1, 'Same Name'), (2, 'Same Name'), (3, 'New Researcher'), (4, 'Solo Researcher'), (5, '100% Literal')")
        c.execute('CREATE TABLE venues(venue_id BIGINT, name VARCHAR)')
        c.execute("INSERT INTO venues VALUES (1, 'Test Journal'), (2, 'New Venue'), (3, 'Empty Venue')")
        c.execute('CREATE TABLE publications(publication_id BIGINT, year INTEGER, venue_id BIGINT, type VARCHAR, title VARCHAR, db_key VARCHAR)')
        papers = [
            (1,2000,1,'article','Quantum Algorithms and Large Language Models','conf/test/p1'),
            (2,cls.start-1,1,'article','Historical Deep Learning Approaches','conf/test/p2'),
            (3,cls.start,1,'article','Computer Vision and Neural Networks','conf/test/p3'),
            (4,cls.end,1,'article','Cybersecurity Intrusion Detection Systems','conf/test/p4'),
            (5,cls.end,2,'article','Blockchain Smart Contracts and Consensus','conf/test/p5'),
            (6,cls.end+1,2,'article','Future Advances in Machine Learning','conf/test/p6'),
            (7,cls.end+2,2,'article','Autonomous Robotics and Navigation','conf/test/p7'),
            (8,None,1,'article','Undated Database Systems Optimization','conf/test/p8'),
            (9,cls.start+1,2,'article','Distributed Systems and Cloud Computing','conf/test/p9')
        ]
        c.executemany("INSERT INTO publications VALUES (?, ?, ?, ?, ?, ?)", papers)
        c.execute('CREATE TABLE publication_authors(publication_id BIGINT, author_id BIGINT)')
        c.executemany('INSERT INTO publication_authors VALUES (?,?)', [(1,1),(2,1),(2,2),(3,1),(3,2),(4,1),(4,3),(5,3),(6,3),(7,3),(8,1),(9,4)])
        c.execute('CREATE TABLE author_stats AS SELECT a.author_id, a.name, COUNT(pa.publication_id) AS publication_count FROM authors a LEFT JOIN publication_authors pa USING(author_id) GROUP BY a.author_id,a.name')
        c.execute('CREATE TABLE venue_stats AS SELECT v.name, COUNT(p.publication_id) AS publication_count FROM venues v LEFT JOIN publications p USING(venue_id) GROUP BY v.name')
        c.execute('CREATE TABLE publication_year_stats AS SELECT year, COUNT(*) AS publication_count FROM publications WHERE year IS NOT NULL GROUP BY year')
        c.execute('CREATE TABLE dashboard_summary AS SELECT (SELECT COUNT(*) FROM publications) AS total_publications, (SELECT COUNT(*) FROM authors) AS total_authors, (SELECT COUNT(*) FROM venues) AS total_venues, MIN(year) AS first_year, MAX(year) AS last_year FROM publications')
        c.execute('CREATE TABLE author_collaboration(author1_id BIGINT, author2_id BIGINT, weight BIGINT)')
        c.execute('INSERT INTO author_collaboration VALUES (1,2,2),(1,3,1)')
        c.execute('CREATE TABLE author_collaboration_dashboard(author1_id BIGINT, author2_id BIGINT, weight BIGINT)')
        c.execute('INSERT INTO author_collaboration_dashboard VALUES (1,2,2),(1,3,1)')
        c.execute('CREATE TABLE author_collaboration_dashboard_named(author1 VARCHAR, author2 VARCHAR, weight BIGINT)')
        c.execute("INSERT INTO author_collaboration_dashboard_named VALUES ('Same Name', 'Same Name', 2)")

        # Topics Fixtures
        c.execute('CREATE TABLE topics(topic_id BIGINT PRIMARY KEY, topic_name VARCHAR, category VARCHAR, description VARCHAR, first_seen_year INT, latest_activity_year INT, publication_count BIGINT, growth_rate FLOAT)')
        c.execute("INSERT INTO topics VALUES (1, 'Artificial Intelligence', 'AI & ML', 'Core intelligent systems', 2000, 2025, 10, 150.0), (2, 'Computer Vision', 'AI & ML', 'Visual recognition', 2005, 2025, 8, 80.0)")
        c.execute('CREATE TABLE topic_keywords(topic_id BIGINT, keyword VARCHAR, weight FLOAT)')
        c.execute("INSERT INTO topic_keywords VALUES (1, 'neural', 1.0), (2, 'vision', 1.0)")
        c.execute('CREATE TABLE publication_topics(publication_id BIGINT, topic_id BIGINT, confidence_score FLOAT)')
        c.execute("INSERT INTO publication_topics VALUES (1, 1, 0.9), (3, 2, 0.8), (4, 1, 0.7)")
        c.execute('CREATE TABLE topic_year_stats(topic_id BIGINT, year INT, publication_count BIGINT)')
        c.execute("INSERT INTO topic_year_stats VALUES (1, 2020, 2), (1, 2021, 3), (2, 2020, 1), (2, 2021, 2)")
        c.execute('CREATE TABLE author_topics(author_id BIGINT, topic_id BIGINT, publication_count BIGINT, share_percentage FLOAT)')
        c.execute("INSERT INTO author_topics VALUES (1, 1, 4, 80.0), (3, 2, 3, 60.0)")
        c.execute('CREATE TABLE venue_topics(venue_id BIGINT, topic_id BIGINT, publication_count BIGINT, share_percentage FLOAT)')
        c.execute("INSERT INTO venue_topics VALUES (1, 1, 5, 50.0), (2, 2, 4, 40.0)")

        # Citations & Impact Fixtures
        c.execute('CREATE TABLE publication_citations(publication_id BIGINT PRIMARY KEY, citations INT, influential_citations INT, citation_velocity FLOAT)')
        c.execute("INSERT INTO publication_citations VALUES (1, 45, 8, 4.5), (2, 12, 2, 1.2), (3, 120, 25, 12.0), (4, 5, 1, 1.0), (5, 80, 15, 8.0), (6, 0, 0, 0.0), (7, 0, 0, 0.0), (8, 2, 0, 0.2), (9, 30, 6, 3.0)")
        c.execute('CREATE TABLE author_impact_stats(author_id BIGINT PRIMARY KEY, total_citations BIGINT, avg_citations_per_paper FLOAT, h_index INT, citation_velocity FLOAT, highly_cited_papers_count INT)')
        c.execute("INSERT INTO author_impact_stats VALUES (1, 182, 36.4, 3, 18.7, 1), (2, 57, 28.5, 2, 5.7, 0), (3, 205, 51.2, 4, 21.0, 1), (4, 30, 30.0, 1, 3.0, 0), (5, 0, 0.0, 0, 0.0, 0)")

        # Institutions Fixtures
        c.execute('CREATE TABLE institutions(institution_id BIGINT PRIMARY KEY, name VARCHAR, short_name VARCHAR, country VARCHAR, type VARCHAR, publication_count BIGINT, citation_count BIGINT, h_index INT)')
        c.execute("INSERT INTO institutions VALUES (1, 'Stanford University', 'Stanford', 'United States', 'University', 500, 12500, 45), (2, 'MIT', 'MIT', 'United States', 'University', 600, 14000, 50)")
        c.execute('CREATE TABLE author_institutions(author_id BIGINT, institution_id BIGINT)')
        c.execute("INSERT INTO author_institutions VALUES (1, 1), (2, 1), (3, 2), (4, 2)")
        c.execute('CREATE TABLE institution_collaboration(institution1_id BIGINT, institution2_id BIGINT, weight BIGINT)')
        c.execute("INSERT INTO institution_collaboration VALUES (1, 2, 15)")
        c.execute('CREATE TABLE institution_year_stats(institution_id BIGINT, year INT, publication_count BIGINT)')
        c.execute("INSERT INTO institution_year_stats VALUES (1, 2020, 40), (1, 2021, 55), (2, 2020, 50), (2, 2021, 65)")
        c.execute('CREATE TABLE institution_topics(institution_id BIGINT, topic_id BIGINT, publication_count BIGINT)')
        c.execute("INSERT INTO institution_topics VALUES (1, 1, 25), (2, 1, 30), (2, 2, 20)")

        # Momentum Fixtures
        c.execute('CREATE TABLE author_momentum(author_id BIGINT, name VARCHAR, momentum_rank INT, momentum_score FLOAT, damped_growth_rate FLOAT, raw_growth_rate FLOAT, recent_publications INT, historical_publications INT, recent_collaborators INT, career_stage VARCHAR, career_span INT, primary_topic VARCHAR, explanation VARCHAR)')
        c.execute("INSERT INTO author_momentum VALUES (3, 'New Researcher', 1, 1250.5, 300.0, 300.0, 4, 1, 2, 'Early-Career', 4, 'Computer Vision', 'Ranked #1 with Momentum Score 1250.5: +300.0% acceleration, 4 papers published, 2 active co-authors, Early-Career researcher active in Computer Vision.')")
        c.close()
        clear_cache()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        clear_cache()
        cls.env.stop()
        cls.temp.cleanup()

    def get(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_author_profile_counts_and_identity(self):
        a = self.get('/api/authors/1')
        self.assertEqual(a['total_publications'], 5)
        self.assertEqual(a['first_publication_year'], 2000)
        self.assertEqual(a['last_publication_year'], self.end)
        self.assertEqual(a['active_years'], 4)
        self.assertEqual(a['collaborator_count'], 2)
        self.assertEqual(a['collaboration_strength'], 3)
        self.assertEqual(a['collaborators'][0]['author_id'], 2)
        self.assertEqual(a['collaborators'][0]['shared_papers'], 2)
        self.assertIsNotNone(a['collaborators'][0]['coauthorship_share'])
        self.assertIn('total_solo_papers', a)
        self.assertIn('total_collaborative_papers', a)
        self.assertIn('collaboration_ratio', a)
        self.assertIn('productivity_breakdown', a)
        self.assertEqual(a['top_venues'][0]['papers'], 5)
        self.assertEqual(sum(r['count'] for r in a['yearly_activity']), 4)

    def test_author_without_publications(self):
        a = self.get('/api/authors/5')
        self.assertIsNone(a['first_publication_year'])
        self.assertEqual(a['career_duration'], 0)
        self.assertEqual(a['yearly_activity'], [])

    def test_calendar_gaps_and_zero_baseline(self):
        rows = self.get('/api/publications/timeline')
        by_year = {r['year']:r for r in rows}
        self.assertEqual(by_year[2001]['count'], 0)
        self.assertEqual(by_year[2001]['growth_rate'], -100)
        self.assertIsNone(by_year[self.start-1]['growth_rate'])

    def test_venue_profile(self):
        v = self.get('/api/venues/1')
        self.assertEqual(v['total_publications'], 5)
        self.assertEqual(v['author_count'], 3)
        self.assertEqual(v['active_years'], 4)
        self.assertEqual(v['top_authors'][0]['author_id'], 1)
        self.assertEqual(v['top_authors'][0]['papers'], 5)

    def test_empty_venue(self):
        v = self.get('/api/venues/3')
        self.assertEqual(v['total_publications'], 0)
        self.assertEqual(v['top_authors'], [])
        self.assertIsNone(v['first_publication_year'])

    def test_rising_boundaries_and_zero_history(self):
        d = self.get('/api/authors/rising?minimum_recent=1')
        self.assertEqual((d['recent_start'], d['recent_end']), (self.start, self.end))
        rows = {r['id']:r for r in d['items']}
        self.assertEqual(rows[1]['historical_publications'], 2)
        self.assertEqual(rows[1]['recent_publications'], 2)
        self.assertEqual(rows[1]['growth_rate'], 0)
        self.assertEqual(rows[3]['recent_publications'], 2)
        self.assertIsNone(rows[3]['growth_rate'])
        self.assertIsNone(d['items'][-1]['growth_rate'])

    def test_rising_pagination_and_sort(self):
        first = self.get('/api/authors/rising?minimum_recent=1&sort=recent_publications&order=asc&limit=1')
        second = self.get('/api/authors/rising?minimum_recent=1&sort=recent_publications&order=asc&limit=1&offset=1')
        self.assertEqual(first['total'], 4)
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        empty = self.get('/api/authors/rising?minimum_recent=1&offset=100')
        self.assertEqual(empty['total'], 4)
        self.assertEqual(empty['items'], [])

    def test_venue_growth(self):
        rows = {r['id']:r for r in self.get('/api/venues/growth?minimum_recent=1')['items']}
        self.assertEqual(rows[1]['recent_publications'], 2)
        self.assertEqual(rows[1]['historical_publications'], 2)
        self.assertIsNone(rows[2]['growth_rate'])
        self.assertEqual(rows[2]['recent_publications'], 2)

    def test_search_ids_and_literal_wildcards(self):
        results = self.get('/api/search?q=Same')
        self.assertEqual({r['author_id'] for r in results['authors']}, {1,2})
        literal = self.get('/api/search?q=100%25')
        self.assertEqual([r['author_id'] for r in literal['authors']], [5])
        self.assertEqual(self.get('/api/search?q=%25%25')['authors'], [])
        self.assertTrue(results['papers_available'])
        self.assertIn('papers', results)
        self.assertEqual(len(self.get('/api/search?q=Venue&limit=1')['venues']), 1)

    def test_graph_ids_caps_and_metrics(self):
        g = self.get('/api/collaboration?author_id=1&limit=2')
        self.assertEqual(len(g['nodes']), 2)
        self.assertEqual(g['center_id'], '1')
        self.assertTrue(g['truncated'])
        self.assertEqual(g['matching_collaborators'], 2)
        self.assertEqual(g['edges'], [{'source':'1','target':'2','weight':2}])
        center = next(n for n in g['nodes'] if n['id']=='1')
        self.assertEqual(center['publications'], 5)
        self.assertEqual(center['collaborators'], 2)

    def test_graph_year_filter(self):
        g = self.get(f'/api/collaboration?author_id=1&start_year={self.end}&end_year={self.end}')
        self.assertEqual(g['edges'], [{'source':'1','target':'3','weight':1}])
        empty = self.get(f'/api/collaboration?author_id=1&start_year={self.end}&min_weight=2')
        self.assertEqual(empty['edges'], [])
        self.assertEqual(len(empty['nodes']), 1)

    def test_isolated_researcher(self):
        g = self.get('/api/collaboration?author_id=4')
        self.assertEqual(len(g['nodes']), 1)
        self.assertEqual(g['nodes'][0]['collaborators'], 0)

    def test_decade_aggregation(self):
        rows = self.get('/api/trends/decades')
        self.assertEqual(len(rows), 8)
        d = next(d for d in rows if d['decade']==2000)
        self.assertEqual(d['publications'], 1)
        self.assertEqual(d['authors'], 1)
        self.assertEqual(d['average_authors_per_paper'], 1)
        self.assertEqual(rows[0]['publications'], 0)

    def test_live_insights(self):
        d = self.get('/api/insights')
        self.assertEqual(d['through_year'], self.end)
        self.assertEqual(len(d['items']), 5)
        self.assertIn('+100.0%', d['items'][0]['observation'])
        self.assertIn('Test Journal', d['items'][2]['observation'])
        self.assertIn('2 collaborators', d['items'][3]['observation'])

    def test_input_validation_and_static_route_order(self):
        for url in ['/api/authors/-1','/api/venues/0','/api/search?q=%20%20','/api/search?q=x','/api/collaboration?limit=501','/api/collaboration?min_weight=0','/api/collaboration?start_year=2025&end_year=2000','/api/authors/rising?sort=DROP%20TABLE','/api/venues/growth?offset=-1','/api/venues/trends?venues='+','.join(str(i) for i in range(13))]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 422)
        self.get('/api/authors/rising')
        self.get('/api/venues/growth')
        self.get('/api/authors/top')
        self.get('/api/venues/top')
        self.get('/api/venues/trends')

    def test_missing_entities(self):
        for url in ['/api/authors/999','/api/venues/999','/api/collaboration?author_id=999']:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_read_only_and_cache(self):
        from backend.app.database import get_connection
        c = get_connection()
        try:
            with self.assertRaises(duckdb.Error):
                c.execute('CREATE TABLE forbidden(id INTEGER)')
        finally:
            c.close()
        with self.assertRaises(ValueError):
            query('DELETE FROM publications')
        clear_cache()
        first = self.get('/api/authors/top')
        with patch('backend.app.services.duckdb.get_connection', side_effect=AssertionError('Cache miss')):
            self.assertEqual(self.get('/api/authors/top'), first)

    def test_database_errors_do_not_leak_sql(self):
        clear_cache()
        with patch('backend.app.services.duckdb.get_connection', side_effect=duckdb.IOException('private/path and SELECT secret')):
            with self.assertLogs('backend.app.main', level='ERROR'):
                r = self.client.get('/api/authors/top')
        self.assertEqual(r.status_code, 503)
        self.assertNotIn('secret', r.text)
        self.assertNotIn('private', r.text)

    def test_collaboration_evolution_and_team_distribution(self):
        evo = self.get('/api/trends/collaboration-evolution')
        self.assertIsInstance(evo, list)
        self.assertTrue(len(evo) > 0)
        self.assertIn('average_authors_per_paper', evo[0])
        self.assertIn('unique_authors', evo[0])

        dist = self.get('/api/trends/team-distribution')
        self.assertIsInstance(dist, list)
        self.assertTrue(len(dist) > 0)
        self.assertIn('category', dist[0])
        self.assertIn('percentage', dist[0])

    def test_publications_growth_and_types_timeline(self):
        growth = self.get('/api/publications/growth')
        self.assertIsInstance(growth, list)
        self.assertTrue(len(growth) > 0)
        self.assertIn('year', growth[0])
        self.assertIn('publication_count', growth[0])

        types_tl = self.get('/api/publications/types/timeline')
        self.assertIsInstance(types_tl, list)
        self.assertTrue(len(types_tl) > 0)
        self.assertIn('type', types_tl[0])

    def test_author_advanced_rankings_and_scatter(self):
        collab = self.get('/api/authors/collaborative?limit=5')
        self.assertIsInstance(collab, list)
        self.assertTrue(len(collab) > 0)
        self.assertIn('collaborators', collab[0])

        scatter = self.get('/api/authors/productivity-scatter')
        self.assertIsInstance(scatter, list)
        self.assertTrue(len(scatter) > 0)
        self.assertIn('papers', scatter[0])
        self.assertIn('collaborators', scatter[0])

    def test_network_stats_and_venue_heatmap(self):
        stats = self.get('/api/network/stats')
        self.assertIn('total_researchers', stats)
        self.assertIn('total_collaborations', stats)
        self.assertIn('weight_distribution', stats)
        self.assertTrue(len(stats['weight_distribution']) > 0)

        heatmap = self.get('/api/venues/heatmap?start_year=2000&end_year=2025')
        self.assertIsInstance(heatmap, list)

    def test_insights_card_generation(self):
        ins = self.get('/api/insights')
        self.assertIn('items', ins)
        self.assertTrue(any('Strongest scientific collaboration' in item['title'] for item in ins['items']))

    def test_topics_endpoints(self):
        topics = self.get('/api/topics')
        self.assertIsInstance(topics, list)
        self.assertTrue(len(topics) >= 2)
        self.assertEqual(topics[0]['topic_name'], 'Artificial Intelligence')
        self.assertIn('growth_rate', topics[0])

        timeline = self.get('/api/topics/timeline?topics=1,2&start_year=2020&end_year=2021')
        self.assertIsInstance(timeline, list)
        self.assertTrue(len(timeline) > 0)

        detail = self.get('/api/topics/1')
        self.assertEqual(detail['topic_name'], 'Artificial Intelligence')
        self.assertIn('top_researchers', detail)
        self.assertIn('top_venues', detail)
        self.assertIn('top_institutions', detail)
        self.assertIn('yearly_growth', detail)

    def test_publications_search_and_detail(self):
        search_res = self.get('/api/publications/search?q=Quantum')
        self.assertIn('items', search_res)
        self.assertTrue(len(search_res['items']) > 0)
        self.assertEqual(search_res['items'][0]['publication_id'], 1)
        self.assertIn('authors', search_res['items'][0])
        self.assertIn('citations', search_res['items'][0])

        detail = self.get('/api/publications/1')
        self.assertEqual(detail['publication_id'], 1)
        self.assertIn('authors', detail)
        self.assertIn('citations', detail)
        self.assertIn('influential_citations', detail)
        self.assertIn('citation_velocity', detail)

    def test_institutions_endpoints(self):
        insts = self.get('/api/institutions')
        self.assertIsInstance(insts, list)
        self.assertTrue(len(insts) >= 2)
        self.assertIn('publication_count', insts[0])

        detail = self.get('/api/institutions/1')
        self.assertEqual(detail['name'], 'Stanford University')
        self.assertIn('top_researchers', detail)
        self.assertIn('top_topics', detail)
        self.assertIn('collaborating_institutions', detail)

    def test_momentum_and_citations_rankings(self):
        momentum = self.get('/api/authors/momentum')
        self.assertIn('items', momentum)
        self.assertTrue(len(momentum['items']) > 0)
        self.assertEqual(momentum['items'][0]['name'], 'New Researcher')
        self.assertIn('explanation', momentum['items'][0])

        most_cited = self.get('/api/authors/most-cited?limit=5')
        self.assertIsInstance(most_cited, list)
        self.assertTrue(len(most_cited) > 0)
        self.assertIn('total_citations', most_cited[0])

        highest_impact = self.get('/api/authors/highest-impact?limit=5')
        self.assertIsInstance(highest_impact, list)
        self.assertTrue(len(highest_impact) > 0)
        self.assertIn('h_index', highest_impact[0])

    def test_momentum_without_title_classification_is_nullable(self):
        with duckdb.connect(str(self.path)) as db:
            db.execute('UPDATE author_momentum SET primary_topic=NULL WHERE author_id=3')
        clear_cache()
        try:
            rows = self.get('/api/authors/momentum')['items']
            self.assertIsNone(rows[0]['primary_topic'])
        finally:
            with duckdb.connect(str(self.path)) as db:
                db.execute("UPDATE author_momentum SET primary_topic='Computer Vision' WHERE author_id=3")
            clear_cache()

    def test_enhanced_collaboration_network(self):
        graph = self.get('/api/collaboration?author_id=1&limit=10')
        self.assertIn('nodes', graph)
        self.assertIn('edges', graph)
        self.assertIn('communities', graph)
        self.assertIn('bridge_nodes', graph)
        self.assertTrue(len(graph['nodes']) > 0)
        first_node = graph['nodes'][0]
        self.assertIn('community_id', first_node)
        self.assertIn('community_label', first_node)
        self.assertIn('degree_centrality', first_node)
        self.assertIn('pagerank', first_node)

    def test_assistant_query_endpoint(self):
        # Compare institutions query
        r = self.client.post('/api/assistant/query', json={'query': 'Compare Stanford vs MIT'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['status'], 'outside_scope')
        self.assertEqual(data['sources'], [])
        self.assertNotIn('chart', data)
        self.assertNotIn('research_brief', data)

        # Emerging researchers query
        r2 = self.client.post('/api/assistant/query', json={'query': 'Show me emerging AI researchers'})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()['status'], 'outside_scope')


if __name__ == '__main__':
    main()
