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

## Indexing a separate table (ops / SRE docs)

The pipeline is fully driven by environment variables, so a second corpus can
be indexed into its own HANA table without code changes by pointing the fetch
and index tasks at a different sources file and table name.

The repository ships [`ops_docs_sources.json`](./ops_docs_sources.json), which
indexes internal operations/SRE docs (SRE runbooks, on-call guides, Gardener,
orchestration-operator, kubeconfig-service) into the `ops_docs` table:

```bash
DOCS_SOURCES_FILE_PATH=./ops_docs_sources.json \
DOCS_PATH=./data-ops \
DOCS_TABLE_NAME=ops_docs \
  poetry run python src/main.py fetch

DOCS_SOURCES_FILE_PATH=./ops_docs_sources.json \
DOCS_PATH=./data-ops \
DOCS_TABLE_NAME=ops_docs \
  poetry run python src/main.py index
```

Each source entry may set:

- `audience` (list, default `["public"]`) — surfaced as chunk metadata so a
  consumer can filter internal vs. public docs. Ops sources use `["internal"]`.
- `doc_type` (string, optional) — free-form classification such as `runbook`,
  `on-call-guide`, or `operator-docs`.

### Private / GitHub Enterprise sources

Most ops sources live on SAP's internal GitHub Enterprise
(`github.tools.sap`). The fetcher is public-only by default; to reach the
enterprise host set:

- `GITHUB_ENTERPRISE_HOST` — e.g. `github.tools.sap`. Only this host (plus
  public `github.com`) is allow-listed as a document source.
- `GITHUB_TOKEN` — a token with read access to the private repos. It is sent
  as a bearer token **only** to the configured enterprise host.

Enterprise archives are fetched from the GHE REST API tarball endpoint
(`/api/v3/repos/<owner>/<repo>/tarball/<ref>`). The commit sha is read from the
archive's pax header when present, falling back to the trailing sha in the
top-level directory name.

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
