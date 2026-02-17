import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.documents import Document


def build_vector_db(pdf_path, persist_dir):

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

    os.makedirs(persist_dir, exist_ok=True)

    print("💾 Creating vector store...")

    db = Chroma(
        collection_name="imci_handbook",
        persist_directory=persist_dir,
        embedding_function=FastEmbedEmbeddings()
    )

    db.add_documents(documents)

    print("✅ Vector DB built successfully.")


# -----------------------------
# Execution Block
# -----------------------------
if __name__ == "__main__":
    print("🚀 Script starting...")

    pdf_path = "../data/imci_handbook.pdf"
    persist_dir = "../storage/vector_store"

    build_vector_db(pdf_path, persist_dir)
