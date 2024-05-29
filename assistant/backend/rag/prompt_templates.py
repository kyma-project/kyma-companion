PROMPT_TEMPLATE_HYDE = """
You are Kubernetes AI assistant which helps users with cluster issue resolution and analysis. You are also Kyma expert.  
Kyma is an opinionated set of Kubernetes-based modular building blocks, including all necessary capabilities to develop
and run enterprise-grade cloud-native applications.

<context>
{context}
</context>

<question>
{question}
</question>

Please write a short documentation for the question and the resource content. Use Kyma specific terminology.
Use recent data. Limit the response to 200 words.
"""

PROMPT_TEMPLATE_MULT_QUERY = """
You are AI language model assistant for Kubernetes and Kyma. Kyma is an opinionated 
set of Kubernetes-based modular building blocks, including all necessary capabilities to develop and run 
enterprise-grade cloud-native applications.

<context>
{context}
</context>

<question>
{question}
</question>

Your task is to generate four different versions of the given user question based on the context to retrieve relevant 
documents from a vector database. By generating multiple perspectives on the user question, your goal is to help the 
user overcome some of the limitations of the distance-based similarity search. Provide these alternative questions 
separated by newlines. Only provide the query, no numbering.
"""

RERANKER_PROMT_TEMPLATE = """You are expert in Kubernetes and Kyma and are tasked with finding the most relevant Kyma 
documentation. Below, you find the Kyma documentations that have been retrieved to answer a question. These Kyma 
documents are ordered according to how relevant an imperfect semantic retrieval system determined them to be to 
the given user question.

<documents>
{retrieved_docs}
</documents>

<question> 
{query}
</question>

<your-tasks>
1. Carefully read the question and the documents.
2. Compare the question to each doc by considering keyword(s) or semantic meaning and determine
 a relevance score for each between 1 and 10.
3. If a document is relevant to the question, return them in the order of relevance.
In order to do this, carefully read and compare the question to the documents and use your expert knowledge
from Kyma and Kubernetes.
</your-tasks>

<additional-rules>
Please output a list of the most relevant Kyma documents given the above user question closely following these rules:
1. Do not make up or invent any new documents. Only use the documents from the provided ranking.
2. Use the documents and your expertise to decide what to keep, how to rank, and which documents to remove.
3. Restrict the output to the most top 2-3 relevant documents.
4. Response must contain the complete documents that are in fact relevant to the question
5. Provide a response in a structured XML format that matches the following format: "<documents><document>...<document>
</documents>"
</additional-rules>

The Kyma documents most relevant to the question sorted by perceived relevance are: 
"""