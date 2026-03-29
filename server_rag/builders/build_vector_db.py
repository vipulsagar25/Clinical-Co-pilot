import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient

# Load .env from project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def build_vector_db(pdf_path):

    print(f"📂 Checking file at: {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"❌ File not found at: {pdf_path}")
        print(f"Current directory: {os.getcwd()}")
        return

    print("📖 Loading PDF...")
    loader = PyPDFLoader(pdf_path)
    pages = loader.load()
    print(f"Loaded {len(pages)} pages.")

    print("✂️ Splitting text...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=80,
        separators=["\n\n", "\n", ".", "?"]
    )

    documents = []

    for page in pages:
        p_num = page.metadata.get("page", 0) + 1
        chunks = splitter.split_text(page.page_content)

        for i, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk.strip(),
                    metadata={
                        "source": "IMCI Handbook",
                        "page_number": p_num,
                        "chunk_id": f"{p_num}_{i}"
                    }
                )
            )

    print(f"Created {len(documents)} chunks.")

    print("🔗 Connecting to Qdrant...")

    QDRANT_URL = os.getenv("QDRANT_URL")
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

    if not QDRANT_URL or not QDRANT_API_KEY:
        print("❌ QDRANT_URL or QDRANT_API_KEY not found in .env file")
        return

    embedding = FastEmbedEmbeddings()

    print("☁️ Uploading to Qdrant...")

    from qdrant_client.models import Distance, VectorParams
    
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
    )
    
    # Create collection if it doesn't exist
    collection_name = "imci_handbook"
    try:
        client.get_collection(collection_name)
        print(f"Collection '{collection_name}' already exists")
    except:
        print(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    
    vectorstore = Qdrant.from_documents(
        documents,
        embedding,
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        collection_name=collection_name,
    )

    print("✅ Vector DB uploaded to Qdrant successfully.")


# -----------------------------
if __name__ == "__main__":
    print("🚀 Script starting...")

    pdf_path = "../data/imci_handbook.pdf"

    build_vector_db(pdf_path)