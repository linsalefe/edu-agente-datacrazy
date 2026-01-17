from typing import Dict, Optional

from loguru import logger

from app.llm.router import PromptRouter


class PromptBuilder:
    """Constrói prompts completos com contexto RAG e dados do lead"""

    def __init__(self):
        self.router = PromptRouter()
        self.max_tokens = 4000

    def build_system_prompt(
        self,
        stage: str,
        context_rag: str,
        lead_data: Optional[Dict] = None,
        intent: Optional[str] = None,
    ) -> str:
        """
        Monta o prompt completo do sistema
        """
        # Buscar template do prompt
        prompt_template = self.router.get_prompt(stage, intent)

        # Preparar dados do lead
        lead_info = self._format_lead_data(lead_data)
        logger.info(f"🧾 Lead data no prompt:\n{lead_info}")

        # Truncar contexto RAG se necessário
        context_rag = self._truncate_context(context_rag)

        # Bloco de dados do lead com regra forte
        lead_data_block = self._build_lead_data_block(lead_data)

        # Interpolar variáveis no template
        system_prompt = prompt_template.format(
            contexto_rag=context_rag,
            lead_data=lead_info,
        )

        # Adiciona o bloco de dados do lead NO FINAL (mais peso)
        system_prompt = f"{system_prompt}\n\n{lead_data_block}"

        # Verificar tamanho
        estimated_tokens = len(system_prompt) // 4
        if estimated_tokens > self.max_tokens:
            logger.warning(f"⚠️  Prompt muito grande: ~{estimated_tokens} tokens. Truncando...")
            max_context_chars = 1500
            context_rag_short = (context_rag[:max_context_chars] + "...") if len(context_rag) > max_context_chars else context_rag

            system_prompt = prompt_template.format(
                contexto_rag=context_rag_short,
                lead_data=lead_info,
            )
            system_prompt = f"{system_prompt}\n\n{lead_data_block}"

        logger.info(f"✅ Prompt construído: ~{len(system_prompt) // 4} tokens")
        return system_prompt

    def _build_lead_data_block(self, lead_data: Optional[Dict]) -> str:
        """
        Constrói bloco explícito de dados do lead com regra forte.
        Inclui todos os campos necessários para fechamento.
        """
        block = """
═══════════════════════════════════════════════════════════════════════
📌 DADOS ATUAIS DO LEAD (NÃO PERGUNTE NOVAMENTE O QUE JÁ TEM)
═══════════════════════════════════════════════════════════════════════
"""
        
        if not lead_data:
            block += "Nenhum dado coletado ainda.\n"
        else:
            name = lead_data.get("name", "")
            phone = lead_data.get("phone", "")
            lead_email = lead_data.get("email", "")
            
            profile = lead_data.get("profile") or {}
            qual = {}
            if isinstance(profile, dict):
                if isinstance(profile.get("qualification"), dict):
                    qual = profile.get("qualification") or {}
                else:
                    qual = profile
            
            dados_coletados = []
            dados_faltantes = []
            
            # ===== DADOS BÁSICOS =====
            if name and name != "Cliente":
                dados_coletados.append(f"✅ Nome: {name}")
            else:
                dados_faltantes.append("❌ Nome completo: não coletado")
            
            # ===== DADOS DE INTERESSE =====
            course = qual.get("course")
            if course:
                dados_coletados.append(f"✅ Curso de interesse: {course}")
            else:
                dados_faltantes.append("❌ Curso: não coletado")
            
            city = qual.get("city")
            if city:
                dados_coletados.append(f"✅ Cidade/Polo: {city}")
            else:
                dados_faltantes.append("❌ Cidade: não coletado")
            
            education = qual.get("education_level")
            has_hs = qual.get("has_high_school")
            if education:
                dados_coletados.append(f"✅ Escolaridade: {education}")
            elif has_hs:
                dados_coletados.append(f"✅ Ensino médio: Concluído")
            else:
                dados_faltantes.append("❌ Escolaridade: não coletado")
            
            motivation = qual.get("motivation")
            if motivation:
                dados_coletados.append(f"✅ Motivação: {motivation[:80]}...")
            else:
                dados_faltantes.append("❌ Motivação: não coletado")
            
            # ===== DADOS PARA MATRÍCULA (FECHAMENTO) =====
            cpf = qual.get("cpf")
            if cpf:
                dados_coletados.append(f"✅ CPF: {cpf}")
            else:
                dados_faltantes.append("❌ CPF: não coletado")
            
            # Email pode estar no lead ou no qualification
            email = qual.get("email") or lead_email
            if email:
                dados_coletados.append(f"✅ E-mail: {email}")
            else:
                dados_faltantes.append("❌ E-mail: não coletado")
            
            birth_date = qual.get("birth_date")
            if birth_date:
                dados_coletados.append(f"✅ Data de nascimento: {birth_date}")
            else:
                dados_faltantes.append("❌ Data de nascimento: não coletado")
            
            cep = qual.get("cep")
            if cep:
                dados_coletados.append(f"✅ CEP: {cep}")
            else:
                dados_faltantes.append("❌ CEP: não coletado")
            
            if dados_coletados:
                block += "\n🟢 JÁ COLETADOS (NÃO PERGUNTE):\n"
                block += "\n".join(dados_coletados)
                block += "\n"
            
            if dados_faltantes:
                block += "\n🔴 FALTANTES (PERGUNTE UM POR VEZ):\n"
                block += "\n".join(dados_faltantes)
                block += "\n"

        block += """
═══════════════════════════════════════════════════════════════════════
⚠️  REGRA OBRIGATÓRIA:
- NUNCA pergunte o que já está com ✅
- Pergunte SOMENTE o que está com ❌ (um por vez)
- PRIORIDADE QUALIFICAÇÃO: 1º Curso → 2º Cidade → 3º Escolaridade → 4º Motivação
- PRIORIDADE FECHAMENTO: 1º CPF → 2º E-mail → 3º Data nascimento → 4º CEP
═══════════════════════════════════════════════════════════════════════
"""
        return block

    def _format_lead_data(self, lead_data: Optional[Dict]) -> str:
        """Formata dados do lead para inclusão no prompt."""
        if not lead_data:
            return "Novo lead - informações ainda não coletadas"

        parts = []

        name = (lead_data.get("name") or "").strip()
        phone = (lead_data.get("phone") or "").strip()
        email = (lead_data.get("email") or "").strip()

        if name and name != "Cliente":
            parts.append(f"Nome: {name}")
        if phone:
            parts.append(f"Telefone: {phone}")
        if email:
            parts.append(f"Email: {email}")

        profile = lead_data.get("profile") or {}
        qual = {}
        if isinstance(profile, dict):
            if isinstance(profile.get("qualification"), dict):
                qual = profile.get("qualification") or {}
            else:
                qual = profile

        course = (qual.get("course") or "").strip()
        city = (qual.get("city") or "").strip()
        education = (qual.get("education_level") or "").strip()
        has_hs = qual.get("has_high_school")
        motivation = (qual.get("motivation") or "").strip()
        cpf = (qual.get("cpf") or "").strip()
        qual_email = (qual.get("email") or "").strip()
        birth_date = (qual.get("birth_date") or "").strip()
        cep = (qual.get("cep") or "").strip()

        if course:
            parts.append(f"Curso de interesse: {course}")
        if city:
            parts.append(f"Cidade: {city}")
        if education:
            parts.append(f"Escolaridade: {education}")
        elif has_hs:
            parts.append("Ensino médio: Concluído")
        if motivation:
            parts.append(f"Motivação: {motivation[:100]}")
        if cpf:
            parts.append(f"CPF: {cpf}")
        if qual_email and qual_email != email:
            parts.append(f"E-mail: {qual_email}")
        if birth_date:
            parts.append(f"Data de nascimento: {birth_date}")
        if cep:
            parts.append(f"CEP: {cep}")

        return "\n".join(parts) if parts else "Informações básicas do lead"

    def _truncate_context(self, context: str, max_chars: int = 2000) -> str:
        """Trunca contexto RAG mantendo informação útil."""
        if not context:
            return ""

        if len(context) <= max_chars:
            return context

        truncated = context[:max_chars]
        last_newline = truncated.rfind("\n")

        if last_newline > max_chars * 0.8:
            truncated = truncated[:last_newline]

        return truncated + "\n\n[... contexto truncado ...]"