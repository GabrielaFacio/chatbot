# -*- coding: utf-8 -*-
"""Sales Support Model (hsr) Retrieval Augmented Generation (RAG)"""
import os
from dotenv import find_dotenv, load_dotenv
from models.hybrid_search_retreiver import HybridSearchRetriever


hsr = HybridSearchRetriever()

dotenv_path = find_dotenv()
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path, verbose=True)
else:    
    raise FileNotFoundError("No .env file found in root directory of repository")

if __name__ == "__main__":
    sql_statement="""
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
    AND (ce.nombre = 'Es Rentable' OR ce.nombre = 'Liberado');

"""
    hsr.load_sql(sql=sql_statement)