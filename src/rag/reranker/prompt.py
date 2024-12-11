RERANKER_PROMPT_TEMPLATE = """
You are an expert in Kubernetes and Kyma.
You are provided with a list of queries and a list of Kyma documents.
Given the queries and documents, your task is to rank the documents based on their relevance to the queries.

<input-documents>
{documents}
</input-documents>

<input-queries>
{queries}
</input-queries>

<your-tasks>
1. Carefully read the queries and documents provided in the input sections.
2. Compare the queries to each document by considering keywords or semantic meaning.
3. Determine a relevance score for each document with respect to the queries (higher score means more relevant).
4. Avoid documents that are irrelevant to the queries with very low relevance scores.
</your-tasks>

<additional-rules>
1. Do not make up or invent any new documents. Only use the documents from the provided ranking.
2. Use the documents and your expertise to decide what to keep, how to rank, and which documents to remove.
3. Order the documents based on their relevance score to the queries (top document is the most relevant).
4. Restrict the output to the top {limit} most relevant documents to the queries.
</additional-rules>
"""
