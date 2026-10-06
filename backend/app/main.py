import logging
import duckdb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .routes import (
    authors, venues, trends, graph, insights, search,
    topics, publications, institutions, assistant,
    fields, knowledge_graph, benchmark, data_quality,
    forecast, bridge
)

app = FastAPI(title='DBLP Research Intelligence API', version='3.0')


@app.on_event('shutdown')
def close_local_retrieval():
    # The large local sidecar and read-only DuckDB connection are lazy-loaded.
    from .services.title_retrieval import close_full_title_index
    close_full_title_index()
    from .services.local_query_interpreter import close_interpreter
    close_interpreter()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:4173', 'http://127.0.0.1:4173'],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*']
)

for module in (
    authors, venues, trends, graph, insights, search,
    topics, publications, institutions, assistant,
    fields, knowledge_graph, benchmark, data_quality,
    forecast, bridge
):
    app.include_router(module.router)


@app.exception_handler(duckdb.Error)
async def database_error(request: Request, exc: duckdb.Error):
    logging.getLogger(__name__).exception('Analytics query failed: %s', request.url.path)
    return JSONResponse(status_code=503, content={'detail': 'Research data is temporarily unavailable. Please retry shortly.'})


@app.get('/')
def home():
    return {'message': 'DBLP Research Intelligence API running'}
