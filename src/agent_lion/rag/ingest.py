from pathlib import Path

import chromadb
from dotenv import load_dotenv
from llama_index.core import SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

# set file paths for vector database and crawled markdown files
DB_NAME = str(Path(__file__).parent.parent.parent.parent / "vector_db")
KNOWLEDGE_BASE = str(Path(__file__).parent.parent.parent.parent / "crawled_md_files")

load_dotenv(override=True)

# set the embedding model to use for creating vector embeddings of the documents
embeddings = OpenAIEmbedding(model="text-embedding-3-large")

def fetch_documents():
    """Load documents from the knowledge base directory."""
    documents = SimpleDirectoryReader(KNOWLEDGE_BASE).load_data()
    return documents

def create_embeddings(loaded_documents):
    """Create vector embeddings for the loaded documents and store them in the Chroma vector database."""

    # connect to the Chroma vector database
    db = chromadb.PersistentClient(path=DB_NAME)

    # get or create the Chroma collection
    chroma_collection = db.get_or_create_collection("agent_lion_collection")

    # connect Chroma to the LlamaIndex vector store
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # create the vector index using the documents and embedding model
    index = VectorStoreIndex.from_documents(loaded_documents, storage_context=storage_context, embed_model=embeddings)

    # display the number of vectors in the vector store
    count = chroma_collection.count()
    print(f"There are {count:,} vectors in the vector store.")

    return index

if __name__ == "__main__":
    documents = fetch_documents()
    create_embeddings(documents)

    print("Ingestion complete")