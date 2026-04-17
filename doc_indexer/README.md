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

