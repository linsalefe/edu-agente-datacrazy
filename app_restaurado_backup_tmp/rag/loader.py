import os
from pathlib import Path
from typing import List, Dict
import PyPDF2
from docx import Document
from loguru import logger


class RAGLoader:
    """Carrega arquivos de conhecimento para o RAG"""
    
    def __init__(self, base_dir: str = "data/rag"):
        self.base_dir = Path(base_dir)
    
    def load_txt_files(self, directory: str) -> List[Dict]:
        """Carrega todos os arquivos .txt de um diretório"""
        files_data = []
        dir_path = self.base_dir / directory
        
        if not dir_path.exists():
            logger.warning(f"Diretório não encontrado: {dir_path}")
            return files_data
        
        for file_path in dir_path.glob("*.txt"):
            try:
                # Tentar UTF-8 primeiro
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Fallback para Latin-1
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                
                files_data.append({
                    'content': content,
                    'source': str(file_path.name),
                    'category': directory,
                    'type': 'txt'
                })
                
                logger.info(f"✅ Carregado: {file_path.name}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao carregar {file_path.name}: {e}")
        
        return files_data
    
    def load_pdf_files(self, directory: str) -> List[Dict]:
        """Carrega todos os arquivos .pdf de um diretório"""
        files_data = []
        dir_path = self.base_dir / directory
        
        if not dir_path.exists():
            return files_data
        
        for file_path in dir_path.glob("*.pdf"):
            try:
                with open(file_path, 'rb') as f:
                    pdf_reader = PyPDF2.PdfReader(f)
                    content = ""
                    
                    for page in pdf_reader.pages:
                        content += page.extract_text() + "\n"
                
                files_data.append({
                    'content': content,
                    'source': str(file_path.name),
                    'category': directory,
                    'type': 'pdf'
                })
                
                logger.info(f"✅ Carregado PDF: {file_path.name}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao carregar PDF {file_path.name}: {e}")
        
        return files_data
    
    def load_docx_files(self, directory: str) -> List[Dict]:
        """Carrega todos os arquivos .docx de um diretório"""
        files_data = []
        dir_path = self.base_dir / directory
        
        if not dir_path.exists():
            return files_data
        
        for file_path in dir_path.glob("*.docx"):
            try:
                doc = Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
                
                files_data.append({
                    'content': content,
                    'source': str(file_path.name),
                    'category': directory,
                    'type': 'docx'
                })
                
                logger.info(f"✅ Carregado DOCX: {file_path.name}")
                
            except Exception as e:
                logger.error(f"❌ Erro ao carregar DOCX {file_path.name}: {e}")
        
        return files_data
    
    def load_all_files(self) -> List[Dict]:
        """Carrega todos os arquivos de todas as categorias"""
        all_files = []
        
        # Categorias padrão
        categories = ['empresa', 'produtos', 'processos', 'faq']
        
        for category in categories:
            logger.info(f"📂 Carregando categoria: {category}")
            all_files.extend(self.load_txt_files(category))
            all_files.extend(self.load_pdf_files(category))
            all_files.extend(self.load_docx_files(category))
        
        logger.info(f"✅ Total de arquivos carregados: {len(all_files)}")
        return all_files