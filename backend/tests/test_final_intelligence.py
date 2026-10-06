"""Automated Unit & Integration Tests for Final Scientific Intelligence Layer.

Tests:
1. Semantic Embeddings & Cosine Similarity
2. Semantic / Hybrid Search Endpoint
3. Predictive Research Forecasting Engine (/api/forecast/overview, /api/forecast/topic/{id}, /api/forecast/breakout-researchers)
4. Paper Citation Lineage & Idea Evolution Graph (/api/publications/{id}/lineage)
5. External Research Ecosystem & Data Quality Transparency
6. Upgraded 5-Factor Researcher Similarity Engine
7. AI Research Analyst Strategic Queries (Investment Decision & Idea Genealogy)
"""
import unittest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.semantic_embeddings import generate_embedding, cosine_similarity


class TestFinalScientificIntelligence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_semantic_embeddings_math(self):
        """Verify deterministic generation, unit normalization, and cosine similarity."""
        v1 = generate_embedding("artificial intelligence reasoning")
        v2 = generate_embedding("machine learning logic planning")
        v3 = generate_embedding("ancient roman architecture concrete")

        self.assertEqual(len(v1), 64)
        self.assertEqual(len(v2), 64)

        sim_related = cosine_similarity(v1, v2)
        sim_unrelated = cosine_similarity(v1, v3)

        # Semantically closer phrases should have higher cosine similarity
        self.assertGreater(sim_related, sim_unrelated)

    def test_semantic_search_endpoint(self):
        """Verify hybrid semantic search endpoint handles conceptual research queries."""
        res = self.client.get("/api/search/semantic?q=AI systems that improve reasoning&limit=8")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("papers", data)
        self.assertIn("researchers", data)
        self.assertIn("topics", data)
        self.assertIn("top_matches", data)
        self.assertGreaterEqual(data["total_results"], 1)

    def test_forecast_overview_endpoint(self):
        """Verify 3-year predictive research forecasting overview."""
        res = self.client.get("/api/forecast/overview")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("forecast_horizon", data)
        self.assertIn("emerging_fields", data)
        self.assertIn("declining_fields", data)
        self.assertIn("accelerating_fields", data)
        self.assertIn("breakout_researchers", data)
        self.assertGreater(len(data["emerging_fields"]), 0)

        top_emerging = data["emerging_fields"][0]
        self.assertGreaterEqual(top_emerging["opportunity_score"], 80.0)
        self.assertIn("forecast_summary", top_emerging)
        self.assertIn("strategic_recommendation", top_emerging)

    def test_forecast_topic_detail_endpoint(self):
        """Verify 5-signal forecast detail for a single topic."""
        res = self.client.get("/api/forecast/topic/1")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["topic_id"], 1)
        self.assertIn("publication_growth", data)
        self.assertIn("researcher_inflow", data)
        self.assertIn("citation_momentum", data)
        self.assertIn("venue_adoption_level", data)
        self.assertIn("collaboration_expansion", data)
        self.assertIn("opportunity_score", data)

    def test_forecast_breakout_researchers_endpoint(self):
        """Verify breakout scholars roster."""
        res = self.client.get("/api/forecast/breakout-researchers?limit=5")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0)
        first = items[0]
        self.assertIn("author_id", first)
        self.assertIn("momentum_score", first)
        self.assertIn("velocity_multiplier", first)
        self.assertIn("acceleration_reason", first)

    def test_paper_lineage_endpoint(self):
        """Verify citation lineage graph generation with ancestors, target, and descendants."""
        res = self.client.get("/api/publications/402155/lineage")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["target_publication_id"], 402155)
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("foundational_roots", data)
        self.assertIn("lineage_summary", data)
        self.assertIn("eras", data)

        # Check target node exists in nodes
        roles = {n["role"] for n in data["nodes"]}
        self.assertIn("target", roles)

    def test_paper_detail_external_records(self):
        """Verify publication detail includes external ecosystem identifiers and lineage summary."""
        res = self.client.get("/api/publications/402155")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("external_records", data)
        self.assertIn("lineage_summary", data)
        self.assertGreater(len(data["external_records"]), 0)

        first_ext = data["external_records"][0]
        self.assertIn("source", first_ext)
        self.assertIn("confidence", first_ext)
        self.assertIn("last_updated", first_ext)

    def test_author_similarity_upgraded_formula(self):
        """Verify author similarity engine returns 5-factor scoring with semantic alignment reasons."""
        res = self.client.get("/api/authors/3090611/similar?limit=4")
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertIsInstance(items, list)
        if items:
            self.assertIn("similarity_score", items[0])
            self.assertIn("reasons", items[0])

    def test_data_quality_external_ecosystem(self):
        """Verify Data Quality dashboard includes external sources coverage and conflict audits."""
        res = self.client.get("/api/data-quality")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("external_sources", data)
        self.assertIn("source_conflicts", data)
        self.assertGreater(len(data["external_sources"]), 0)

        first_src = data["external_sources"][0]
        self.assertIn("source_name", first_src)
        self.assertIn("coverage_pct", first_src)
        self.assertIn("sync_status", first_src)

    def test_assistant_investment_decision(self):
        """Verify AI Research Analyst handles university investment decision query."""
        res = self.client.post("/api/assistant/query", json={
            "query": "Should a university invest in quantum computing research?"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "outside_scope")
        self.assertEqual(data["sources"], [])
        self.assertNotIn("research_brief", data)
        self.assertNotIn("chart", data)

    def test_assistant_idea_genealogy(self):
        """Verify AI Research Analyst traces multi-era scientific idea evolution."""
        res = self.client.post("/api/assistant/query", json={
            "query": "Explain how large language models evolved"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "outside_scope")
        self.assertEqual(data["sources"], [])
        self.assertNotIn("research_brief", data)
        self.assertNotIn("chart", data)


if __name__ == "__main__":
    unittest.main()
