from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
import openai
import streamlit as st
openai.api_key = "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"
model = SentenceTransformer('all-MiniLM-L6-v2')
#model=SentenceTransformer('sentence-transformers/distiluse-base-multilingual-cased')

pc=Pinecone(api_key='311981a0-29fd-4407-bdf4-b5d3c4582db3', environment='gcp-starter')
index = pc.Index('rag')
#index=Pinecone.Index(self=Pinecone,host='rag')

def find_match(input):
    input_em = model.encode(input).tolist()
    result = index.query(top_k=2,vector=input_em,includeMetadata=True) 
    print(result['matches'][0]['metadata']['lc_id']) 
    print(result['matches'][1]['metadata']['lc_id'])     
    return result['matches'][0]['metadata']['lc_id'] +"\n"+result['matches'][1]['metadata']['lc_id']
    
def query_refiner(conversation, query):
    response = openai.chat.completions.create(
    messages=[
    {"role": "system", "content": f"Given the following user query and conversation log, formulate a question that would be the most relevant to provide the user with an answer from a knowledge base.\n\nCONVERSATION LOG: \n{conversation}\n\nQuery: {query}\n\nRefined Query:",
   },
    {"role": "user", "content": "The user question is ..."}
  ],
    model="gpt-3.5-turbo",
    temperature=0.7,
    max_tokens=256,
    top_p=1,
    frequency_penalty=0,
    presence_penalty=0)
    #return response.choices[0].text
    return response.choices[0].message.content

def get_conversation_string():
    conversation_string = ""
    for i in range(len(st.session_state['responses'])-1):
        
        conversation_string += "Usuario: "+st.session_state['requests'][i] + "\n"
        conversation_string += "Bot: "+ st.session_state['responses'][i+1] + "\n"
    return conversation_string