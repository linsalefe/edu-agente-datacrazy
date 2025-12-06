from app.rag.loader import RAGLoader
from app.rag.splitter import RAGSplitter
from app.rag.vectorstore import VectorStore
from loguru import logger
import sys


def load_rag_data():
    """Carrega arquivos RAG, divide em chunks e armazena embeddings"""
    
    try:
        logger.info("🚀 Iniciando carregamento da base de conhecimento RAG...")
        
        # 1. Carregar arquivos
        logger.info("📂 Passo 1/4: Carregando arquivos...")
        loader = RAGLoader()
        documents = loader.load_all_files()
        
        if not documents:
            logger.error("❌ Nenhum arquivo encontrado!")
            return False
        
        logger.info(f"✅ {len(documents)} arquivos carregados")
        
        # 2. Dividir em chunks
        logger.info("✂️  Passo 2/4: Dividindo em chunks...")
        splitter = RAGSplitter(chunk_size=500, overlap=50)
        chunks = splitter.split_documents(documents)
        
        logger.info(f"✅ {len(chunks)} chunks gerados")
        
        # 3. Limpar base anterior (opcional - comentar em produção)
        logger.info("🗑️  Passo 3/4: Limpando base anterior...")
        vectorstore = VectorStore()
        vectorstore.clear_all()
        
        # 4. Gerar embeddings e armazenar
        logger.info("🔮 Passo 4/4: Gerando embeddings e armazenando...")
        
        success_count = 0
        error_count = 0
        
        for i, chunk in enumerate(chunks, 1):
            try:
                vectorstore.store_document(
                    content=chunk['content'],
                    metadata=chunk['metadata']
                )
                success_count += 1
                
                # Log de progresso
                if i % 5 == 0:
                    logger.info(f"   Progresso: {i}/{len(chunks)} chunks processados")
                    
            except Exception as e:
                logger.error(f"   Erro no chunk {i}: {e}")
                error_count += 1
        
        # Resumo final
        total_docs = vectorstore.count_documents()
        logger.info(f"\n{'='*50}")
        logger.info(f"✅ CARREGAMENTO CONCLUÍDO!")
        logger.info(f"{'='*50}")
        logger.info(f"📊 Resumo:")
        logger.info(f"   • Arquivos lidos: {len(documents)}")
        logger.info(f"   • Chunks gerados: {len(chunks)}")
        logger.info(f"   • Embeddings criados: {success_count}")
        logger.info(f"   • Erros: {error_count}")
        logger.info(f"   • Total no banco: {total_docs}")
        logger.info(f"{'='*50}\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        return False


if __name__ == "__main__":
    success = load_rag_data()
    sys.exit(0 if success else 1)