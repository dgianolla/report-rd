import logging
import os

import anthropic

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


async def summarize_comments(ocorrencias: list[str], projeto_nome: str) -> str | None:
    """
    Recebe a lista de ocorrências (texto extraído do HTML) do diário de obra
    e retorna um resumo conciso usando Claude Haiku.
    Retorna None se a lista estiver vazia ou se houver erro.
    """
    if not ocorrencias:
        return None

    texto = "\n\n".join(ocorrencias)

    prompt = (
        f"Você é um assistente que resume ocorrências de diários de obra.\n"
        f"Projeto: {projeto_nome}\n\n"
        f"Ocorrências do diário:\n{texto}\n\n"
        f"Faça um resumo breve e objetivo em até 2 frases, destacando as principais atividades executadas. "
        f"Use linguagem direta, sem introduções como 'As ocorrências indicam que...'."
    )

    try:
        client = _get_client()
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = next((b.text for b in response.content if b.type == "text"), None)
        logger.info("LLM summarized comments for project '%s'", projeto_nome)
        return text
    except Exception as exc:
        logger.error("LLM summarization failed for project '%s': %s", projeto_nome, exc)
        return None
