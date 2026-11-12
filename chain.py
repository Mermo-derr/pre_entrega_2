import asyncio
import logging
import time
from dotenv import load_dotenv
from langchain_core.callbacks import AsyncCallbackHandler
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
from pydantic import ValidationError
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from schemas import EntityExtraction
load_dotenv(override=True)

logger = logging.getLogger("chain")


class LLMLogHandler(AsyncCallbackHandler):
    """Registra cada llamada al modelo: así se ven los reintentos y si entra el fallback."""

    async def on_chat_model_start(self, serialized, messages, *, metadata=None, **kwargs):
        metadata = metadata or {}
        logger.info("Llamando a %s (%s)", metadata.get("ls_model_name", "?"), metadata.get("ls_provider", "?"))

    async def on_llm_end(self, response, **kwargs):
        uso = (response.llm_output or {}).get("token_usage")
        logger.info("Respuesta del modelo recibida%s", f" | tokens: {uso.get('total_tokens')}" if uso else "")

    async def on_llm_error(self, error, **kwargs):
        logger.warning("Error del modelo: %s: %s", type(error).__name__, error)

# Cliente principal (OpenAI) y de respaldo (Gemini)
llm = ChatOpenAI(model="gpt-4o", temperature=0, max_retries=0)
backup_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

structured_llm = llm.with_structured_output(EntityExtraction)

llm_con_retry = structured_llm.with_retry(
    retry_if_exception_type=(
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
        ValidationError,
    ),
    wait_exponential_jitter=True,
    stop_after_attempt=3,
)

backup_structured = backup_llm.with_structured_output(EntityExtraction)

prompt = ChatPromptTemplate.from_messages([
    ("system", "Extraé la información estructurada del texto del usuario."),
    ("human", "{input}"),
])

chain = prompt | llm_con_retry.with_fallbacks([backup_structured])

sample_text = (
    "LangGraph es una librería de LangChain para construir agentes "
    "con estado. Me parece muy útil, aunque la documentación "
    "todavía tiene huecos.")


async def process_text(text: str) -> EntityExtraction:
    """Ejecuta la cadena sobre `text` y devuelve la extracción estructurada."""
    logger.info("Procesando texto (%d caracteres)", len(text))
    inicio = time.perf_counter()
    try:
        resultado = await chain.ainvoke({"input": text}, config={"callbacks": [LLMLogHandler()]})
    except Exception:
        logger.exception("Falló la cadena tras %.2fs (OpenAI y Gemini)", time.perf_counter() - inicio)
        raise
    logger.info("Extracción completada en %.2fs | criticidad=%s", time.perf_counter() - inicio,
                resultado.nivel_de_criticidad.value)
    return resultado


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    resultado = await process_text(sample_text)
    print(resultado)


if __name__ == "__main__":
    asyncio.run(main())
