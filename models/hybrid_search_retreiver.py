
# -*- coding: utf-8 -*-
"""
Hybrid Search Retriever. A class that combines the following:
    - OpenAI prompting and ChatModel
    - PromptingWrapper
    - Vector embedding with Pinecone
    - Hybrid Retriever to combine vector embeddings with text search
 
Provides a pdf loader program that extracts text, vectorizes, and
loads into a Pinecone dot product vector database that is dimensioned
to match OpenAI embeddings.
 
See: https://python.langchain.com/docs/modules/model_io/llms/llm_caching
     https://python.langchain.com/docs/modules/data_connection/document_loaders/pdf
     https://python.langchain.com/docs/integrations/retrievers/pinecone_hybrid_search
"""
# general purpose imports
import logging
import textwrap
from typing import Union
import pyodbc
from openai import OpenAI
from collections import deque

# pinecone integration
from langchain.cache import InMemoryCache
from langchain.chat_models import ChatOpenAI
# embedding
from langchain.globals import set_llm_cache
 
# prompting and chat
#from langchain.llms.openai import OpenAI
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
 
# hybrid search capability
from langchain.retrievers import PineconeHybridSearchRetriever
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from pinecone_text.sparse import BM25Encoder  # pylint: disable=import-error
 
# this project
from models.conf import settings
from models.pinecone import PineconeIndex
import os
import dropbox
 
class Document:
  def __init__(self,page_content,metadata=None):
        self.page_content=page_content
        self.metadata=metadata if metadata is not None else {}

class HybridSearchRetriever:
    """Hybrid Search Retriever"""
 
    _chat: ChatOpenAI = None
    _b25_encoder: BM25Encoder = None
    _pinecone: PineconeIndex = None
    _retriever: PineconeHybridSearchRetriever = None
 
    def __init__(self):
        """Constructor"""
        #conexión con dropbox
        #self.connection=os.environ['ACCESS_TOKEN']
        #self.dbx=dropbox.Dropbox(self.connection)
        set_llm_cache(InMemoryCache())
        self.message_history=[]
    def add_to_history(self,message:BaseMessage):
        self.message_history.append(message)
    def get_history(self):
        return self.message_history  
    
     
       
    @property
    def pinecone(self) -> PineconeIndex:
        """PineconeIndex lazy read-only property."""
        if self._pinecone is None:
            self._pinecone = PineconeIndex()
        return self._pinecone
 
    # prompting wrapper
    @property
    def chat(self) -> ChatOpenAI:
        """ChatOpenAI lazy read-only property."""
        if self._chat is None:
            self._chat = ChatOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),  # pylint: disable=no-member
                organization=settings.openai_api_organization,
                cache=settings.openai_chat_cache,
                max_retries=settings.openai_chat_max_retries,
                model=settings.openai_chat_model_name,
                temperature=settings.openai_chat_temperature,
            )
        return self._chat
 
    @property
    def bm25_encoder(self) -> BM25Encoder:
        """BM25Encoder lazy read-only property."""
        if self._b25_encoder is None:
            self._b25_encoder = BM25Encoder().default()
        return self._b25_encoder
 
    @property
    def retriever(self) -> PineconeHybridSearchRetriever:
        """PineconeHybridSearchRetriever lazy read-only property."""
        if self._retriever is None:
            self._retriever = PineconeHybridSearchRetriever(
                embeddings=self.pinecone.openai_embeddings, sparse_encoder=self.bm25_encoder, index=self.pinecone.index
            )
        return self._retriever
 
    def cached_chat_request(
        self, system_message: Union[str, SystemMessage], human_message: Union[str, HumanMessage]
    ) -> BaseMessage:
        """Cached chat request."""
        if not isinstance(system_message, SystemMessage):
            logging.debug("Converting system message to SystemMessage")
            system_message = SystemMessage(content=str(system_message))
 
        if not isinstance(human_message, HumanMessage):
            logging.debug("Converting human message to HumanMessage")
            human_message = HumanMessage(content=str(human_message))
        messages = [system_message, human_message]
        # pylint: disable=not-callable
        retval = self.chat(messages)
        return retval
 
    def prompt_with_template(
        self, prompt: PromptTemplate, concept: str, model: str = settings.openai_prompt_model_name
    ) -> str:
        """Prompt with template."""
        llm = OpenAI(
            model=model,
            api_key=settings.openai_api_key.get_secret_value(),  # pylint: disable=no-member
            organization=settings.openai_api_organization,
        )
        retval = llm(prompt.format(concept=concept))
        return retval
 
    # def load(self, filepath: str):
    #     try:
    #         #Obtener la lista de archivos PDF en la carpeta de Dropbox
    #         response=self.dbx.files_list_folder(filepath)

    #         #Iterar sobre los archivos PDF en la carpeta
    #         for entry in response.entries:
    #             if entry.name.endswith(".pdf"): #filtrar sólo PDF

    #                 #descargar el contenido del archivo PDF
    #                 _,res=self.dbx.files_download(entry.path_lower)
    #                 pdf_content=res.content
    #                 #procesar el contenido del PDF para generar embeddings
    #                 embeddings=self.pinecone.pdf_loader(pdf_content)
    #                 #se almacenan los embeddings en Pinecone
    #                 self.pinecone.vector_store.add_documents(embeddings)

    #                 #se imprime mensaje de confirmación
    #                 print(f"Embeddings generados y almacenados de dropbox")
        
    #     except Exception as e:
    #         print(f"Error: {e}")
       
      



    def tokenize (self,text):
        if text is not None:
            return text.split()
        else:
            return[]
 
    #Load sql database
    def load_sql(self,sql):
       
        #Connect to the bd
        connectionString = f"DRIVER={os.environ['DRIVER']};SERVER={os.environ['SERVER']};DATABASE={os.environ['DATABASE']};UID={os.environ['UID']};PWD={os.environ['PWD']};TrustServerCertificate=yes;"
        conn=pyodbc.connect(connectionString)
        cursor=conn.cursor()
 
        #Execute the provided SQL command
        sql="""SELECT 
    ch.clave, 
    ch.nombre, 
    ch.certificacion, 
    ch.disponible, 
    ch.sesiones, 
    ch.pecio_lista, 
    ch.subcontratado, 
    ch.pre_requisitos, 
    t.nombre AS tecnologia_id, 
    c.nombre AS complejidad_id, 
    tc.nombre AS tipo_curso_id, 
    m.nombre AS nombre_moneda,
    ce.nombre AS estatus_curso
FROM 
    cursos_habilitados ch 
JOIN 
    tecnologias t ON ch.tecnologia_id = t.id 
JOIN 
    complejidades c ON ch.complejidad_id = c.id 
JOIN 
    tipo_cursos tc ON ch.tipo_curso_id = tc.id 
JOIN 
    monedas m ON ch.moneda_id = m.id
JOIN
    cursos_estatus ce ON ch.curso_estatus_id = ce.id
WHERE 
    ch.disponible = 1 
    AND (ce.nombre = 'Es Rentable' OR ce.nombre = 'Liberado')
    AND tc.nombre IN ('intensivo', 'programa', 'digital')
UNION ALL
-- Consulta para cursos subcontratados
SELECT 
    ch.clave, 
    ch.nombre, 
    ch.certificacion, 
    ch.disponible, 
    ch.sesiones, 
    ch.pecio_lista, 
    ch.subcontratado, 
    ch.pre_requisitos, 
    t.nombre AS tecnologia_id, 
    c.nombre AS complejidad_id, 
    tc.nombre AS tipo_curso_id, 
    m.nombre AS nombre_moneda,
    ce.nombre AS estatus_curso
FROM 
    cursos_habilitados ch 
JOIN 
    tecnologias t ON ch.tecnologia_id = t.id 
JOIN 
    complejidades c ON ch.complejidad_id = c.id 
JOIN 
    tipo_cursos tc ON ch.tipo_curso_id = tc.id 
JOIN 
    monedas m ON ch.moneda_id = m.id
JOIN
    cursos_estatus ce ON ch.curso_estatus_id = ce.id
WHERE 
    ch.subcontratado = 1 
    AND tc.nombre IN ('Intensivo', 'Digital','Programa')
    AND (ce.nombre = 'Es Rentable' OR ce.nombre = 'Liberado');"""
        
        cursor.execute(sql)      
        rows=cursor.fetchall()
        self.datos_recuperados=[]
        for row in rows:
            contents=" ".join(str(col) for col in row if col is not None)          
            self.datos_recuperados.append(contents)
            tokens=self.tokenize(contents)
            document=Document(
                page_content=contents,
                metadata={
                    "context":contents,
                    "tokens":tokens
            })
            embeddings=self.pinecone.openai_embeddings.embed_documents([contents])
            self.pinecone.vector_store.add_documents(documents=[document],embeddings=embeddings)
            print(", ".join(f"{col}" for col in row))
 
        print("Finished loading data from SQL "+ self.pinecone.index_stats)
        conn.close()
   
           
       
 
    def rag(self, human_message: Union[str, HumanMessage],conversation_history=None):
        """
        Retrieval Augmented Generation prompt.
        1. Retrieve human message prompt: Given a user input, relevant splits are retrieved
           from storage using a Retriever.
        2. Generate: A ChatModel / LLM produces an answer using a prompt that includes
           the question and the retrieved data
 
        To prompt OpenAI's GPT-3 model to consider the embeddings from the Pinecone
        vector database, you would typically need to convert the embeddings back
        into a format that GPT-3 can understand, such as text. However, GPT-3 does
        not natively support direct input of embeddings.
 
        The typical workflow is to use the embeddings to retrieve relevant documents,
        and then use the text of these documents as part of the prompt for GPT-3.
        """
        if not isinstance(human_message, HumanMessage):
            logging.debug("Converting human_message to HumanMessage")
            human_message = HumanMessage(content=str(human_message))
 
        self.add_to_history(human_message)
        # ---------------------------------------------------------------------
        # 1.) Retrieve relevant documents from Pinecone vector database
        # ---------------------------------------------------------------------
        context= " ".join([msg.content for msg in conversation_history[-5:]])
        enhanced_query= f"{context} {human_message.content}"
        documents = self.retriever.get_relevant_documents(query=enhanced_query) 

        #2.)Constructing a response including all related information
       
        print("Documents retrieved from Pinecone: ")
        for doc in documents:
            print(doc.page_content)
        
        #Construyendo una respuesta incluyendo toda la información relacionada
        curso_claves = [doc.metadata.get('lc_id') for doc in documents]      
        #curso_claves = [next(iter(doc.metadata))]    
        claves_text = ". ".join(f"La clave del curso es: {clave}." for clave in curso_claves)
        document_texts=[doc.page_content for doc in documents] 
        leader = textwrap.dedent(
            """You are a helpful assistant.
            You always include the clave of the course you are talking about in that moment.
            Enlist all the information related to the courses and ordenate them by complexity.
            Enlist courses giving the following bullets:complejidad, duration, price and requirements.
            Yoy must show all related courses from the first answer.
            You can assume that all of the following is true.
            You should attempt to incorporate these facts
            into your responses:\n\n
        """
        )
        system_message_content = f"{leader}{claves_text} {'. '.join(document_texts)}"
        system_message = SystemMessage(content=system_message_content)   
 
        # ---------------------------------------------------------------------
        # finished with hybrid search setup
        # ---------------------------------------------------------------------
        logging.debug("------------------------------------------------------")
        logging.debug("rag() Retrieval Augmented Generation prompt")
        logging.debug("Diagnostic information:")
        logging.debug("  Retrieved %i related documents from Pinecone", len(documents))
        logging.debug("  System messages contains %i words", len(system_message.content.split()))
        logging.debug("  Prompt: %s", system_message.content)
        logging.debug("------------------------------------------------------")
        
 
        # 2.) get a response from the chat model
        response=self.cached_chat_request(system_message=system_message,human_message=human_message)
        print("Response from the chat model: ")
        return response.content
       
