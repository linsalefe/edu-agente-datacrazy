from typing import List, Dict
from app.rag.vectorstore import VectorStore
from loguru import logger


class RAGQuery:
    """Gerencia queries e formatação de contexto RAG"""
    
    def __init__(self):
        self.vectorstore = VectorStore()
        self.max_context_chars = 2000
    
    def build_context(self, query: str, top_k: int = 4) -> str:
        """Busca documentos relevantes e formata contexto"""
        try:
            # Buscar documentos similares
            documents = self.vectorstore.similarity_search(query, top_k)
            
            if not documents:
                logger.warning("Nenhum documento relevante encontrado")
                return "Não há informações específicas disponíveis no momento."
            
            # Formatar contexto
            context_parts = []
            total_chars = 0
            
            for i, doc in enumerate(documents, 1):
                category = doc['metadata'].get('category', 'geral')
                source = doc['metadata'].get('source', 'documento')
                content = doc['content']
                
                # Verificar limite de caracteres
                if total_chars + len(content) > self.max_context_chars:
                    # Truncar se necessário
                    remaining = self.max_context_chars - total_chars
                    if remaining > 100:  # Só adiciona se sobrar espaço razoável
                        content = content[:remaining] + "..."
                    else:
                        break
                
                context_parts.append(f"### [{category.upper()}] {source}\n{content}")
                total_chars += len(content)
            
            formatted_context = "\n\n".join(context_parts)
            
            logger.info(f"✅ Contexto construído: {len(context_parts)} documentos, {total_chars} caracteres")
            
            return formatted_context
            
        except Exception as e:
            logger.error(f"Erro ao construir contexto: {e}")
            return "Erro ao buscar informações."
    
    def rerank_results(self, query: str, results: List[Dict]) -> List[Dict]:
        """Reordena resultados por relevância (implementação simples)"""
        # Por enquanto, mantém ordem da busca vetorial
        # Futuramente pode adicionar reranking mais sofisticado
        return results