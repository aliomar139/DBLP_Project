# DBLP Analytics Platform - Technical Report

## 1. Project Overview

This project builds a research analytics platform on top of the DBLP
computer science bibliography dataset.

The objective is to transform the raw DBLP XML dump into a structured
analytical database that supports:

-   Interactive dashboards
-   Research trend analysis
-   Author and venue exploration
-   Collaboration network visualization
-   Future machine learning applications

The system is designed as a data platform rather than only a
visualization project, leaving room for future capabilities such as:

-   Paper embeddings
-   Semantic search
-   Recommendation systems
-   Graph machine learning
-   Research intelligence tools

# 2. Final Architecture

The current architecture is:

    DBLP XML
        |
        |
    Python ETL Pipeline
        |
        |
    DuckDB Analytical Warehouse
        |
        |
    FastAPI Backend
        |
        |
    React + TypeScript Dashboard

The XML parsing and database creation stages are complete.

# 3. Why DuckDB Was Chosen

Initially, SQLite was considered because it is simple and lightweight.
However, the project requirements evolved toward:

-   Large-scale analytics
-   Dashboard queries
-   Machine learning preparation
-   Graph analysis

DuckDB was selected because it is optimized for analytical workloads.

Advantages:

-   Columnar analytical execution
-   Extremely fast aggregations
-   Native Python integration
-   Runs locally without server setup
-   Works well with Pandas, Arrow, and ML workflows
-   Suitable for large datasets on a personal machine

# 4. Hardware Optimization

The pipeline was optimized for:

-   Intel i5-1245U
-   40 GB RAM
-   NVMe SSD

DuckDB configuration:

-   Memory limit: 25 GB
-   Threads: 10

The remaining RAM is intentionally left available for the operating
system and development tools.

# 5. Final ETL Pipeline

## Current Parser Version

The final parser is the V4 pipeline.

The pipeline performs:

1.  Streaming XML parsing using lxml.iterparse
2.  Fast batch ingestion using PyArrow + DuckDB
3.  Raw data storage
4.  SQL-based normalization

## Why this design was chosen

Earlier approaches normalized data during XML parsing.

That was slower because Python handled:

-   Author deduplication
-   Relationship creation
-   Venue lookup

The final approach lets Python only extract data while DuckDB performs
analytical transformations.

This resulted in:

-   8,738,331 publications processed
-   Runtime: approximately 4.5 minutes

# 6. Database Schema

## Core Tables

## raw_publications

Stores the extracted DBLP information:

-   id
-   publication type
-   DBLP key
-   title
-   year
-   venue
-   authors

## publications

Normalized publication table:

-   publication_id
-   DBLP key
-   type
-   title
-   year
-   venue_id

## authors

Researcher entity table:

-   author_id
-   name

## venues

Publication venues:

-   venue_id
-   name

## publication_authors

Many-to-many relationship:

-   publication_id
-   author_id

# 7. Analytics Layer

## publication_year_stats

Used for:

-   Publication growth charts
-   Timeline visualization

## author_stats

Used for:

-   Top researchers
-   Author ranking

## venue_stats

Used for:

-   Conference/journal ranking

## author_collaboration

Graph representation:

-   author1
-   author2
-   collaboration weight

Current size:

-   approximately 32.5 million edges

## Dashboard graph tables

Created specifically for visualization:

-   top_authors
-   author_collaboration_dashboard
-   author_collaboration_dashboard_named

# 8. Data Validation

Final database statistics:

Publications: 8,738,331

Authors: 4,301,538

Venues: 21,224

The author extraction issue was fixed by:

-   Using author.itertext()
-   Using a safe delimiter
-   Rebuilding normalized author tables

# 9. Backend Design

The backend will use FastAPI.

Responsibilities:

-   Connect to DuckDB
-   Serve dashboard data
-   Provide JSON APIs

Planned endpoints:

GET /api/overview

GET /api/publications/timeline

GET /api/authors/top

GET /api/venues/top

GET /api/collaboration

# 10. Frontend Design

The dashboard will use:

-   React
-   TypeScript
-   Recharts
-   D3.js

Planned views:

## Overview Dashboard

Displays:

-   Total publications
-   Total authors
-   Total venues
-   Research growth

## Research Trends

Displays:

-   Publication timeline
-   Venue trends

## Author Explorer

Displays:

-   Researcher profiles
-   Publication history
-   Collaborators

## Collaboration Network

Displays:

-   Interactive researcher graph

# 11. Future ML Extensions

The current design intentionally supports ML.

Possible additions:

## Paper embeddings

Store vector representations of papers for:

-   Semantic search
-   Similar paper recommendation

## Author embeddings

Represent researchers using:

-   Publication history
-   Collaboration network

## Graph ML

Use:

-   Collaboration graph
-   Author networks

for:

-   Community detection
-   Link prediction
-   Research recommendation

# Conclusion

The project has successfully completed the hardest stage: building a
scalable DBLP data platform.

The next stage is application development: FastAPI backend followed by
React dashboard implementation.
