from app.models.conversation import ConversationStage
from typing import Dict


class StageMapper:
    """Mapeia estágios do WhatsApp Agent para estágios do DataCrazy"""
    
    # Mapeamento de estágios internos → DataCrazy
    # IMPORTANTE: Ajuste os IDs conforme seu pipeline no DataCrazy
    STAGE_MAP: Dict[str, int] = {
        ConversationStage.novo.value: 1,           # Novo Lead
        ConversationStage.atendimento.value: 2,    # Em Atendimento
        ConversationStage.qualificacao.value: 3,   # Qualificação
        ConversationStage.negociacao.value: 4,     # Negociação
        ConversationStage.fechamento.value: 5,     # Fechamento
        ConversationStage.pos_venda.value: 6       # Pós-venda
    }
    
    @classmethod
    def map_stage_to_datacrazy(cls, stage: str) -> int:
        """
        Converte estágio interno para ID do DataCrazy
        
        Args:
            stage: Estágio interno (ex: 'novo', 'qualificacao')
            
        Returns:
            ID do estágio no DataCrazy
        """
        
        return cls.STAGE_MAP.get(stage, 1)  # Default: Novo Lead
    
    @classmethod
    def get_pipeline_id(cls) -> int:
        """
        Retorna ID do pipeline padrão
        IMPORTANTE: Configure isso no DataCrazy
        """
        return 1  # TODO: Configurar pipeline correto