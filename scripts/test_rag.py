from app.rag.query import RAGQuery
from loguru import logger

def test_rag_search():
    """Testa busca semântica no RAG"""
    
    rag = RAGQuery()
    
    queries = [
        "Quais cursos de saúde estão disponíveis?",
        "Quanto custa a mensalidade?",
        "O diploma EAD é reconhecido pelo MEC?"
    ]
    
    print("\n" + "="*60)
    print("🔍 TESTANDO BUSCA SEMÂNTICA RAG")
    print("="*60 + "\n")
    
    for query in queries:
        print(f"\n📝 Query: {query}")
        print("-" * 60)
        
        context = rag.build_context(query, top_k=2)
        
        print(f"📄 Contexto encontrado:\n")
        print(context[:500] + "..." if len(context) > 500 else context)
        print("\n" + "="*60)

if __name__ == "__main__":
    test_rag_search()