"""Export an existing index to the file format and import such a file through the configured writer(s)."""

import json
from collections.abc import Iterator
from typing import Any

import psycopg
from hdbcli import dbapi
from langchain_core.documents import Document
from writers.base import RunDescriptor, Writer, new_run_id
from writers.file import FileWriter

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE

logger = get_logger(__name__)


def _batches(items: list[Any], size: int) -> Iterator[list[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ----------------------------------------------------------------------------- import


def run_import_file(path: str, writer: Writer, batch_size: int = CHUNKS_BATCH_SIZE) -> RunDescriptor:
    """Stream the chunks of a file-writer JSON through the writer, with the stored vectors and a new run id.

    POC: the file is parsed completely into memory first.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    run_obj: dict[str, Any] = data["run"]
    chunks: list[dict[str, Any]] = data["chunks"]
    if not chunks:
        raise ValueError(f"{path} contains no chunks.")
    dimensions = int(run_obj["dimensions"])
    for i, c in enumerate(chunks):
        if len(c["embedding"]) != dimensions:
            raise ValueError(
                f"chunk {i}: vector has {len(c['embedding'])} dimensions, file says dimensions={dimensions}"
            )
    extra = {k: v for k, v in run_obj.items() if k not in {"run_id", "embedding_model", "dimensions", "sources"}}
    extra["imported_from_run"] = run_obj.get("run_id")
    run = RunDescriptor(
        run_id=new_run_id(),
        embedding_model=run_obj["embedding_model"],
        dimensions=dimensions,
        sources=run_obj.get("sources") or {},
        extra=extra,
    )
    try:
        writer.begin(run)
        for n, batch in enumerate(_batches(chunks, batch_size), start=1):
            docs = [Document(page_content=c["content"], metadata=c["metadata"]) for c in batch]
            writer.write(docs, [c["embedding"] for c in batch])
            logger.info(f"Imported batch {n} with {len(batch)} chunks")
        writer.commit()
    except Exception:
        logger.exception("Error while importing")
        writer.abort()
        raise
    logger.info(f"Imported {len(chunks)} chunks from {path} as run {run.run_id}")
    return run


# ----------------------------------------------------------------------------- export


def _export_to_file(
    run: RunDescriptor, rows: Iterator[list[tuple[str, dict[str, Any], list[float]]]], path: str
) -> None:
    # FileWriter buffers all chunks in memory until commit (POC, acceptable).
    writer = FileWriter(path)
    try:
        writer.begin(run)
        total = 0
        for batch in rows:
            writer.write(
                [Document(page_content=t, metadata=m) for t, m, _ in batch],
                [v for _, _, v in batch],
            )
            total += len(batch)
        writer.commit()
    except Exception:
        writer.abort()
        raise
    logger.info(f"Exported {total} chunks (run {run.run_id}) to {writer.path}")


def export_pgvector(dsn: str, path: str, batch_size: int = CHUNKS_BATCH_SIZE) -> None:
    """Export the current run of a pgvector index."""
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT run_id, table_name, embedding_model, dimensions, sources FROM docs_index_runs WHERE is_current"
        ).fetchone()
        if row is None:
            raise RuntimeError("No current run in docs_index_runs.")
        src_run_id, table, model, dimensions, sources = row
        run = RunDescriptor(
            run_id=new_run_id(),
            embedding_model=model,
            dimensions=dimensions,
            sources=sources,
            extra={"exported_from": {"store": "pgvector", "run_id": src_run_id, "table": table}},
        )

        def rows() -> Iterator[list[tuple[str, dict[str, Any], list[float]]]]:
            # table name comes from our own docs_index_runs row; server-side cursor streams in batches
            with conn.cursor(name="export_cur") as cur:
                cur.itersize = batch_size
                cur.execute(f"SELECT content, metadata, embedding::text FROM {table} ORDER BY id")  # noqa: S608
                while batch := cur.fetchmany(batch_size):
                    yield [(c, m, json.loads(e)) for c, m, e in batch]

        _export_to_file(run, rows(), path)


def _lob_text(value: Any) -> str:
    """hdbcli returns NCLOB columns as LOB objects (read() returns the content); plain str stays as is."""
    if isinstance(value, str):
        return value
    if isinstance(value, dbapi.LOB):
        data = value.read()
        return data.decode("utf-8") if isinstance(data, bytes) else str(data)
    return str(value)


def export_hana(
    conn: dbapi.Connection,
    schema: str,
    table: str,
    embedding_model: str,
    path: str,
    batch_size: int = CHUNKS_BATCH_SIZE,
) -> None:
    """Export all rows of the HANA table (HANA has no run manifest, so sources is empty)."""
    with conn.cursor() as cur:
        cur.execute(f'SELECT "VEC_TEXT", "VEC_META", TO_NVARCHAR("VEC_VECTOR") FROM "{schema}"."{table}"')  # noqa: S608

        def convert(r: tuple[Any, Any, Any]) -> tuple[str, dict[str, Any], list[float]]:
            return _lob_text(r[0]), json.loads(_lob_text(r[1])), json.loads(_lob_text(r[2]))

        first = cur.fetchmany(batch_size)
        if not first:
            raise RuntimeError(f"Table {schema}.{table} is empty.")
        first_rows = [convert(r) for r in first]

        def rows() -> Iterator[list[tuple[str, dict[str, Any], list[float]]]]:
            yield first_rows
            while batch := cur.fetchmany(batch_size):
                yield [convert(r) for r in batch]

        run = RunDescriptor(
            run_id=new_run_id(),
            embedding_model=embedding_model,
            dimensions=len(first_rows[0][2]),
            sources={},
            extra={"exported_from": {"store": "hana", "table": table}},
        )
        _export_to_file(run, rows(), path)
