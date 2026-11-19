from pathlib import Path

import chromadb
from dotenv import load_dotenv
from langchain_core.documents import Document
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.indices.vector_store import VectorIndexRetriever
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

load_dotenv(override=True)

# set file path for the vector database
DB_NAME = str(Path(__file__).parent.parent.parent.parent / "vector_db")

# set the embedding model and number of top-matching chunks to retrieve for a given question
embeddings = OpenAIEmbedding(model="text-embedding-3-large")
RETRIEVAL_K = 10

# connect to the Chroma vector database
db = chromadb.PersistentClient(path=DB_NAME)

# get or create the Chroma collection
chroma_collection = db.get_or_create_collection("agent_lion_collection")

# connect Chroma to the LlamaIndex vector store
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)

# load the existing vector index from the Chroma vector store
index = VectorStoreIndex.from_vector_store(vector_store, storage_context=storage_context, embed_model=embeddings)

# create a retriever to fetch relevant context documents for a given question
retriever = VectorIndexRetriever(index=index, similarity_top_k=RETRIEVAL_K)

def fetch_context(question: str) -> list[Document]:
    """Retrieve relevant context documents for a question."""
    nodes = retriever.retrieve(question)

    return [Document(page_content=node.node.text) for node in nodes]