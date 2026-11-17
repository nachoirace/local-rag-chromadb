"""Ingesta: lee los documentos de data/, los parte en chunks y los guarda en ChromaDB.

    python ingest.py               # indexa sólo si la base está vacía
    python ingest.py --reindexar   # borra lo que hay y vuelve a indexar
"""

import argparse
import logging
from pathlib import Path

import chromadb
import tiktoken
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path(__file__).parent / "data"
VECTORSTORE_DIR = str(Path(__file__).parent / "vectorstore")
COLLECTION_NAME = "turnito_docs"
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 500  # en tokens
CHUNK_OVERLAP = 50

logger = logging.getLogger("rag")
encoding = tiktoken.get_encoding("cl100k_base")  # mismo tokenizer que usa text-embedding-3-small


def contar_tokens(texto: str) -> int:
    return len(encoding.encode(texto))


def obtener_coleccion(path: str = VECTORSTORE_DIR, embedding_function=None):
    """Abre (o crea) la colección. La usan ingest.py y rag.py, así los dos usan el mismo modelo de embeddings."""
    client = chromadb.PersistentClient(path=path)
    if embedding_function is None:
        embedding_function = OpenAIEmbeddingFunction(model_name=EMBEDDING_MODEL, api_key_env_var="OPENAI_API_KEY")
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        configuration={"hnsw": {"space": "cosine"}},
    )


def cargar_documentos(data_dir: Path = DATA_DIR) -> dict[str, str]:
    archivos = sorted(p for p in data_dir.iterdir() if p.suffix in {".md", ".txt"})
    return {archivo.name: archivo.read_text(encoding="utf-8") for archivo in archivos}


def partir_en_chunks(texto: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=contar_tokens,
        # corto por oraciones: no parte ideas a la mitad y el overlap repite las últimas oraciones del chunk anterior
        separators=[". ", "\n", " ", ""],
        keep_separator="end",
    )
    return splitter.split_text(texto)


def ingestar(coleccion=None, data_dir: Path = DATA_DIR, reindexar: bool = False) -> int:
    """Indexa los documentos y devuelve cuántos chunks guardó (0 si la base ya estaba cargada)."""
    coleccion = coleccion or obtener_coleccion()

    if coleccion.count() > 0:
        if not reindexar:
            logger.info("La base ya tiene %d chunks, no reindexo (usá --reindexar para forzarlo)", coleccion.count())
            return 0
        coleccion.delete(ids=coleccion.get()["ids"])

    ids, chunks, metadatas = [], [], []
    for nombre, texto in cargar_documentos(data_dir).items():
        partes = partir_en_chunks(texto)
        logger.info("%s: %d tokens -> %d chunks", nombre, contar_tokens(texto), len(partes))
        for i, chunk in enumerate(partes, start=1):
            ids.append(f"{nombre}#{i}")
            chunks.append(chunk)
            metadatas.append({"fuente": nombre, "chunk": i, "tokens": contar_tokens(chunk)})

    coleccion.upsert(ids=ids, documents=chunks, metadatas=metadatas)
    logger.info("Guardados %d chunks en la colección '%s'", len(ids), COLLECTION_NAME)
    return len(ids)


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Indexa los documentos de data/ en ChromaDB.")
    parser.add_argument("--reindexar", action="store_true", help="Borra la colección y vuelve a indexar todo.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for ruidoso in ("httpx", "httpx2", "openai", "chromadb"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    ingestar(reindexar=args.reindexar)
