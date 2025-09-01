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

---

### Running with Docker

You can also run the project inside a Docker container to simplify environment setup.

1. **Build the Docker image**:

```bash
docker build -t doc-indexer .
```

2. **Run the container**:

Make sure you mount your local `config` and `data` folders into the container. Replace `<path-to-config>` and `<path-to-data>` with the absolute paths on your machine:

```bash
docker run -v <path-to-config>:/config -v <path-to-data>:/app/data doc-indexer -- fetch
```

or

```bash
docker run -v <path-to-config>:/config -v <path-to-data>:/app/data doc-indexer -- index
```

> The `--` separates Docker options from arguments passed to your Python script. Use `fetch` to fetch documents or `index` to index them.



## Testing

The `config-doc-indexer.json` file can also be used for testing.
To run the unit and integration tests, use the following command:

```bash
poetry run poe test
```

To run the unit tests, use the following command:

```bash
poetry run poe test-unit
```

To run the integration tests, use the following command:

```bash
poetry run poe test-integration
```

## Static Code Analysis
```bash
poetry run poe codecheck
```
