import os
from openai import OpenAI
client=OpenAI(api_key=os.getenv('OPENAI_API_KEY')) 

if client is not None:
    print("El cliente de OpenAI se ha inicializado correctamente.")
else:
    print("No se pudo inicializar el cliente de OpenAI.")