# Local RAG con ChromaDB

Sistema RAG (Retrieval-Augmented Generation) de punta a punta: indexa documentos
`.md`/`.txt` en una base vectorial local (ChromaDB), y ante una pregunta busca los
fragmentos más relevantes y genera una respuesta **usando sólo esa información**.
Si la respuesta no está en los documentos, contesta **"No lo sé"** en vez de inventar.

```python
from rag import get_rag_response

r = await get_rag_response("¿Qué días se pueden hacer deploys a producción?")
print(r.respuesta)      # "Martes y jueves, entre las 10:00 y las 16:00..."
print(r.referencias)    # ["deploys.md#1"]
```

## Dataset

En `data/` hay 4 documentos de la documentación interna de **Turnito**, una empresa
inventada que hace un sistema de turnos médicos:

| Archivo | Tema |
|---|---|
| `arquitectura.md` | Servicios, base de datos, backups, colas, observabilidad |
| `deploys.md` | Ventanas de deploy, canary, feature flags, migraciones, rollback |
| `incidentes.md` | Severidades, roles, primeras acciones, postmortems |
| `guardias.md` | Rotación on-call, escalamiento, compensación |

Elegí una empresa inventada a propósito: como el modelo no puede saber nada de
Turnito de antemano, si responde bien es porque la información salió de los
documentos, y la pregunta trampa demuestra que no completa con conocimiento propio.

## Estructura

```
├── data/              # dataset de ejemplo (.md)
├── ingest.py          # ingesta: carga, chunking y guardado en ChromaDB
├── rag.py             # cadena RAG (LCEL) y get_rag_response()
├── schemas.py         # RespuestaRAG (Pydantic): respuesta + referencias
├── main.py            # las dos pruebas: pregunta normal y pregunta trampa
├── tests/             # tests sin red
├── .env.example
└── requirements.txt
```

## Instalación

Requiere **Python 3.12+** y una API key de OpenAI.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y poné tu OPENAI_API_KEY
```

| Variable | Obligatoria | Default | Descripción |
|---|---|---|---|
| `OPENAI_API_KEY` | sí | – | Se usa para los embeddings y para el modelo de chat |
| `OPENAI_MODEL` | no | `gpt-4.1-mini` | Modelo de chat |

## Cómo se ejecuta

**1. Ingesta** (opcional, `main.py` la corre sola si hace falta):

```bash
python ingest.py               # indexa sólo si la base está vacía
python ingest.py --reindexar   # borra todo y vuelve a indexar (ej. si cambiaste los documentos)
```

```
INFO    arquitectura.md: 1131 tokens -> 3 chunks
INFO    deploys.md: 1018 tokens -> 3 chunks
INFO    guardias.md: 846 tokens -> 2 chunks
INFO    incidentes.md: 1010 tokens -> 3 chunks
INFO    Guardados 11 chunks en la colección 'turnito_docs'
```

**2. Pruebas** (una pregunta que está en los documentos y una trampa):

```bash
python main.py
python main.py --pregunta "¿Cuánto tiempo se guardan los logs?"
```

Salida esperada (el texto exacto de la respuesta depende del modelo):

```
=== Prueba 1: la respuesta está en los documentos ===
INFO    Recuperados: deploys.md#1 (...), deploys.md#3 (...), ...
Pregunta: ¿Qué días y en qué horario se pueden hacer deploys a producción?
Respuesta: Los deploys a producción se hacen martes y jueves, entre las 10:00 y las 16:00 (hora de Buenos Aires).
Referencias: deploys.md#1
✓ Respondió con referencias

=== Prueba 2: pregunta trampa (no está en los documentos) ===
INFO    Recuperados: ... (los 4 más parecidos, aunque ninguno hable del tema)
Pregunta: ¿Cuál es el presupuesto anual de marketing de Turnito?
Respuesta: No lo sé
Referencias: -
✓ No alucinó: dijo que no lo sabe
```

Los números entre paréntesis son la distancia coseno de cada fragmento (más chica = más parecido).

**Tests** (no usan red ni API key):

```bash
pip install -r requirements-dev.txt
pytest
```

## Cómo funciona

### Ingesta (`ingest.py`)

1. Lee todos los `.md` y `.txt` de `data/`.
2. Los parte con `RecursiveCharacterTextSplitter` en chunks de **500 tokens con 50 de
   overlap**. El tamaño se mide en tokens con `tiktoken` (`cl100k_base`, el tokenizer
   de los embeddings de OpenAI), no en caracteres. Corto por **oraciones**, así nunca
   queda una idea partida a la mitad, y el overlap repite las últimas oraciones de un
   chunk al principio del siguiente para no perder el contexto entre los dos. (Si la
   última oración pasa de 50 tokens no se repite: el splitter no corta oraciones para
   armar el overlap.)
3. Guarda cada chunk en ChromaDB (`./vectorstore`, cliente persistente) con id
   `archivo#n` y metadata (`fuente`, `chunk`, `tokens`). Uso `upsert`, así correrlo dos
   veces no duplica nada.
4. **Si la base ya tiene datos, no reindexa** (no gasta tiempo ni plata en embeddings
   de nuevo). Para forzarlo está `--reindexar`.

### Embeddings

Uso `text-embedding-3-small` de OpenAI con similitud **coseno**. La colección se abre
siempre con la misma función, `obtener_coleccion()`, que usan tanto la ingesta como la
búsqueda, así no hay forma de indexar con un modelo y consultar con otro. Además
ChromaDB guarda qué función de embeddings tiene la colección.

No usé el modelo local por defecto de Chroma (`all-MiniLM-L6-v2`) porque sólo procesa
los primeros ~256 tokens de cada texto: con chunks de 500 tokens, se perdería la mitad
de cada fragmento. `text-embedding-3-small` acepta hasta 8191 tokens y funciona mejor
en español.

### Cadena RAG (`rag.py`)

```python
RunnableParallel(fragmentos=retriever, pregunta=RunnablePassthrough())
| RunnablePassthrough.assign(respuesta=prompt | modelo | PydanticOutputParser)
```

1. **Retriever:** convierte la pregunta en embedding y trae los **4 fragmentos** más
   parecidos (`TOP_K = 4`; pasar muchos más mete ruido y el modelo presta menos
   atención a lo importante). ChromaDB es sincrónico, así que la búsqueda corre con
   `asyncio.to_thread` para no bloquear el event loop.
2. **Prompt:** el prompt de sistema funciona como filtro de veracidad: responder sólo
   con el contexto y, si no está, decir exactamente "No lo sé". Cada fragmento va
   etiquetado con su fuente (`[deploys.md#1]`) para que el modelo pueda citarla.
3. **Modelo:** `ChatOpenAI` con temperatura 0, llamado de forma asíncrona (`ainvoke`).
4. **Parser:** `PydanticOutputParser` convierte la respuesta en un `RespuestaRAG`
   (`respuesta` + `referencias`). Si el modelo no devuelve un JSON válido, o hay un
   error transitorio de la API, se reintenta hasta 3 veces.

`get_rag_response(query)` ejecuta la cadena y además **descarta las referencias que el
modelo haya inventado**: sólo quedan las de fragmentos que realmente se recuperaron. Si
la respuesta es "No lo sé", las referencias quedan vacías.
