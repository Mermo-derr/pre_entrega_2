# Extracción estructurada con LangChain

Cadena de **LangChain** que convierte texto libre en datos estructurados validados con **Pydantic**:
tecnologías mencionadas, nivel de criticidad y un resumen técnico. Usa **OpenAI** como modelo principal,
con **reintentos** ante errores transitorios y **fallback automático a Gemini** si OpenAI sigue fallando.
Cada llamada al modelo queda registrada en el log.

## Estructura

```
.
├── schemas.py          # Pydantic: EntityExtraction y CriticidadEnum
├── chain.py            # Prompt, modelos, reintentos, fallback, logging y script de prueba
├── .env.example        # Plantilla de variables de entorno
└── requirements.txt
```

### Diseño

- **`schemas.py`** define la salida esperada:
  - `EntityExtraction`: `tecnologias` (lista de textos), `nivel_de_criticidad` y `resumen_tecnico`.
  - `CriticidadEnum`: `bajo`, `medio` o `alto`.
- **`chain.py`** arma la cadena `prompt | modelo_principal.with_fallbacks([modelo_respaldo])`:
  - **Modelo principal:** `ChatOpenAI` (`gpt-4o`, `temperature=0`) con `with_structured_output(EntityExtraction)`.
  - **Reintentos:** `with_retry` hasta 3 intentos con espera exponencial y jitter. Los reintentos del SDK
    de OpenAI están desactivados (`max_retries=0`) para que solo reintente LangChain.
  - **Fallback:** si los 3 intentos fallan, la misma petición pasa a `ChatGoogleGenerativeAI`
    (`gemini-2.5-flash`) con la misma salida estructurada.
  - **`LLMLogHandler`** (`AsyncCallbackHandler`) registra el inicio de cada llamada (modelo y proveedor),
    los tokens usados y los errores, así se ven los reintentos y el paso al fallback.
- **`process_text(text)`** es la función asíncrona que ejecuta la cadena y devuelve un `EntityExtraction`.

## Requisitos

- Python 3.14 (probado con 3.14.7)
- Una clave de API de OpenAI y una de Google AI Studio (Gemini)

## Instalación

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Si PowerShell bloquea la activación ("la ejecución de scripts está deshabilitada"), ejecuta una vez
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

En Linux / macOS: `python3 -m venv .venv && source .venv/bin/activate`.

## Variables de entorno

Copia la plantilla y rellénala:

```powershell
Copy-Item .env.example .env
```

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | Sí | Clave de API de OpenAI (modelo principal). |
| `GOOGLE_API_KEY` | Para el fallback | Clave de API de Gemini. Sin ella, si OpenAI falla, también falla el respaldo. |

`chain.py` carga el `.env` con `load_dotenv(override=True)`, así que sus valores tienen prioridad sobre
las variables ya definidas en el sistema.

El archivo `.env` contiene tus claves y está en `.gitignore`: **nunca lo subas al repositorio**.

## Ejecutar el script de prueba

Con el entorno virtual activado:

```powershell
python chain.py
```

Procesa un texto de ejemplo sobre LangGraph y muestra en el log cada llamada al modelo, el tiempo total
y la criticidad detectada. Al final imprime el `EntityExtraction` resultante.

Sin activar el entorno virtual, cambia `python` por `.\.venv\Scripts\python.exe`.

## Uso desde código

```python
import asyncio
from chain import process_text

async def main():
    resultado = await process_text("Migramos la API de Flask a FastAPI y se cayó producción.")
    print(resultado.tecnologias)
    print(resultado.nivel_de_criticidad.value)
    print(resultado.resumen_tecnico)

asyncio.run(main())
```

## Manejo de errores

| Situación | Qué pasa |
|---|---|
| Error de conexión, timeout, 429 o 5xx de OpenAI | Se reintenta hasta 3 veces con espera exponencial. |
| La respuesta no cumple el esquema (`ValidationError`) | También se reintenta. |
| OpenAI falla los 3 intentos, o con otro error (por ejemplo clave inválida) | Pasa al fallback con Gemini. |
| Gemini también falla | `process_text` registra el error con la traza y relanza la excepción. |
