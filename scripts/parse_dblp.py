import time
import duckdb
import pyarrow as pa
from lxml import etree
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

XML_FILE = BASE_DIR / "data" / "dblp.xml"
DB_FILE = BASE_DIR / "database" / "dblp.duckdb"
LOG_FILE = BASE_DIR / "logs" / "parse.log"


# ============================================================
# SETTINGS
# ============================================================

MEMORY_LIMIT = "25GB"
THREADS = 10

BATCH_SIZE = 1_000_000


PUB_TYPES = {
    "article",
    "inproceedings",
    "proceedings",
    "book",
    "incollection",
    "phdthesis",
    "mastersthesis"
}


# ============================================================
# LOG
# ============================================================

def log(msg):

    print(msg)

    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as f:
        f.write(str(msg) + "\n")


# ============================================================
# CHECKS
# ============================================================

if DB_FILE.exists():

    raise Exception(
        "Database already exists. Delete it before rebuilding."
    )


DB_FILE.parent.mkdir(exist_ok=True)
LOG_FILE.parent.mkdir(exist_ok=True)


# ============================================================
# DUCKDB
# ============================================================

conn = duckdb.connect(
    str(DB_FILE)
)


conn.execute(
    f"SET memory_limit='{MEMORY_LIMIT}'"
)

conn.execute(
    f"SET threads={THREADS}"
)


log("=" * 70)
log("DBLP V4 PIPELINE (AUTHOR FIX)")
log("=" * 70)


# ============================================================
# RAW TABLE
# ============================================================

conn.execute("""
CREATE TABLE raw_publications(

    id BIGINT,
    type VARCHAR,
    db_key VARCHAR,
    title VARCHAR,
    year INTEGER,
    venue VARCHAR,
    authors VARCHAR

)
""")


# ============================================================
# XML PARSER
# ============================================================

context = etree.iterparse(
    str(XML_FILE),
    events=("end",),
    tag=PUB_TYPES,
    load_dtd=False,
    resolve_entities=False,
    no_network=True
)


ids = []
types = []
keys = []
titles = []
years = []
venues = []
authors = []


count = 0

start = time.time()


def flush():

    global ids, types, keys
    global titles, years
    global venues, authors


    if not ids:
        return


    table = pa.table(
        {
            "id": ids,
            "type": types,
            "db_key": keys,
            "title": titles,
            "year": years,
            "venue": venues,
            "authors": authors
        }
    )


    conn.register(
        "batch",
        table
    )


    conn.execute("""
        INSERT INTO raw_publications
        SELECT *
        FROM batch
    """)


    conn.unregister(
        "batch"
    )


    ids.clear()
    types.clear()
    keys.clear()
    titles.clear()
    years.clear()
    venues.clear()
    authors.clear()



# ============================================================
# PARSE
# ============================================================

log("Starting XML parsing...")


for _, elem in context:


    pub_type = elem.tag


    key = elem.get(
        "key",
        ""
    )


    title = elem.findtext(
        "title"
    ) or ""


    title = " ".join(
        title.split()
    )


    year_text = elem.findtext(
        "year"
    )


    year = None

    if year_text and year_text.isdigit():

        year = int(year_text)



    venue = (
        elem.findtext("journal")
        or
        elem.findtext("booktitle")
        or
        ""
    ).strip()



    # =========================
    # FIXED AUTHOR EXTRACTION
    # =========================

    author_names = []

    for author in elem.findall("author"):

        name = "".join(
            author.itertext()
        ).strip()


        if name:

            author_names.append(name)



    author_string = "|||".join(
        author_names
    )


    # =========================


    count += 1


    ids.append(count)
    types.append(pub_type)
    keys.append(key)
    titles.append(title)
    years.append(year)
    venues.append(venue)
    authors.append(author_string)



    if len(ids) >= BATCH_SIZE:


        flush()


        elapsed = time.time() - start


        log(
f"""
Processed:
{count:,}

Time:
{elapsed/60:.2f} min
"""
        )



    elem.clear()


    while elem.getprevious() is not None:

        del elem.getparent()[0]



flush()


log("Raw import finished")


# ============================================================
# NORMALIZATION
# ============================================================


log("Building normalized tables...")


conn.execute("""
CREATE TABLE venues AS

SELECT

row_number() OVER() AS venue_id,

venue AS name

FROM
(
SELECT DISTINCT venue
FROM raw_publications
WHERE venue <> ''
)

""")


conn.execute("""
CREATE TABLE publications AS

SELECT

r.id AS publication_id,

r.db_key,

r.type,

r.title,

r.year,

v.venue_id


FROM raw_publications r

LEFT JOIN venues v

ON r.venue=v.name

""")


conn.execute("""
CREATE TABLE authors AS

WITH exploded AS (

SELECT

unnest(
string_split(authors,'|||')
)

AS name


FROM raw_publications

)


SELECT

row_number() OVER()
AS author_id,


trim(name)
AS name


FROM

(
SELECT DISTINCT name
FROM exploded
WHERE trim(name)<>''
)

""")


conn.execute("""
CREATE TABLE publication_authors AS


WITH exploded AS (

SELECT

id,

unnest(
string_split(authors,'|||')
)

AS author_name


FROM raw_publications

)


SELECT

p.publication_id,

a.author_id


FROM exploded e


JOIN publications p

ON e.id=p.publication_id


JOIN authors a

ON trim(e.author_name)=a.name

""")


# ============================================================
# DASHBOARD TABLES
# ============================================================

log("Creating dashboard tables...")


conn.execute("""
CREATE TABLE publication_year_stats AS

SELECT

year,

COUNT(*) AS publication_count


FROM publications

WHERE year IS NOT NULL

GROUP BY year

ORDER BY year

""")


conn.execute("""
CREATE TABLE author_stats AS

SELECT

a.author_id,

a.name,

COUNT(*) AS publication_count


FROM authors a

JOIN publication_authors pa

ON a.author_id=pa.author_id


GROUP BY

a.author_id,

a.name


ORDER BY publication_count DESC

""")


conn.execute("""
CREATE TABLE venue_stats AS

SELECT

v.name,

COUNT(*) AS publication_count


FROM venues v

JOIN publications p

ON v.venue_id=p.venue_id


GROUP BY v.name

ORDER BY publication_count DESC

""")


conn.close()


elapsed = time.time()-start


log(
f"""
============================

DONE

Publications:
{count:,}

Runtime:
{elapsed/60:.2f} minutes

Database:
{DB_FILE}

============================
"""
)