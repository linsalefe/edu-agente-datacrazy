from typing import Dict, Optional

from loguru import logger

from app.llm.router import PromptRouter


class PromptBuilder:
    """Constrói prompts completos com contexto RAG e dados do lead"""

    def __init__(self):
        self.router = PromptRouter()
        self.max_tokens = 4000  # Limite seguro para o prompt completo

    def build_system_prompt(
        self,
        stage: str,
        context_rag: str,
        lead_data: Optional[Dict] = None,
        intent: Optional[str] = None,
    ) -> str:
        """
        Monta o prompt completo do sistema

        Args:
            stage: Estágio atual da conversa
            context_rag: Contexto recuperado do RAG
            lead_data: Dados do lead (nome, perfil, etc)
            intent: Intenção detectada (opcional)

        Returns:
            Prompt completo formatado
        """
        # Buscar template do prompt
        prompt_template = self.router.get_prompt(stage, intent)

        # Preparar dados do lead (inclui qualificação coletada)
        lead_info = self._format_lead_data(lead_data)
        logger.info(f"🧾 Lead data no prompt:\n{lead_info}")

        # Truncar contexto RAG se necessário
        context_rag = self._truncate_context(context_rag)

        # Interpolar variáveis
        system_prompt = prompt_template.format(
            contexto_rag=context_rag,
            lead_data=lead_info,
        )

        # Verificar tamanho (estimativa: 1 token ≈ 4 caracteres)
        estimated_tokens = len(system_prompt) // 4
        if estimated_tokens > self.max_tokens:
            logger.warning(f"⚠️  Prompt muito grande: ~{estimated_tokens} tokens. Truncando...")
            max_context_chars = 1500
            context_rag_short = (context_rag[:max_context_chars] + "...") if len(context_rag) > max_context_chars else context_rag

            system_prompt = prompt_template.format(
                contexto_rag=context_rag_short,
                lead_data=lead_info,
            )

        logger.info(f"✅ Prompt construído: ~{len(system_prompt) // 4} tokens")
        return system_prompt

    def _format_lead_data(self, lead_data: Optional[Dict]) -> str:
        """Formata dados do lead para inclusão no prompt (inclui qualificação coletada)."""
        if not lead_data:
            return "Novo lead - informações ainda não coletadas"

        parts = []

        # Básico
        name = (lead_data.get("name") or "").strip()
        phone = (lead_data.get("phone") or "").strip()
        email = (lead_data.get("email") or "").strip()

        if name:
            parts.append(f"Nome: {name}")
        if phone:
            parts.append(f"Telefone: {phone}")
        if email:
            parts.append(f"Email: {email}")

        # Perfil
        profile = lead_data.get("profile") or {}

        # Qualificação (onde você está salvando curso/cidade/escolaridade)
        qual = profile.get("qualification") or {}

        course = (qual.get("course") or "").strip()
        city = (qual.get("city") or "").strip()

        if course:
            parts.append(f"Curso de interesse: {course}")
        if city:
            parts.append(f"Cidade: {city}")

        if "has_high_school" in qual:
            parts.append(f"Concluiu ensino médio: {'Sim' if qual.get('has_high_school') else 'Não'}")

        full_name = (qual.get("full_name") or "").strip()
        if full_name and (not name or full_name.lower() != name.lower()):
            parts.append(f"Nome completo informado: {full_name}")

        # Campos extras
        motivation = (qual.get("motivation") or "").strip()
        if motivation:
            parts.append(f"Motivação: {motivation}")

        return "\n".join(parts) if parts else "Informações básicas do lead"

    def _truncate_context(self, context: str, max_chars: int = 2000) -> str:
        """Trunca contexto RAG mantendo informação útil."""
        if not context:
            return ""

        if len(context) <= max_chars:
            return context

        truncated = context[:max_chars]
        last_newline = truncated.rfind("\n")

        # Se tem quebra perto do fim, tenta manter parágrafos completos
        if last_newline > max_chars * 0.8:
            truncated = truncated[:last_newline]

        return truncated + "\n\n[... contexto truncado ...]"
