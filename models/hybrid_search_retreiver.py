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
import io
import pdfplumber
import requests
from bs4 import BeautifulSoup
import datetime
# from bs4.element import Tag



# pinecone integration
from langchain.cache import InMemoryCache
from langchain.chat_models import ChatOpenAI

# embedding
from langchain.globals import set_llm_cache

# prompting and chat
from langchain.llms.openai import OpenAI
from langchain.prompts import PromptTemplate

# hybrid search capability
from langchain.retrievers import PineconeHybridSearchRetriever
from langchain.schema import BaseMessage, HumanMessage, SystemMessage
from pinecone_text.sparse import BM25Encoder  # pylint: disable=import-error

# this project
from models.conf import settings
from models.pinecone import PineconeIndex

class Document:
    def __init__(self,page_content,metadata=None):
        self.page_content=page_content
        self.metadata=metadata if metadata is not None else {}

logging.basicConfig(level=logging.DEBUG if settings.debug_mode else logging.ERROR)


class HybridSearchRetriever:
    """Hybrid Search Retriever"""

    _chat: ChatOpenAI = None
    _b25_encoder: BM25Encoder = None
    _pinecone: PineconeIndex = None
    _retriever: PineconeHybridSearchRetriever = None

    def __init__(self):
        """Constructor"""
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

    def load(self, filepath: str):
        #aquí iría el de la conexión a la base de datos
         # """Pdf loader."""
        self.pinecone.pdf_loader(filepath=filepath)
    def tokenize (self,text):
        if text is not None:
            return text.split()
        else:
            return[]
  
    #Load sql database
    def load_sql(self,sql):
        
        #Connect to the bd
        conn=pyodbc.connect(connectionString)
        cursor=conn.cursor()

        #Execute the provided SQL command
        cursor.execute(sql)      
        rows=cursor.fetchall() 
        
        for row in rows:
            content=" ".join(str(col) for col in row if col is not None)           
            tokens=self.tokenize(content)
            document=Document(
                page_content=content,
                metadata={
                    "context":content,
                    "tokens":tokens
            })
            embeddings=self.pinecone.openai_embeddings.embed_documents([content])
            self.pinecone.vector_store.add_documents(documents=[document],embeddings=embeddings) 
            print(", ".join(f"{col}" for col in row))

        print("Finished loading data from SQL "+ self.pinecone.index_stats)
        conn.close()
    
           
        

    def rag(self, human_message: Union[str, HumanMessage]):
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

        #Add new message to history
        self.add_to_history(human_message)

        # ---------------------------------------------------------------------
        # 1.) Retrieve relevant documents from Pinecone vector database
        # ---------------------------------------------------------------------
        documents = self.retriever.get_relevant_documents(query=human_message.content)
        print("Documents retrieved from Pinecone: ")
        for doc in documents:
            print(doc.page_content)
        documents = self.pinecone.vector_store.similarity_search(query=human_message.content)
        #documents = self.pinecone.vector_store.bm25_search(query=human_message.content)
        # Extract the text from the documents
        document_texts = [doc.page_content for doc in documents]

        #Create system message taking into account either history and retrieved documents
        history_text=" ".join([human_message.content for message in self.message_history[-5:] ]) #Last 5 messages
        combined_context=f"{history_text}{' '.join(document_texts)}"

        leader = textwrap.dedent(
            """You are a helpful assistant.
            You can assume that all of the following is true.
            You should attempt to incorporate these facts
            into your responses:\n\n
        """
        )
        system_message_content = f"{leader} {combined_context}"
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
        response = self.cached_chat_request(system_message=system_message, human_message=human_message)

        #Add response to history system
        self.add_to_history(response)
        print("Response from the chat model: ")
        print(response.content)

        return response.content