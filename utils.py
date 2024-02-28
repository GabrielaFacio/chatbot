from sentence_transformers import SentenceTransformer
import pinecone
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
    #print(result['matches'][0]['metadata'])
    return result['matches'][0]['metadata']['text'] +"\n"+result['matches'][1]['metadata']['text']
    # context1 = result['matches'][0]['metadata'].get('tokens', 'Contexto no encontrado')
    # context2 = result['matches'][1]['metadata'].get('tokens', 'Contexto no encontrado')
    
    # return context1 + "\n" + context2
def query_refiner(conversation, query):
    response = openai.chat.completions.create(
    messages=[
    {"role": "system", "content": f"Given the following user query and conversation log, formulate a question that would be the most relevant to provide the user with an answer from a knowledge base.\n\nCONVERSATION LOG: \n{conversation}\n\nQuery: {query}\n\nRefined Query:",
   },
    {"role": "user", "content": "The user question is ..."}
  ],
    model="gpt-3.5-turbo",
    #model="text-davinci-003",
    #prompt=f"Given the following user query and conversation log, formulate a question that would be the most relevant to provide the user with an answer from a knowledge base.\n\nCONVERSATION LOG: \n{conversation}\n\nQuery: {query}\n\nRefined Query:",
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