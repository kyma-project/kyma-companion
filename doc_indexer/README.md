# Kyma Documentation Indexer

Kyma Documentation Indexer
This project implements a documentation indexing system for Kyma that stores the indexed content in SAP HANA Cloud DB. 
The system processes Markdown files, splits them into meaningful chunks based on headers, and creates searchable vector embeddings.

## Concepts
The indexer splits the documentation content into chunks based on the provided headers and creates vector embeddings for each chunk. 
It uses GPT embedding models to create the embeddings. 
The embeddings are stored in SAP HANA Cloud DB, which allows for fast and efficient search queries.

## Development

To run the project locally, follow these steps:

1. Install the dependencies:

```bash
poetry install
```

2. Prepare the `config-doc-indexer.json` file based on the [template](../config/config-example.json).

3. Run the fetcher to pull documents from the specified sources in the `docs_sources.json` [file](./docs_sources.json):

```bash
poetry run python src/main.py fetch
```

4. Run the indexer to create embeddings for the fetched documents:
```bash
poetry run python src/main.py index
```

## Writers

`DOCS_WRITER` selects where `index` writes (`src/writers/`):

| Writer | Setting | Behaviour |
|---|---|---|
| `hana` (default) | `DATABASE_*` | Deletes all rows and adds the chunks; HanaDB embeds. Unchanged. |
| `pgvector` | `DOCS_SEARCH_PG_DSN` | Embeds the chunks itself and writes one table `docs_chunks_<run_id>` per run, tracked in `docs_index_runs`. `commit()` flips `is_current`; the last 2 committed runs are kept. Layout: `kyma-docs-search/docs/poc-contract.md`. |
| `file` | `INDEX_TO_FILE=true` (or `DOCS_WRITER=file`) | JSON file `{"run": ..., "chunks": [{content, metadata, embedding}]}`. Path: `DOCS_FILE_PATH` (default `kyma_docs_{run_id}.json`, `{run_id}` is substituted). |

`DOCS_WRITER` accepts a comma-separated list, e.g. `pgvector,file`: all writers get the same run and the chunks are embedded once. If one commit fails, the writers not yet committed are aborted and the error is raised (already committed ones stay).

Demo (local Postgres with pgvector, see the contract):

```bash
export CONFIG_PATH=../config/config.json DOCS_SOURCES_FILE_PATH=./e2e_docs_sources.json DOCS_PATH=./data \
  DOCS_WRITER=pgvector DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs
poetry run python src/main.py fetch
poetry run python src/main.py index
```

## Run summary

After every `index` run a markdown summary is rendered (`src/utils/summary.py`): a header with run id, writer(s), embedding model and dimensions, total chunks and duration, a table per module (chunks, delta vs the previous run, commit linked to `<repo url>/commit/<sha>`), and a warnings line (modules with zero chunks, modules present in the previous run but missing now). Deltas are only known for the `pgvector` writer (the previous current run is read before the flip); otherwise they show `n/a`.

| Output | Behaviour |
|---|---|
| log | Always, one multi-line INFO message at the end of `index`. |
| `DOCS_SUMMARY_PATH` | If set (default empty), the summary is written to this file (overwritten). |
| `GITHUB_STEP_SUMMARY` | If this environment variable is set (GitHub Actions does), the summary is appended to that file and shows as the job summary. |

The pgvector writer also stores the statistics as JSON in the column `docs_index_runs.report jsonb` (added with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, NULL for older runs and runs written by other tools). Shape:

```json
{"run_id": "...", "writers": ["pgvector"], "embedding_model": "...", "dimensions": 3072,
 "total_chunks": 11, "duration_seconds": 5.2,
 "modules": {"<module>": <chunk count>},
 "sources": {"<module>": {"repo_url": "...", "commit": "..."}},
 "previous": {"run_id": "...", "total_chunks": 11, "modules": {"<module>": <count>}} }
```

`previous` is `null` when there was no current run before.

## Export and import

Export is a convenience for developers: clone an existing index (for example the one on HANA) into a local Postgres without paying for the embeddings again.

```bash
# export the CURRENT index to a file (run object + chunks with vectors)
export DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs
poetry run python src/main.py export --from pgvector --file kyma_docs.json
CONFIG_PATH=../config/config.json poetry run python src/main.py export --from hana --file kyma_docs.json  # DATABASE_*, DOCS_TABLE_NAME

# import a file through the configured writer(s) as a NEW run (new run_id, stored vectors, no embedding, no sleep)
DOCS_WRITER=pgvector poetry run python src/main.py import --file kyma_docs.json
```

Round trip pgvector -> file -> pgvector: run the first export command, then the import with `DOCS_WRITER=pgvector`; `docs_index_runs` then has a second run with the same `chunk_count`, which is current.

HANA -> local pgvector: run the HANA export, then import with `DOCS_WRITER=pgvector DOCS_SEARCH_PG_DSN=postgres://postgres:postgres@localhost:5433/docs`. HANA has no manifest, so `sources` is `{}`; the file run object carries `exported_from`. The import fails early if any vector length differs from `dimensions`. Importing with `DOCS_WRITER=hana` deletes the table content first and writes the stored vectors (`HanaDB.add_texts(embeddings=...)`).

Memory: the file writer and the import keep the whole file in memory (POC).

## Testing

The `config.json` file must be present for integration tests (see [template](../config/config-example.json)).

### Test structure

| Layer | Location | Description |
|---|---|---|
| Unit | `tests/unit/` | Fast tests with no external dependencies. All external calls are mocked. |
| Integration | `tests/integration/` | Tests that make real API calls to the embedding service and SAP AI Core, including a full end-to-end test that writes to a temporary Hana DB table. |

A missing config is a hard failure — there are no silent skips.

In CI, the e2e table is named `kc_pr_<PR number>_e2e` so orphaned tables can be traced back to the PR that created them. Locally a UUID is used (`test_e2e_<uuid>_e2e`).

### Running tests

Run unit tests:
```bash
poetry run poe test-unit
```

Run integration tests:
```bash
poetry run poe test-integration
```

Run all tests:
```bash
poetry run poe test
```

### Key regression tests

- **`tests/unit/test_main.py::test_run_indexer_passes_model_name_not_deployment_id`** — verifies that `run_indexer()` passes the model name (not the deployment ID) to the embedding factory.
- **`tests/integration/test_main.py::test_run_indexer_embedding_model_creation`** — positive check: model creation via the exact production sequence produces a working embeddings model.
- **`tests/integration/test_main.py::test_run_indexer_fails_when_deployment_id_passed_as_model_name`** — negative check: passing a deployment ID instead of a model name raises `ValueError`.
- **`tests/integration/test_main.py::test_run_indexer_e2e`** — full end-to-end: indexes real documents into a temporary Hana DB table and verifies chunks were stored.

## Static Code Analysis
```bash
poetry run poe codecheck
```

## CI drafts

`ci/index-docs.yaml` is a draft of the scheduled indexing workflow for an internal repo (Vault via OIDC, one landscape at a time, run summary and artifacts). `ci/probe-runner.yaml` is the one-off phase-0 check for OIDC, Python and PyPI on github.tools.sap runners. Neither runs from this repository.
