from app.llm.router import PromptRouter
from typing import Dict, Optional
from loguru import logger


class PromptBuilder:
    """Constrói prompts completos com contexto RAG e dados do lead"""
    
    def __init__(self):
        self.router = PromptRouter()
        self.max_tokens = 4000  # Limite seguro para o contexto
    
    def build_system_prompt(
        self, 
        stage: str, 
        context_rag: str, 
        lead_data: Optional[Dict] = None,
        intent: Optional[str] = None
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
        
        # Preparar dados do lead
        lead_info = self._format_lead_data(lead_data)
        
        # Truncar contexto RAG se necessário
        context_rag = self._truncate_context(context_rag)
        
        # Interpolar variáveis
        system_prompt = prompt_template.format(
            contexto_rag=context_rag,
            lead_data=lead_info
        )
        
        # Verificar tamanho (estimativa: 1 token ≈ 4 caracteres)
        estimated_tokens = len(system_prompt) // 4
        
        if estimated_tokens > self.max_tokens:
            logger.warning(f"⚠️  Prompt muito grande: ~{estimated_tokens} tokens. Truncando...")
            # Truncar contexto RAG mais agressivamente
            max_context_chars = 1500
            context_rag = context_rag[:max_context_chars] + "..."
            system_prompt = prompt_template.format(
                contexto_rag=context_rag,
                lead_data=lead_info
            )
        
        logger.info(f"✅ Prompt construído: ~{len(system_prompt) // 4} tokens")
        
        return system_prompt
    
    def _format_lead_data(self, lead_data: Optional[Dict]) -> str:
        """Formata dados do lead para inclusão no prompt"""
        if not lead_data:
            return "Novo lead - informações ainda não coletadas"
        
        parts = []
        
        if lead_data.get('name'):
            parts.append(f"Nome: {lead_data['name']}")
        
        if lead_data.get('phone'):
            parts.append(f"Telefone: {lead_data['phone']}")
        
        if lead_data.get('email'):
            parts.append(f"Email: {lead_data['email']}")
        
        # Informações do perfil
        profile = lead_data.get('profile', {})
        
        if profile.get('interest'):
            parts.append(f"Interesse: {profile['interest']}")
        
        if profile.get('budget'):
            parts.append(f"Orçamento: R$ {profile['budget']}")
        
        if profile.get('urgency'):
            parts.append(f"Urgência: {profile['urgency']}")
        
        if profile.get('qualification_score'):
            parts.append(f"Score: {profile['qualification_score']}/100")
        
        return "\n".join(parts) if parts else "Informações básicas do lead"
    
    def _truncate_context(self, context: str, max_chars: int = 2000) -> str:
        """Trunca contexto RAG mantendo informação útil"""
        if len(context) <= max_chars:
            return context
        
        # Truncar mas tentar manter parágrafos completos
        truncated = context[:max_chars]
        last_newline = truncated.rfind('\n')
        
        if last_newline > max_chars * 0.8:  # Se tem quebra perto do fim
            truncated = truncated[:last_newline]
        
        return truncated + "\n\n[... contexto truncado ...]"