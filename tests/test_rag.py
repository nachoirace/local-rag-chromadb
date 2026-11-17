"""Tests sin red: embeddings de prueba (trigramas) en vez de OpenAI y un chat model falso de LangChain."""

import hashlib
import json

import numpy as np
import pytest
from chromadb.api.types import Documents, EmbeddingFunction
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from ingest import CHUNK_SIZE, cargar_documentos, contar_tokens, ingestar, obtener_coleccion, partir_en_chunks
from rag import crear_cadena, get_rag_response
from schemas import NO_LO_SE, RespuestaRAG


class EmbeddingDePrueba(EmbeddingFunction):
    """Vector de trigramas de caracteres: textos que comparten palabras quedan cerca."""

    def __init__(self):
        pass

    def __call__(self, input: Documents):
        vectores = []
        for texto in input:
            v = np.zeros(512, dtype=np.float32)
            t = f"  {texto.lower()} "
            for i in range(len(t) - 2):
                v[int(hashlib.md5(t[i : i + 3].encode()).hexdigest(), 16) % 512] += 1
            vectores.append(v / (np.linalg.norm(v) or 1))
        return vectores

    @staticmethod
    def name():
        return "prueba-trigramas"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return EmbeddingDePrueba()


@pytest.fixture
def coleccion(tmp_path):
    col = obtener_coleccion(path=str(tmp_path / "vectorstore"), embedding_function=EmbeddingDePrueba())
    ingestar(col)
    return col


def modelo_falso(*respuestas: dict | str) -> FakeListChatModel:
    return FakeListChatModel(responses=[r if isinstance(r, str) else json.dumps(r, ensure_ascii=False) for r in respuestas])


# --- Ingesta -----------------------------------------------------------------


def test_chunks_respetan_el_tamanio_en_tokens():
    for texto in cargar_documentos().values():
        chunks = partir_en_chunks(texto)
        assert len(chunks) >= 2
        assert all(contar_tokens(c) <= CHUNK_SIZE + 5 for c in chunks)  # +5: el conteo por partes puede variar 1 o 2


def hay_overlap(a: str, b: str) -> bool:
    return any(a.endswith(b[:k]) for k in range(20, len(b)))  # el final de a se repite al principio de b


def test_overlap_entre_chunks():
    texto = " ".join(f"Oración número {i} del documento." for i in range(400))
    a, b = partir_en_chunks(texto)[:2]
    assert hay_overlap(a, b)


def test_overlap_en_el_dataset():
    pares = [
        (a, b)
        for texto in cargar_documentos().values()
        for a, b in zip(partir_en_chunks(texto), partir_en_chunks(texto)[1:])
    ]
    assert sum(hay_overlap(a, b) for a, b in pares) >= len(pares) // 2


def test_ingesta_guarda_chunks_con_metadata(coleccion):
    datos = coleccion.get(include=["metadatas"])
    assert coleccion.count() == sum(len(partir_en_chunks(t)) for t in cargar_documentos().values())
    assert "deploys.md#1" in datos["ids"]
    assert {m["fuente"] for m in datos["metadatas"]} == set(cargar_documentos())


def test_no_reindexa_si_la_base_ya_existe(coleccion):
    total = coleccion.count()
    assert ingestar(coleccion) == 0
    assert ingestar(coleccion, reindexar=True) == total
    assert coleccion.count() == total


# --- Recuperación y generación -----------------------------------------------


async def test_respuesta_con_referencias(coleccion):
    modelo = modelo_falso(
        {"respuesta": "Martes y jueves de 10:00 a 16:00.", "referencias": ["deploys.md#1", "inventado.md#9"]}
    )
    r = await get_rag_response("¿Qué días se pueden hacer deploys?", crear_cadena(coleccion, modelo))

    assert r.encontrada
    assert r.referencias == ["deploys.md#1"]  # la referencia inventada se descarta


async def test_el_prompt_lleva_el_contexto_recuperado_y_top_k(coleccion):
    cadena = crear_cadena(coleccion, modelo_falso({"respuesta": NO_LO_SE, "referencias": []}), top_k=3)
    resultado = await cadena.ainvoke("ventanas de deploy martes y jueves")

    assert len(resultado["fragmentos"]) == 3
    assert resultado["fragmentos"][0]["id"].startswith("deploys.md")


async def test_pregunta_trampa_no_lo_se(coleccion):
    modelo = modelo_falso({"respuesta": NO_LO_SE, "referencias": ["deploys.md#1"]})
    r = await get_rag_response("¿Cuál es el presupuesto de marketing?", crear_cadena(coleccion, modelo))

    assert not r.encontrada
    assert r.referencias == []


async def test_reintenta_si_el_modelo_no_devuelve_json(coleccion):
    modelo = modelo_falso("Los deploys son martes y jueves.", {"respuesta": "Martes y jueves.", "referencias": []})
    r = await get_rag_response("¿Qué días se deploya?", crear_cadena(coleccion, modelo))

    assert r == RespuestaRAG(respuesta="Martes y jueves.", referencias=[])
