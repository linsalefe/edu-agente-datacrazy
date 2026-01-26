from sqlalchemy import Column, Integer, Text, JSON, Index
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector
from app.database import Base, SessionLocal
from app.config import settings
from openai import OpenAI
from loguru import logger
from typing import List, Dict


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # OpenAI embeddings são 1536 dimensões
    meta = Column(JSON, default={})  # MUDOU AQUI: metadata -> meta
    
    __table_args__ = (
        Index('idx_embedding', 'embedding', postgresql_using='ivfflat'),
    )


class VectorStore:
    """Gerencia armazenamento e busca de embeddings"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db = SessionLocal()
    
    def embed_text(self, text: str) -> List[float]:
        """Gera embedding para um texto usando OpenAI"""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            raise
    
    def store_document(self, content: str, metadata: Dict) -> int:
        """Armazena um documento com seu embedding"""
        try:
            # Gerar embedding
            embedding = self.embed_text(content)
            
            # Criar documento
            doc = Document(
                content=content,
                embedding=embedding,
                meta=metadata  # MUDOU AQUI: metadata -> meta
            )
            
            self.db.add(doc)
            self.db.commit()
            self.db.refresh(doc)
            
            return doc.id
            
        except Exception as e:
            logger.error(f"Erro ao armazenar documento: {e}")
            self.db.rollback()
            raise
    
    def similarity_search(self, query: str, top_k: int = 4) -> List[Dict]:
        """Busca documentos similares usando embeddings"""
        try:
            # Gerar embedding da query
            query_embedding = self.embed_text(query)
            
            # Buscar documentos similares
            results = self.db.query(Document).order_by(
                Document.embedding.l2_distance(query_embedding)
            ).limit(top_k).all()
            
            # Formatar resultados
            documents = []
            for doc in results:
                documents.append({
                    'content': doc.content,
                    'metadata': doc.meta,  # MUDOU AQUI: meta -> metadata no retorno
                    'id': doc.id
                })
            
            logger.info(f"🔍 Encontrados {len(documents)} documentos relevantes")
            return documents
            
        except Exception as e:
            logger.error(f"Erro na busca semântica: {e}")
            return []
    
    def clear_all(self):
        """Remove todos os documentos (usar apenas em dev)"""
        try:
            self.db.query(Document).delete()
            self.db.commit()
            logger.info("🗑️  Todos os documentos removidos")
        except Exception as e:
            logger.error(f"Erro ao limpar documentos: {e}")
            self.db.rollback()
    
    def count_documents(self) -> int:
        """Retorna total de documentos armazenados"""
        return self.db.query(Document).count()