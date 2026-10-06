"""Unit and regression tests for Strategic Scientific Intelligence Platform features."""
import os
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


class TestStrategicIntelligence(unittest.TestCase):

    # -------------------------------------------------------------------------
    # FEATURE 1: Research Impact Beyond Citations
    # -------------------------------------------------------------------------
    def test_author_impact_profile(self):
        # Test with prominent researcher (e.g. H. Vincent Poor or Geoffrey Hinton)
        res = client.get('/api/authors/3090611/impact')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('overall_impact_score', data)
        self.assertGreaterEqual(data['overall_impact_score'], 0.0)
        self.assertLessEqual(data['overall_impact_score'], 100.0)
        self.assertIn('academic_impact', data)
        self.assertIn('technology_impact', data)
        self.assertIn('open_science_impact', data)
        self.assertIn('influence_growth', data)
        self.assertIn('field_percentile', data)
        self.assertIn('main_drivers', data)
        self.assertIsInstance(data['main_drivers'], list)
        self.assertGreater(len(data['main_drivers']), 0)
        self.assertIn('raw_metrics', data)
        self.assertIn('total_citations', data['raw_metrics'])

    # -------------------------------------------------------------------------
    # FEATURE 2: Field Normalization Engine
    # -------------------------------------------------------------------------
    def test_fields_list_and_baselines(self):
        res = client.get('/api/fields')
        self.assertEqual(res.status_code, 200)
        fields = res.json()
        self.assertEqual(len(fields), 8)
        first = fields[0]
        self.assertIn('field_name', first)
        self.assertIn('publication_count', first)
        self.assertIn('avg_citations_per_author', first)
        self.assertIn('avg_citations_per_paper', first)

    def test_field_definitions(self):
        res = client.get('/api/fields/definitions')
        self.assertEqual(res.status_code, 200)
        defs = res.json()
        self.assertEqual(len(defs), 8)
        self.assertEqual(defs[0]['slug'], 'ai')

    def test_field_detail(self):
        res = client.get('/api/fields/1')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('field', data)
        self.assertIn('topics', data)
        self.assertIn('top_venues', data)
        self.assertIn('top_institutions', data)

    def test_field_normalized_rankings(self):
        res = client.get('/api/authors/field-normalized?limit=20')
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertGreater(len(items), 0)
        first = items[0]
        self.assertIn('field_adjusted_impact', first)
        self.assertIn('field_adjusted_productivity', first)
        self.assertIn('field_percentile', first)
        self.assertIn('primary_field', first)
        self.assertIn('normalized_rank', first)
        self.assertGreater(first['field_adjusted_impact'], 0.0)

    # -------------------------------------------------------------------------
    # FEATURE 3: Researcher Career Intelligence
    # -------------------------------------------------------------------------
    def test_author_career_intelligence(self):
        res = client.get('/api/authors/3090611/career')
        self.assertEqual(res.status_code, 200)
        career = res.json()
        self.assertIn('career_stage', career)
        self.assertIn('career_span_years', career)
        self.assertIn('narrative', career)
        self.assertIsInstance(career['narrative'], str)
        self.assertGreater(len(career['narrative']), 30)
        self.assertIn('breakthrough_moments', career)
        self.assertIn('topic_transitions', career)

    # -------------------------------------------------------------------------
    # FEATURE 5: Researcher Similarity Engine
    # -------------------------------------------------------------------------
    def test_author_similarity(self):
        res = client.get('/api/authors/1544190/similar?limit=4')
        self.assertEqual(res.status_code, 200)
        peers = res.json()
        self.assertIsInstance(peers, list)
        if peers:
            first = peers[0]
            self.assertIn('name', first)
            self.assertIn('similarity_score', first)
            self.assertGreaterEqual(first['similarity_score'], 0)
            self.assertLessEqual(first['similarity_score'], 100)
            self.assertIn('reasons', first)
            self.assertIsInstance(first['reasons'], list)

    # -------------------------------------------------------------------------
    # FEATURE 6: Research Graph Universe
    # -------------------------------------------------------------------------
    def test_knowledge_graph_query(self):
        res = client.get('/api/knowledge-graph?q=Language&limit=30')
        self.assertEqual(res.status_code, 200)
        graph = res.json()
        self.assertIn('nodes', graph)
        self.assertIn('edges', graph)
        self.assertIn('analytics', graph)
        self.assertGreater(len(graph['nodes']), 0)
        # Check node types
        node_types = {n['entity_type'] for n in graph['nodes']}
        self.assertTrue(len(node_types) >= 2)
        # Check analytics
        analytics = graph['analytics']
        self.assertIn('influential_hubs', analytics)
        self.assertIn('cluster_distribution', analytics)

    # -------------------------------------------------------------------------
    # FEATURE 9: Benchmarking Mode
    # -------------------------------------------------------------------------
    def test_benchmark_presets(self):
        res = client.get('/api/benchmark/presets')
        self.assertEqual(res.status_code, 200)
        presets = res.json()
        self.assertGreater(len(presets), 0)

    def test_benchmark_compare_institutions(self):
        res = client.get('/api/benchmark/compare?type=institution&entity1=1&entity2=2')
        self.assertEqual(res.status_code, 200)
        report = res.json()
        self.assertEqual(report['comparison_type'], 'institution')
        self.assertIn('executive_summary', report)
        self.assertIn('metrics', report)
        self.assertGreater(len(report['metrics']), 0)
        self.assertIn('specializations', report)
        first_m = report['metrics'][0]
        self.assertIn('metric_name', first_m)
        self.assertIn('advantage', first_m)

    # -------------------------------------------------------------------------
    # FEATURE 10: Research Strategy Assistant
    # -------------------------------------------------------------------------
    def test_assistant_landscape_brief(self):
        res = client.post('/api/assistant/query', json={'query': 'Analyze AI research landscape 2026'})
        self.assertEqual(res.status_code, 200)
        resp = res.json()
        self.assertEqual(resp['status'], 'outside_scope')
        self.assertEqual(resp['sources'], [])
        self.assertNotIn('research_brief', resp)

    def test_assistant_institution_dominance(self):
        res = client.post('/api/assistant/query', json={'query': 'Which institutions dominate quantum computing?'})
        self.assertEqual(res.status_code, 200)
        resp = res.json()
        self.assertEqual(resp['status'], 'unavailable')
        self.assertEqual(resp['sources'], [])
        self.assertNotIn('chart', resp)

    # -------------------------------------------------------------------------
    # FEATURE 11: Data Quality and Trust Layer
    # -------------------------------------------------------------------------
    def test_data_quality_health(self):
        res = client.get('/api/data-quality/health')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreater(data['total_publications'], 8000000)
        self.assertGreater(data['total_authors'], 4000000)
        self.assertIn('DuckDB', data['storage_engine'])

    def test_data_quality_transparency(self):
        res = client.get('/api/data-quality/transparency')
        self.assertEqual(res.status_code, 200)
        docs = res.json()
        self.assertGreater(len(docs), 0)
        self.assertIn('formula', docs[0])
        self.assertIn('limitations', docs[0])

    def test_data_quality_overview(self):
        res = client.get('/api/data-quality')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('health', data)
        self.assertIn('audits', data)
        self.assertIn('formulas', data)
        self.assertGreater(len(data['audits']), 0)


if __name__ == '__main__':
    unittest.main()
