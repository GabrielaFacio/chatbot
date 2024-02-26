from sentence_transformers import SentenceTransformer
from transformers import GPT2TokenizerFast
import pinecone
from pinecone import Pinecone
import openai
import streamlit as st
openai.api_key = ""
model = GPT2TokenizerFast.from_pretrained('Xenova/text-embedding-ada-002')
#model=SentenceTransformer('Xenova/text-embedding-ada-002')
#EMBEDDING_MODEL = "text-embedding-3-small"

pinecone.init(api_key='', environment='gcp-starter')
index = pinecone.Index('rag')

def find_match(input):
    input_em = list(model.encode(input,convert_to_tensor=True))
    result = index.query(input_em, top_k=2, includeMetadata=True)
    return result['matches'][0]['metadata']['text']+"\n"+result['matches'][1]['metadata']['text']

def query_refiner(conversation, query):
    response = openai.completions.create(
    model="gpt-3.5-turbo-instruct",
    prompt=f"Given the following user query and conversation log, formulate a question that would be the most relevant to provide the user with an answer from a knowledge base.\n\nCONVERSATION LOG: \n{conversation}\n\nQuery: {query}\n\nRefined Query:",
    temperature=0.7,
    max_tokens=256,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0
    )
    return response.choices[0].text

def get_conversation_string():
    conversation_string = ""
    for i in range(len(st.session_state['responses'])-1):
        
        conversation_string += "Human: "+st.session_state['requests'][i] + "\n"
        conversation_string += "Bot: "+ st.session_state['responses'][i+1] + "\n"
    return conversation_string