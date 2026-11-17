"""Cadena RAG: busca los fragmentos más parecidos en ChromaDB y responde sólo con esa información."""

import asyncio
import logging
import os
from functools import cache
from operator import itemgetter

from langchain_core.exceptions import (
    ModelAPIError,
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
    OutputParserException,
)
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_openai import ChatOpenAI

from ingest import obtener_coleccion
from schemas import NO_LO_SE, RespuestaRAG

logger = logging.getLogger("rag")

TOP_K = 4  # entre 3 y 5: más fragmentos meten ruido y gastan tokens

SYSTEM_PROMPT = """Sos un asistente técnico del equipo de ingeniería de Turnito.
Respondé ÚNICAMENTE con la información del CONTEXTO que te paso.

Reglas:
- Si la respuesta no está en el CONTEXTO, respondé exactamente "{no_lo_se}" y dejá las referencias vacías.
- No uses conocimiento propio ni completes con suposiciones, aunque la pregunta parezca fácil.
- En las referencias poné la fuente (lo que está entre corchetes) de cada fragmento que usaste.
- Respondé en español, de forma breve y concreta.

{format_instructions}"""

HUMAN_PROMPT = """CONTEXTO:
{contexto}

PREGUNTA: {pregunta}"""


def crear_modelo() -> ChatOpenAI:
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), temperature=0)


def formatear_contexto(fragmentos: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{f['id']}]\n{f['texto']}" for f in fragmentos)


def crear_cadena(coleccion, modelo, top_k: int = TOP_K):
    parser = PydanticOutputParser(pydantic_object=RespuestaRAG)
    prompt = ChatPromptTemplate.from_messages(
        [("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)]
    ).partial(no_lo_se=NO_LO_SE, format_instructions=parser.get_format_instructions())

    async def buscar(pregunta: str) -> list[dict]:
        # Chroma convierte la pregunta en embedding con la misma función de la colección
        # (text-embedding-3-small) y devuelve los top_k chunks más cercanos por coseno.
        # chromadb es sincrónico, lo corro en otro thread para no bloquear el event loop
        res = await asyncio.to_thread(coleccion.query, query_texts=[pregunta], n_results=top_k)
        fragmentos = [
            {"id": id_, "texto": texto, "distancia": round(distancia, 3)}
            for id_, texto, distancia in zip(res["ids"][0], res["documents"][0], res["distances"][0])
        ]
        logger.info("Recuperados: %s", ", ".join(f"{f['id']} ({f['distancia']})" for f in fragmentos))
        return fragmentos

    generar = (
        {"contexto": lambda x: formatear_contexto(x["fragmentos"]), "pregunta": itemgetter("pregunta")}
        | prompt
        | modelo
        | parser
    ).with_retry(
        retry_if_exception_type=(
            OutputParserException,  # el modelo no devolvió el JSON bien
            ModelConnectionError,
            ModelTimeoutError,
            ModelRateLimitError,
            ModelAPIError,
        ),
        stop_after_attempt=3,
    )

    # devuelvo los fragmentos junto con la respuesta, para poder chequear las referencias
    return RunnableParallel(
        fragmentos=RunnableLambda(buscar), pregunta=RunnablePassthrough()
    ) | RunnablePassthrough.assign(respuesta=generar)


@cache
def cadena_por_defecto():
    return crear_cadena(obtener_coleccion(), crear_modelo())


async def get_rag_response(query: str, cadena=None) -> RespuestaRAG:
    """Busca en ChromaDB, arma el prompt con los fragmentos, llama al LLM y parsea la respuesta."""
    cadena = cadena or cadena_por_defecto()
    resultado = await cadena.ainvoke(query)
    respuesta: RespuestaRAG = resultado["respuesta"]

    # me quedo sólo con referencias a fragmentos que realmente se recuperaron
    recuperados = {f["id"] for f in resultado["fragmentos"]}
    referencias = [r for r in respuesta.referencias if r in recuperados] if respuesta.encontrada else []
    if len(referencias) != len(respuesta.referencias):
        logger.warning("Descarto referencias que no estaban en el contexto: %s", set(respuesta.referencias) - set(referencias))

    return respuesta.model_copy(update={"referencias": referencias})
