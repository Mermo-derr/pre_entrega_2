from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class CriticidadEnum(str, Enum):
    bajo = "bajo"
    medio = "medio"
    alto = "alto"


class EntityExtraction(BaseModel):
    tecnologias: List[str] = Field(description="Tecnologías utilizadas en el texto.")
    nivel_de_criticidad: CriticidadEnum = Field(description="Nivel de criticidad: 'bajo', 'medio' o 'alto'")
    resumen_tecnico: str = Field(description="Breve descripción del texto.")
