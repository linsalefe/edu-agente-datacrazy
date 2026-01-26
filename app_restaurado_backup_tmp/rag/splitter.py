from typing import List, Dict
from loguru import logger


class RAGSplitter:
    """Divide textos grandes em chunks menores mantendo contexto"""
    
    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def split_text(self, text: str, metadata: Dict) -> List[Dict]:
        """Divide um texto em chunks com overlap"""
        
        if not text or len(text.strip()) == 0:
            return []
        
        # Limpar texto
        text = text.strip()
        
        # Se texto for menor que chunk_size, retornar direto
        if len(text) <= self.chunk_size:
            return [{
                'content': text,
                'metadata': metadata
            }]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Definir fim do chunk
            end = start + self.chunk_size
            
            # Se não é o último chunk, tentar quebrar em espaço
            if end < len(text):
                # Procurar último espaço antes do fim
                last_space = text.rfind(' ', start, end)
                if last_space > start:
                    end = last_space
            
            # Extrair chunk
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append({
                    'content': chunk_text,
                    'metadata': {
                        **metadata,
                        'chunk_index': len(chunks),
                        'char_start': start,
                        'char_end': end
                    }
                })
            
            # Mover start considerando overlap
            start = end - self.overlap
            if start <= 0:
                start = end
        
        logger.info(f"📄 Texto dividido em {len(chunks)} chunks")
        return chunks
    
    def split_documents(self, documents: List[Dict]) -> List[Dict]:
        """Divide múltiplos documentos em chunks"""
        all_chunks = []
        
        for doc in documents:
            metadata = {
                'source': doc.get('source', 'unknown'),
                'category': doc.get('category', 'unknown'),
                'type': doc.get('type', 'unknown')
            }
            
            chunks = self.split_text(doc['content'], metadata)
            all_chunks.extend(chunks)
        
        logger.info(f"✅ Total de chunks gerados: {len(all_chunks)}")
        return all_chunks