"""Prueba del RAG: una pregunta que está en los documentos y una pregunta trampa.

    python main.py
    python main.py --pregunta "¿Cuánto tiempo se guardan los logs?"
"""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

from ingest import ingestar
from rag import get_rag_response
from schemas import RespuestaRAG

PREGUNTA_OK = "¿Qué días y en qué horario se pueden hacer deploys a producción?"
PREGUNTA_TRAMPA = "¿Cuál es el presupuesto anual de marketing de Turnito?"


def mostrar(pregunta: str, r: RespuestaRAG) -> None:
    print(f"\nPregunta: {pregunta}")
    print(f"Respuesta: {r.respuesta}")
    print(f"Referencias: {', '.join(r.referencias) or '-'}")


async def main(pregunta: str | None) -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("Falta OPENAI_API_KEY. Copiá .env.example a .env y poné tu key.")
        return 1

    ingestar()  # si la base ya existe no vuelve a indexar

    if pregunta:
        mostrar(pregunta, await get_rag_response(pregunta))
        return 0

    print("\n=== Prueba 1: la respuesta está en los documentos ===")
    r1 = await get_rag_response(PREGUNTA_OK)
    mostrar(PREGUNTA_OK, r1)
    print("✓ Respondió con referencias" if r1.encontrada and r1.referencias else "✗ Esperaba una respuesta con referencias")

    print("\n=== Prueba 2: pregunta trampa (no está en los documentos) ===")
    r2 = await get_rag_response(PREGUNTA_TRAMPA)
    mostrar(PREGUNTA_TRAMPA, r2)
    print("✓ No alucinó: dijo que no lo sabe" if not r2.encontrada else "✗ Respondió algo que no está en los documentos")

    return 0 if (r1.encontrada and not r2.encontrada) else 1


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description="Prueba el sistema RAG.")
    parser.add_argument("--pregunta", help="Hace esta pregunta en vez de las dos pruebas.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for ruidoso in ("httpx", "httpx2", "openai", "chromadb", "langchain_openai"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)

    sys.exit(asyncio.run(main(args.pregunta)))
