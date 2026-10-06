"""Read-only smoke/performance checks against the configured DBLP database."""
import json
from time import perf_counter
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.duckdb import clear_cache


def main():
    clear_cache()
    client = TestClient(app)
    author = client.get('/api/authors/top?limit=1').json()[0]['author_id']
    venue = client.get('/api/venues/top?limit=1').json()[0]['venue_id']
    checks = [
        '/api/overview', '/api/publications/timeline', '/api/publications/growth',
        '/api/publications/types', '/api/publications/types/timeline',
        f'/api/authors/{author}', f'/api/venues/{venue}', '/api/trends/decades',
        '/api/authors/rising?limit=20', '/api/authors/collaborative?limit=20',
        '/api/authors/longest-active?limit=20', '/api/authors/productivity-scatter',
        '/api/venues/growth?limit=20', '/api/venues/heatmap?start_year=2015&end_year=2025',
        '/api/network/stats',
        f'/api/collaboration?author_id={author}&limit=500',
        f'/api/collaboration?author_id={author}&limit=50',
        f'/api/collaboration?author_id={author}&limit=50&start_year=2020&end_year=2025',
        '/api/insights', '/api/search?q=Hinton', '/api/venues/trends',
        '/api/trends/collaboration-evolution', '/api/trends/team-distribution',
        # New Intelligence Endpoints
        '/api/topics', '/api/topics/timeline', '/api/topics/1',
        '/api/publications/search?q=neural&limit=10',
        '/api/publications/search?limit=10&sort_by=citations',
        '/api/authors/momentum?limit=20',
        '/api/authors/most-cited?limit=20',
        '/api/authors/highest-impact?limit=20',
        # Strategic Scientific Intelligence Endpoints
        '/api/fields',
        '/api/fields/definitions',
        '/api/fields/1',
        '/api/authors/field-normalized?limit=10',
        f'/api/authors/{author}/impact',
        f'/api/authors/{author}/career',
        f'/api/authors/{author}/similar?limit=5',
        '/api/knowledge-graph?limit=50',
        '/api/benchmark/presets',
        '/api/benchmark/compare?type=institution&entity1_id=1&entity2_id=2',
        '/api/data-quality',
        '/api/data-quality/health',
        '/api/data-quality/transparency',
        # Final Strategic Intelligence Layer Endpoints
        '/api/forecast/overview',
        '/api/forecast/topic/1',
        '/api/forecast/breakout-researchers?limit=10',
        '/api/search/semantic?q=transformer+attention&limit=10',
        '/api/publications/1/lineage',
        '/api/publications/1',
        '/api/assistant/query',
    ]
    results = []
    for path in checks:
        times = []
        for _ in range(2):
            started = perf_counter()
            response = client.get(path)
            if path == '/api/assistant/query':
                response = client.post(path, json={'query': 'Analyze the future of AI research'})
            else:
                response = client.get(path)
            times.append(round((perf_counter() - started) * 1000, 2))
            assert response.status_code == 200, (path, response.status_code, response.text)
        data = response.json()
        if path.startswith('/api/collaboration'):
            assert len(data['nodes']) <= 500
            assert len(data['edges']) <= 499
            assert len(data['edges']) >= 1
            assert data['center_id'] in {n['id'] for n in data['nodes']}
        if 'rising' in path or path.startswith('/api/venues/growth') or 'momentum' in path:
            assert len(data['items']) <= 20
        row = dict(path=path, cold_ms=times[0], warm_ms=times[1], bytes=len(response.content))
        results.append(row)
        print(json.dumps(row), flush=True)
    client.close()
    return results


if __name__ == '__main__':
    main()
