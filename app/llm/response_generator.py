from app.llm.openai_client import OpenAIClient
from app.llm.prompt_builder import PromptBuilder
from app.rag.query import RAGQuery
from typing import List, Dict, Tuple, Optional
from loguru import logger


class ResponseGenerator:
    """Gera respostas da IA integrando RAG, prompts e OpenAI"""
    
    def __init__(self):
        self.openai_client = OpenAIClient()
        self.prompt_builder = PromptBuilder()
        self.rag_query = RAGQuery()
    
    def generate_response(
        self,
        user_message: str,
        conversation_history: List[Dict],
        stage: str,
        lead_data: Optional[Dict] = None,
        intent: Optional[str] = None
    ) -> Tuple[Optional[str], bool]:
        """
        Gera resposta baseada na mensagem do usuário
        
        Args:
            user_message: Mensagem do usuário
            conversation_history: Histórico da conversa (últimas N mensagens)
            stage: Estágio atual da conversa
            lead_data: Dados do lead
            intent: Intenção detectada (opcional)
            
        Returns:
            Tupla (resposta, precisa_handoff)
        """
        
        try:
            # 1. Buscar contexto relevante no RAG
            logger.info(f"🔍 Buscando contexto RAG para: {user_message[:50]}...")
            context_rag = self.rag_query.build_context(user_message, top_k=3)
            
            # 2. Construir prompt do sistema
            system_prompt = self.prompt_builder.build_system_prompt(
                stage=stage,
                context_rag=context_rag,
                lead_data=lead_data,
                intent=intent
            )
            
            # 3. Montar mensagens para OpenAI
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Adicionar histórico (últimas 6 mensagens = 3 trocas)
            for msg in conversation_history[-6:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Adicionar mensagem atual do usuário
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # 4. Gerar resposta
            logger.info("🤖 Gerando resposta com OpenAI...")
            response = self.openai_client.chat_completion(
                messages=messages,
                temperature=0.8,  # Mais criativo para vendas
                max_tokens=500
            )
            
            if not response:
                logger.error("❌ OpenAI retornou resposta vazia")
                return None, False
            
            # 5. Detectar se precisa handoff
            precisa_handoff = self._detect_handoff(response)
            
            if precisa_handoff:
                logger.warning("⚠️  Handoff detectado na resposta")
            
            logger.info(f"✅ Resposta gerada: {len(response)} caracteres")
            
            return response, precisa_handoff
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar resposta: {e}")
            return None, False
    
    def _detect_handoff(self, response: str) -> bool:
        """
        Detecta se a IA está indicando necessidade de handoff
        
        Keywords que indicam handoff:
        - Transferir, passar, conectar
        - Atendente, consultor, especialista
        - Não consigo, não posso
        """
        
        handoff_keywords = [
            'transferir',
            'passar para',
            'conectar com',
            'atendente',
            'consultor',
            'especialista',
            'equipe',
            'não consigo',
            'não posso ajudar',
            'aguarde um momento',
            'alguém te retorna'
        ]
        
        response_lower = response.lower()
        
        for keyword in handoff_keywords:
            if keyword in response_lower:
                logger.info(f"🎯 Keyword de handoff detectada: {keyword}")
                return True
        
        return False