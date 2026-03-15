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


async def summarize_comments(comentarios: list[str], projeto_nome: str) -> str | None:
    """
    Recebe uma lista de comentários do diário de obra e retorna um resumo conciso
    usando Claude Haiku. Retorna None se a lista estiver vazia ou se houver erro.
    """
    if not comentarios:
        return None

    texto = "\n".join(f"- {c}" for c in comentarios)

    prompt = (
        f"Você é um assistente que resume comentários de diários de obra.\n"
        f"Projeto: {projeto_nome}\n\n"
        f"Comentários do diário:\n{texto}\n\n"
        f"Faça um resumo breve e objetivo em até 2 frases, destacando os pontos mais importantes. "
        f"Use linguagem direta, sem introduções como 'Os comentários indicam que...'."
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
