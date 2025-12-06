from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class PromptRouter:
    """Gerencia e roteia prompts baseado em estágio e intenção"""
    
    def __init__(self):
        self.prompts_dir = Path("app/llm/prompts")
        self.prompts_cache: Dict[str, str] = {}
        self._load_prompts()
    
    def _load_prompts(self):
        """Carrega todos os prompts em cache"""
        prompt_files = {
            'base': 'base.txt',
            'atendimento': 'atendimento.txt',
            'qualificacao': 'qualificacao.txt',
            'objecoes': 'objecoes.txt',
            'fechamento': 'fechamento.txt',
            'handoff': 'handoff.txt'
        }
        
        for key, filename in prompt_files.items():
            file_path = self.prompts_dir / filename
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.prompts_cache[key] = f.read()
                logger.info(f"✅ Prompt carregado: {key}")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar prompt {key}: {e}")
                self.prompts_cache[key] = ""
    
    def get_prompt(self, stage: str, intent: Optional[str] = None) -> str:
        """
        Retorna o prompt apropriado baseado no estágio e intenção
        
        Args:
            stage: Estágio da conversa (novo, atendimento, qualificacao, etc)
            intent: Intenção detectada (objecao, duvida, interesse, etc)
        
        Returns:
            Texto do prompt
        """
        
        # Mapeamento de estágios para prompts
        stage_mapping = {
            'novo': 'atendimento',
            'atendimento': 'atendimento',
            'qualificacao': 'qualificacao',
            'negociacao': 'qualificacao',
            'fechamento': 'fechamento',
            'pos_venda': 'atendimento'
        }
        
        # Se detectou objeção, sempre usa prompt de objeções
        if intent == 'objecao':
            prompt_key = 'objecoes'
        # Se detectou sinal de fechamento, usa prompt de fechamento
        elif intent == 'fechamento':
            prompt_key = 'fechamento'
        # Senão, usa o prompt do estágio
        else:
            prompt_key = stage_mapping.get(stage, 'atendimento')
        
        # Buscar prompt específico
        specific_prompt = self.prompts_cache.get(prompt_key, '')
        
        # Sempre incluir o prompt base
        base_prompt = self.prompts_cache.get('base', '')
        
        # Combinar prompts
        combined = f"{base_prompt}\n\n{specific_prompt}"
        
        logger.info(f"🎯 Prompt selecionado: {prompt_key} (stage: {stage}, intent: {intent})")
        
        return combined
    
    def get_handoff_prompt(self) -> str:
        """Retorna prompt específico de handoff"""
        base = self.prompts_cache.get('base', '')
        handoff = self.prompts_cache.get('handoff', '')
        return f"{base}\n\n{handoff}"