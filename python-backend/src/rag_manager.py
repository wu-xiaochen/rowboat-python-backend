import logging
from typing import List, Optional, Dict, Any
import asyncio
from datetime import datetime

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import WebBaseLoader, TextLoader
# 使用兼容硅基流动的 embeddings
try:
    from langchain_community.embeddings import OpenAIEmbeddings
except ImportError:
    from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Qdrant
from langchain.schema import Document
import qdrant_client
from qdrant_client.models import Distance, VectorParams

from .config import settings

logger = logging.getLogger(__name__)


class RAGManager:
    """
    Manages Retrieval-Augmented Generation (RAG) functionality
    """

    def __init__(self):
        self.client = None
        self.vector_store = None
        self.embeddings = None
        self.text_splitter = None

    async def initialize(self):
        """Initialize RAG components"""
        try:
            # Initialize Qdrant client
            self.client = qdrant_client.QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key
            )

            # Initialize embeddings - 使用硅基流动的 bge-m3 模型
            # OpenAIEmbeddings 兼容 OpenAI API 格式，硅基流动也支持
            # 确保使用正确的 API key，避免使用占位符
            embedding_key = settings.embedding_api_key or settings.provider_api_key
            if not embedding_key or embedding_key.strip() == "":
                raise ValueError("Embedding API key is not configured. Please set PROVIDER_API_KEY or EMBEDDING_API_KEY in .env file")
            if "your-ope" in embedding_key.lower() or "placeholder" in embedding_key.lower() or "sk-111" in embedding_key:
                raise ValueError(f"Invalid API key detected (placeholder value). Please check your .env file configuration.")
            
            logger.info(f"Initializing embeddings with API key: {embedding_key[:10]}...{embedding_key[-4:]}")
            self.embeddings = OpenAIEmbeddings(
                base_url=settings.embedding_base_url,  # 使用专门的 embedding_base_url
                openai_api_key=embedding_key,  # 使用验证过的 embedding_api_key
                model=settings.embedding_model         # BAAI/bge-m3
            )
            logger.info(f"Embeddings initialized with model: {settings.embedding_model} at {settings.embedding_base_url}")

            # Initialize text splitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
                separators=["\n\n", "\n", " ", ""]
            )

            logger.info("RAG manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG manager: {str(e)}")
            raise

    async def cleanup(self):
        """Cleanup RAG resources"""
        if self.client:
            self.client.close()
            logger.info("RAG client closed")

    async def create_collection(self, collection_name: str, vector_size: int = 1536) -> bool:
        """Create a new vector collection"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if collection_name in collection_names:
                logger.info(f"Collection {collection_name} already exists")
                return True

            # Create collection
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
            )

            logger.info(f"Collection {collection_name} created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {str(e)}")
            return False

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a vector collection"""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Collection {collection_name} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to delete collection {collection_name}: {str(e)}")
            return False

    async def add_documents(self, collection_name: str, documents: List[Document]) -> bool:
        """Add documents to a collection"""
        try:
            # Ensure collection exists
            await self.create_collection(collection_name)

            # Create vector store
            vector_store = Qdrant(
                client=self.client,
                collection_name=collection_name,
                embeddings=self.embeddings
            )

            # Add documents
            vector_store.add_documents(documents)

            logger.info(f"Added {len(documents)} documents to collection {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add documents to collection {collection_name}: {str(e)}")
            return False

    async def add_text(self, collection_name: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        """Add text to a collection"""
        try:
            # Create document
            document = Document(
                page_content=text,
                metadata=metadata or {}
            )

            return await self.add_documents(collection_name, [document])

        except Exception as e:
            logger.error(f"Failed to add text to collection {collection_name}: {str(e)}")
            return False

    async def add_url(self, collection_name: str, url: str) -> bool:
        """Add content from URL to a collection"""
        try:
            # Load documents from URL
            loader = WebBaseLoader(url)
            documents = loader.load()

            # Split documents
            split_docs = self.text_splitter.split_documents(documents)

            return await self.add_documents(collection_name, split_docs)

        except Exception as e:
            logger.error(f"Failed to add URL {url} to collection {collection_name}: {str(e)}")
            return False

    async def add_file(self, collection_name: str, file_path: str, file_type: str = "text") -> bool:
        """Add file content to a collection"""
        try:
            if file_type == "text":
                loader = TextLoader(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            documents = loader.load()
            split_docs = self.text_splitter.split_documents(documents)

            return await self.add_documents(collection_name, split_docs)

        except Exception as e:
            logger.error(f"Failed to add file {file_path} to collection {collection_name}: {str(e)}")
            return False

    async def search(self, collection_name: str, query: str, k: int = 5) -> List[Document]:
        """Search documents in a collection"""
        try:
            # 在执行搜索前，确保环境变量正确设置
            import os
            from .config import settings
            
            # 强制设置环境变量，确保 embeddings 使用正确的 API key
            if settings.provider_api_key:
                os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                # 同时确保 embeddings 对象使用正确的 API key
                if self.embeddings and hasattr(self.embeddings, 'openai_api_key'):
                    # 如果 embeddings 已经初始化，更新其 API key
                    current_key = getattr(self.embeddings, 'openai_api_key', None)
                    if not current_key or 'your-ope' in str(current_key).lower() or 'placeholder' in str(current_key).lower():
                        logger.warning(f"Detected invalid API key in embeddings, updating...")
                        self.embeddings.openai_api_key = settings.provider_api_key
            
            # Create vector store
            vector_store = Qdrant(
                client=self.client,
                collection_name=collection_name,
                embeddings=self.embeddings
            )

            # Perform similarity search
            results = vector_store.similarity_search(query, k=k)

            logger.info(f"Found {len(results)} results for query in collection {collection_name}")
            return results

        except Exception as e:
            logger.error(f"Failed to search collection {collection_name}: {str(e)}")
            return []

    async def search_with_score(self, collection_name: str, query: str, k: int = 5) -> List[tuple[Document, float]]:
        """Search documents with similarity scores"""
        try:
            # Create vector store
            vector_store = Qdrant(
                client=self.client,
                collection_name=collection_name,
                embeddings=self.embeddings
            )

            # Perform similarity search with scores
            results = vector_store.similarity_search_with_score(query, k=k)

            logger.info(f"Found {len(results)} results with scores for query in collection {collection_name}")
            return results

        except Exception as e:
            logger.error(f"Failed to search collection {collection_name} with scores: {str(e)}")
            return []

    async def get_collection_info(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a collection"""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vector_count": info.vectors_count,
                "indexed_vector_count": info.indexed_vectors_count,
                "points_count": info.points_count,
                "config": info.config
            }

        except Exception as e:
            logger.error(f"Failed to get info for collection {collection_name}: {str(e)}")
            return None

    async def list_collections(self) -> List[str]:
        """List all collections"""
        try:
            collections = self.client.get_collections()
            return [col.name for col in collections.collections]

        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            return []

    async def delete_documents(self, collection_name: str, document_ids: List[str]) -> bool:
        """Delete documents from a collection"""
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=document_ids
            )

            logger.info(f"Deleted {len(document_ids)} documents from collection {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete documents from collection {collection_name}: {str(e)}")
            return False

    async def update_document(self, collection_name: str, document_id: str, text: str, metadata: Dict[str, Any] = None) -> bool:
        """Update a document in a collection"""
        try:
            # Delete old document
            await self.delete_documents(collection_name, [document_id])

            # Add updated document
            return await self.add_text(collection_name, text, metadata)

        except Exception as e:
            logger.error(f"Failed to update document {document_id} in collection {collection_name}: {str(e)}")
            return False

    def format_search_results(self, results: List[Document]) -> str:
        """Format search results for use in prompts"""
        if not results:
            return "No relevant information found."

        formatted_results = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown")
            formatted_results.append(f"[{i}] {source}: {doc.page_content}")

        return "\n\n".join(formatted_results)

    def format_search_results_with_scores(self, results: List[tuple[Document, float]]) -> str:
        """Format search results with scores for use in prompts"""
        if not results:
            return "No relevant information found."

        formatted_results = []
        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown")
            formatted_results.append(f"[{i}] {source} (score: {score:.3f}): {doc.page_content}")

        return "\n\n".join(formatted_results)


# For use in agents and workflows
async def create_rag_tool(collection_name: str, description: str = "Search knowledge base") -> Any:
    """Create a RAG tool for use in CrewAI agents"""
    # 确保环境变量已设置 - 必须在初始化之前设置
    import os
    from .config import settings
    
    # 强制设置环境变量，覆盖任何现有的占位符值
    if settings.provider_api_key:
        os.environ["OPENAI_API_KEY"] = settings.provider_api_key
        # 验证设置成功
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key != settings.provider_api_key:
            logger.error(f"❌ Failed to set OPENAI_API_KEY! Expected: {settings.provider_api_key[:20]}..., Got: {env_key[:20] if env_key else 'None'}...")
        else:
            logger.info(f"✅ OPENAI_API_KEY environment variable set correctly: {settings.provider_api_key[:20]}...")
    
    rag_manager = RAGManager()
    await rag_manager.initialize()
    
    # 初始化后再次验证并更新 embeddings 的 API key
    if rag_manager.embeddings and hasattr(rag_manager.embeddings, 'openai_api_key'):
        actual_key = rag_manager.embeddings.openai_api_key
        # 检查是否是占位符或错误的 key
        if not actual_key or 'your-ope' in str(actual_key).lower() or 'placeholder' in str(actual_key).lower() or actual_key != settings.provider_api_key:
            logger.warning(f"⚠️ Embeddings API key mismatch detected!")
            logger.warning(f"   Current: {actual_key[:20] if actual_key else 'None'}...")
            logger.warning(f"   Expected: {settings.provider_api_key[:20]}...")
            logger.warning(f"   Updating embeddings API key...")
            # 强制更新
            rag_manager.embeddings.openai_api_key = settings.provider_api_key
            # 同时更新环境变量
            os.environ["OPENAI_API_KEY"] = settings.provider_api_key
            logger.info(f"✅ Updated embeddings API key successfully")
        else:
            logger.info(f"✅ Embeddings API key is correct: {actual_key[:20]}...")

    # 创建一个符合 CrewAI 工具接口的 RAGTool 类
    # CrewAI 工具需要实现 _run 和 _arun 方法
    class RAGTool:
        """Custom RAG tool for CrewAI - 确保使用正确的 API key"""
        
        # 工具元数据
        name: str = "rag_search"
        description: str = "Search knowledge base using RAG"

        def __init__(self, collection_name: str, description: str, rag_mgr: RAGManager):
            self.collection_name = collection_name
            self.description = description
            self.rag_manager = rag_mgr  # 保存 rag_manager 实例
            self.name = "rag_search"  # 工具名称
            
            # 立即设置环境变量，确保在使用时正确
            import os
            from .config import settings
            if settings.provider_api_key:
                os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                # 验证设置
                if os.getenv("OPENAI_API_KEY") != settings.provider_api_key:
                    logger.error(f"Failed to set OPENAI_API_KEY in RAGTool.__init__")
                else:
                    logger.debug(f"✅ OPENAI_API_KEY set in RAGTool.__init__")
            
            # 确保 embeddings 的 API key 正确
            if rag_mgr.embeddings and hasattr(rag_mgr.embeddings, 'openai_api_key'):
                current_key = rag_mgr.embeddings.openai_api_key
                if not current_key or 'your-ope' in str(current_key).lower() or current_key != settings.provider_api_key:
                    logger.info(f"Fixing embeddings API key in RAGTool.__init__")
                    rag_mgr.embeddings.openai_api_key = settings.provider_api_key

        def _run(self, query: str) -> str:
            """Run the RAG search - 同步版本"""
            try:
                # 确保环境变量正确 - 必须在调用前设置
                import os
                from .config import settings
                
                # 强制设置环境变量
                if settings.provider_api_key:
                    os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                    # 验证设置成功
                    if os.getenv("OPENAI_API_KEY") != settings.provider_api_key:
                        logger.error("Failed to set OPENAI_API_KEY environment variable")
                
                # 确保 embeddings 使用正确的 API key
                if self.rag_manager.embeddings:
                    # 直接更新 embeddings 的 API key
                    if hasattr(self.rag_manager.embeddings, 'openai_api_key'):
                        old_key = getattr(self.rag_manager.embeddings, 'openai_api_key', None)
                        # 检查是否是占位符值
                        if not old_key or 'your-ope' in str(old_key).lower() or 'placeholder' in str(old_key).lower() or old_key != settings.provider_api_key:
                            logger.info(f"Updating embeddings API key from {old_key[:10] if old_key else 'None'}... to {settings.provider_api_key[:10]}...")
                            self.rag_manager.embeddings.openai_api_key = settings.provider_api_key
                            # 同时更新环境变量（某些库可能会从环境变量读取）
                            os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                else:
                    logger.error("RAG manager embeddings not initialized")
                    return "Error: RAG embeddings not initialized. Please check API key configuration."
                
                # Run async search in sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 如果事件循环已经在运行，使用线程池
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(
                                asyncio.run,
                                self.rag_manager.search(self.collection_name, query, k=3)
                            )
                            results = future.result()
                    else:
                        results = loop.run_until_complete(
                            self.rag_manager.search(self.collection_name, query, k=3)
                        )
                except RuntimeError:
                    # 如果没有事件循环，创建一个新的
                    results = asyncio.run(
                        self.rag_manager.search(self.collection_name, query, k=3)
                    )

                return self.rag_manager.format_search_results(results)

            except Exception as e:
                logger.error(f"RAG search error: {str(e)}", exc_info=True)
                # 提供更详细的错误信息
                error_msg = str(e)
                if "your-ope" in error_msg.lower() or "incorrect API key" in error_msg.lower():
                    return f"Error: API key configuration issue. Please check your .env file. Original error: {error_msg}"
                return f"Error searching knowledge base: {str(e)}"

        async def _arun(self, query: str) -> str:
            """Async run the RAG search"""
            try:
                # 确保环境变量正确 - 必须在调用前设置
                import os
                from .config import settings
                
                # 强制设置环境变量
                if settings.provider_api_key:
                    os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                
                # 确保 embeddings 使用正确的 API key
                if self.rag_manager.embeddings:
                    if hasattr(self.rag_manager.embeddings, 'openai_api_key'):
                        old_key = getattr(self.rag_manager.embeddings, 'openai_api_key', None)
                        if not old_key or 'your-ope' in str(old_key).lower() or 'placeholder' in str(old_key).lower() or old_key != settings.provider_api_key:
                            logger.info(f"Updating embeddings API key in async context")
                            self.rag_manager.embeddings.openai_api_key = settings.provider_api_key
                            os.environ["OPENAI_API_KEY"] = settings.provider_api_key
                else:
                    logger.error("RAG manager embeddings not initialized")
                    return "Error: RAG embeddings not initialized. Please check API key configuration."
                
                results = await self.rag_manager.search(self.collection_name, query, k=3)
                return self.rag_manager.format_search_results(results)

            except Exception as e:
                logger.error(f"RAG search async error: {str(e)}", exc_info=True)
                error_msg = str(e)
                if "your-ope" in error_msg.lower() or "incorrect API key" in error_msg.lower():
                    return f"Error: API key configuration issue. Please check your .env file. Original error: {error_msg}"
                return f"Error searching knowledge base: {str(e)}"

    return RAGTool(collection_name, description, rag_manager)


# Global RAG manager instance
rag_manager = RAGManager()