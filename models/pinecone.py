# -*- coding: utf-8 -*-
"""A class to manage the lifecycle of Pinecone vector database indexes."""

# document loading
import glob

# general purpose imports
import json
import logging
import os
import pyodbc
# pinecone integration
import pinecone
from pinecone import Pinecone,PodSpec
from langchain.schema import BaseMessage, HumanMessage, SystemMessage

from langchain.document_loaders import PyPDFLoader
#from langchain.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import Document
from langchain.vectorstores.pinecone import Pinecone as LCPinecone

# this project
from models.conf import settings


logging.basicConfig(level=logging.DEBUG if settings.debug_mode else logging.ERROR)


# pylint: disable=too-few-public-methods
class TextSplitter:
    """
    Custom text splitter that adds metadata to the Document object
    which is required by PineconeHybridSearchRetriever.
    """

    def create_documents(self, texts):
        """Create documents"""
        documents = []
        for text in texts:
            # Create a Document object with the text and metadata            
            document = Document(page_content=text, metadata={"context":text})            
            documents.append(document)
        return documents
    
    
class PineconeIndex:
    """Pinecone helper class."""

    _index: pinecone.Index = None
    _index_name: str = None
    _text_splitter: TextSplitter = None
    _openai_embeddings: OpenAIEmbeddings = None
    _vector_store: LCPinecone = None


    def __init__(self):
        self._index=None
        self._text_splitter = None
        self._openai_embeddings = None
        self._vector_store = None
        self._pinecone=None
        logging.debug("PineconeIndex initialized.")
           
        self.message_history=[]
    def add_to_history(self,message:BaseMessage):
        self.message_history.append(message)
    def get_history(self):
        return self.message_history

    # @property
    # def index_name(self) -> str:
    #     """index name."""
    #     return self._index_name

    # @index_name.setter
    # def index_name(self, value: str) -> None:
    #     """Set index name."""
    #     if self._index_name != value:
    #         self.init()
    #         self._index_name = value
    #         self.init_index()

    
    @property
    def index(self) -> pinecone.Index:
        """pinecone.Index lazy read-only property."""
        if self._index is None:
            self._index=self.init_index()
            # self.init_index()
            # self._index = pinecone.Index(index_name=self.index_name)
        return self._index

    @property
    def index_stats(self) -> dict:
        """index stats."""
        retval = self.index.describe_index_stats()
        return json.dumps(retval.to_dict(), indent=4)


    @property
    def vector_store(self) -> LCPinecone:
        """Pinecone lazy read-only property."""
        if self._vector_store is None:
            self._vector_store = LCPinecone(
                index=self.index,
                embedding=self.openai_embeddings,
                text_key=settings.pinecone_vectorstore_text_key,
            )
        return self._vector_store


    @property
    def openai_embeddings(self) -> OpenAIEmbeddings:
        if self._openai_embeddings is None:
                   
        #"""OpenAIEmbeddings lazy read-only property."""
            self._openai_embeddings=OpenAIEmbeddings(                
                api_key=settings.openai_api_key.get_secret_value(),
                organization=settings.openai_api_organization     
            )
        
        return self._openai_embeddings

    @property
    def text_splitter(self) -> TextSplitter:
        """TextSplitter lazy read-only property."""
        if self._text_splitter is None:
            self._text_splitter = TextSplitter()
        return self._text_splitter

    def init_index(self):
        if self._pinecone is None:
            self._pinecone = Pinecone(api_key=settings.pinecone_api_key.get_secret_value())
            #Obtener la lista de índices existentes
            existing_indexes=self._pinecone.list_indexes()
            #Verificar si el índice ya existe
            if settings.pinecone_index_name in [index['name'] for index in existing_indexes]:
                logging.debug(f"Index {settings.pinecone_index_name} already exists.")
            else:        
                logging.debug(f"Creating index {settings.pinecone_index_name} as it does not exist")
                
                self._pinecone.create_index(
                    name=settings.pinecone_index_name,
                    dimension=1536,
                    metric="dotproduct",
                    spec=PodSpec(
                    environment="gcp-starter"
            )
        )
            self._index = self._pinecone.Index(settings.pinecone_index_name)
        return self._index      
        

    def delete(self):
        """Delete index."""
        if not self.initialized:
            logging.debug("Index does not exist. Nothing to delete.")
            return
        print("Deleting index...")
        pinecone.delete_index(self.index_name)

    

    def initialize(self):
        """Initialize index."""
        self.delete()
        self.create()

    def pdf_loader(self, filepath: str):
        """
        Embed PDF.
        1. Load PDF document text data
        2. Split into pages
        3. Embed each page
        4. Store in Pinecone

        Note: it's important to make sure that the "context" field that holds the document text
        in the metadata is not indexed. Currently you need to specify explicitly the fields you
        do want to index. For more information checkout
        https://docs.pinecone.io/docs/manage-indexes#selective-metadata-indexing
        """
        self.initialize()

        pdf_files = glob.glob(os.path.join(filepath, "*.pdf"))
        i = 0
        for pdf_file in pdf_files:
            i += 1
            j = len(pdf_files)
            print(f"Loading PDF {i} of {j}: {pdf_file}")
            loader = PyPDFLoader(file_path=pdf_file)
            docs = loader.load()
            k = 0
            for doc in docs:
                k += 1
                print(k * "-", end="\r")
                documents = self.text_splitter.create_documents([doc.page_content])
                document_texts = [doc.page_content for doc in documents]
                embeddings = self.openai_embeddings.embed_documents(document_texts)
                self.vector_store.add_documents(documents=documents, embeddings=embeddings)

        print("Finished loading PDFs. \n" + self.index_stats)

    def tokenize(self,text):
        if text is not None:
            return text.split()
        else:
            return[]
    
    def load_sql(self,sql):
        """
        Load data from SQL database
        """
        self.initialize()
        
        #Establecer conexión a la base de datos
        connectionString = f"DRIVER={os.environ['DRIVER']};SERVER={os.environ['SERVER']};DATABASE={os.environ['DATABASE']};UID={os.environ['UID']};PWD={os.environ['PWD']};TrustServerCertificate=yes;"
        conn=pyodbc.connect(connectionString)
        cursor=conn.cursor()

        #ejecutar consulta SQL
        sql="SELECT ch.clave,ch.nombre,ch.certificacion,ch.disponible,ch.sesiones,ch.pecio_lista,ch.subcontratado,ch.pre_requisitos,t.nombre AS tecnologia_id,c.nombre AS complejidad_id,tc.nombre AS tipo_curso_id, m.nombre AS nombre_moneda FROM cursos_habilitados ch JOIN tecnologias t ON ch.tecnologia_id = t.id JOIN complejidades c ON ch.complejidad_id = c.id JOIN tipo_cursos tc ON ch.tipo_curso_id = tc.id JOIN monedas m ON ch.moneda_id=m.id WHERE ch.disponible = 1;"
        cursor.execute(sql)
        rows=cursor.fetchall()
        
        #Procesar cada fila y crear documentos
        for row in rows:
            content=" ".join(str(col) for col in row if col is not None)
            tokens=self.tokenize(content)
            document=Document(
                page_content=content,
                metadata={
                    "context": content,
                    "tokens":tokens
                 })
            
        #Embed the document
            embeddings=self.openai_embeddings.embed_documents([content])
            self.vector_store.add_documents(documents=[document], embeddings=embeddings)
        print("Finished loading data from SQL. \n"+ self.index_stats)
        conn.close()

        
