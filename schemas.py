from pydantic import BaseModel, Field

NO_LO_SE = "No lo sé"


class RespuestaRAG(BaseModel):
    """Lo que devuelve el RAG: la respuesta y de qué fragmentos salió."""

    respuesta: str = Field(
        description=f'Respuesta a la pregunta usando solo el contexto. Si no está en el contexto: "{NO_LO_SE}".'
    )
    referencias: list[str] = Field(
        default_factory=list,
        description='Fuentes de los fragmentos usados, tal cual aparecen entre corchetes (ej. "deploys.md#2"). '
        f'Vacía si la respuesta es "{NO_LO_SE}".',
    )

    @property
    def encontrada(self) -> bool:
        return not self.respuesta.strip().startswith(NO_LO_SE)
