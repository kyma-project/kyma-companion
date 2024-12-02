from langchain_core.documents import Document

# Document objects
doc1 = Document(page_content="doc1")
doc2 = Document(page_content="doc2")
doc3 = Document(page_content="doc3")
doc4 = Document(page_content="doc4")
doc5 = Document(page_content="doc5")
doc6 = Document(page_content="doc6")
doc7 = Document(page_content="doc7")
doc8 = Document(page_content="doc8")
doc9 = Document(page_content="doc9")

# JSON representations of Document objects
doc1_json = '{"kwargs": {"page_content": "doc1"}}'
doc2_json = '{"kwargs": {"page_content": "doc2"}}'
doc3_json = '{"kwargs": {"page_content": "doc3"}}'
doc4_json = '{"kwargs": {"page_content": "doc4"}}'
doc5_json = '{"kwargs": {"page_content": "doc5"}}'
doc6_json = '{"kwargs": {"page_content": "doc6"}}'
doc7_json = '{"kwargs": {"page_content": "doc7"}}'
doc8_json = '{"kwargs": {"page_content": "doc8"}}'
doc9_json = '{"kwargs": {"page_content": "doc9"}}'

# Dictionary mapping Document objects to their JSON representations
doc_to_json = {
    doc1.page_content: doc1_json,
    doc2.page_content: doc2_json,
    doc3.page_content: doc3_json,
    doc4.page_content: doc4_json,
    doc5.page_content: doc5_json,
    doc6.page_content: doc6_json,
    doc7.page_content: doc7_json,
    doc8.page_content: doc8_json,
    doc9.page_content: doc9_json,
}
