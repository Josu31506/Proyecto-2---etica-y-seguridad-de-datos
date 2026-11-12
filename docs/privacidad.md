# Qué publica el club y qué precisión tiene

La pregunta es «¿cuántos minutos activos por día registró, en promedio, una persona del grupo durante el mes?». El entrenador puede consultar la estadística grupal. La ficha personal se protege por separado mediante autenticación, autorización por cliente y cifrado.

## De una persona a una contribución

1. En Fitbit se suman los minutos de actividad moderada e intensa de cada día. Un duplicado idéntico cuenta una vez. Un conflicto detiene la importación.
2. Se calcula una media por participante usando sus días observados. Cada persona pesa lo mismo. Se limita esa media a [0, 120] minutos. El tope se fijó para esta consulta de tendencia y puede subestimar a las personas más activas.
3. Dos conjuntos vecinos difieren en **todos** los registros mensuales de una persona. Restar 60 a cada media acotada hace que añadir o quitar una persona cambie la suma centrada a lo sumo en 60 y el conteo en 1.
4. Se protegen ambas cantidades con mecanismos Laplace independientes. Con ε = 1, cada uno recibe 0,5. Las escalas respectivas son 120 minutos y 2 personas. Si el conteo **con ruido** es menor que 8, se omite el valor. En otro caso se calcula 60 + suma protegida / conteo protegido, se acota el resultado y se redondea. La omisión y el redondeo son posprocesamiento. La garantía por publicación es (ε, 0)-DP bajo esta definición de vecindad.
5. La API ofrece fuentes y meses predefinidos. Una transacción guarda el cargo y la publicación juntos, incluso si se omite el valor. El mismo mes y fuente devuelven el resultado guardado. El límite global de ε = 2 admite dos publicaciones distintas de ε = 1 en toda la instalación. Para un servicio continuo habría que acordar presupuesto, horizonte y participación repetida antes de ampliar este alcance.

Elegimos **IBM diffprivlib 0.6.6** porque permite declarar la sensibilidad, dividir explícitamente el presupuesto y usar las mismas operaciones en la API y el experimento. El mecanismo Laplace incorpora un método de muestreo estudiado para reducir riesgos de precisión finita. Dejamos las semillas reproducibles para el laboratorio y usamos azar seguro en el servicio. La unidad protegida, los límites y la composición siguen siendo responsabilidad del equipo. [Holohan et al., Diffprivlib](https://arxiv.org/abs/1907.02444) · [Holohan y Braghin, Secure Random Sampling](https://arxiv.org/abs/2107.10138) · [NIST SP 800-226](https://csrc.nist.gov/pubs/sp/800/226/final).

## Experimento de utilidad en Fitbit

Se eligió la exportación del 12 de abril al 12 de mayo de 2016. En abril hay 33 participantes, 611 días-persona y entre 4 y 19 días observados por participante. La media ponderada por filas sería 35,49 min/día. Dando un voto a cada persona resulta 34,69. Después de acotar una contribución, la referencia queda en **34,05 min/día**. Esta exportación solo cubre parte de abril.

| ε por consulta | Simulaciones | Resultados devueltos | Error absoluto medio | Percentil 90 del error absoluto |
|---:|---:|---:|---:|---:|
| 0,1 | 300 | 83,7 % | 30,34 min | 67,85 min |
| 0,5 | 300 | 99,7 % | 9,50 min | 19,63 min |
| 1 | 300 | 100 % | 4,72 min | 9,69 min |
| 2 | 300 | 100 % | 2,32 min | 4,75 min |

Los errores se calculan sobre las estimaciones devueltas, frente a la media acotada. La diferencia con la media original es otro coste. Como objetivo académico propusimos error medio ≤ 5 minutos y al menos 95 % de respuestas. **ε = 1 es el menor valor ensayado que satisface ambos en este periodo.** Una publicación individual puede desviarse más. Para otro mes, población o tope conviene volver a evaluar la decisión con datos de estudio independientes.

Las semillas de evaluación y referencias exactas pertenecen al laboratorio offline de estos archivos de estudio. Divulgar una comparación exacta con datos operativos eludiría el presupuesto. La API guarda únicamente los resultados protegidos en su historial de publicaciones.

## Modelo y sesgo en Gym Members

Un clasificador predice si una sesión dura al menos 75 minutos, a partir de experiencia y frecuencia semanal. Se separan 681 filas para entrenamiento y 292 para prueba. El clasificador de referencia usa un histograma de 21 combinaciones de variables y dos clases. La versión privada añade Laplace al histograma de entrenamiento completo, con sensibilidad L1 = 1 porque una fila modifica una sola celda. Ambas usan el mismo ajuste de probabilidades y la misma prueba. La unidad protegida es **una fila de entrenamiento**. Gym carece de identificador longitudinal verificable.

| Resultado en prueba | Referencia | Privado ε = 1, media de 30 entrenamientos |
|---|---:|---:|
| Exactitud | 70,89 % | 68,38 % |
| Exactitud balanceada | 69,42 % | 68,77 % |
| AUC del ataque de membresía por confianza | 0,4924 | 0,4927 |
| Ventaja máxima del ataque (TPR − FPR) | 0,0214 | 0,0214 |
| Exactitud en el grupo Female (128) | 71,09 % | 67,97 % |
| Exactitud en el grupo Male (164) | 70,73 % | 68,70 % |

Con ε = 1 la exactitud disminuyó 2,51 puntos porcentuales. El ataque por confianza rindió cerca del azar en ambas versiones, por lo que este ensayo no distingue su resistencia empírica. El atributo de género se usa solo para examinar disparidades del experimento. La cobertura y el tamaño de los grupos limitan la interpretación. El modelo permanece en el notebook. La decisión sobre una meta corresponde al cliente y al entrenador.

[Resultados reproducibles](../evidence/experimentos.json) · [Experimento Fitbit](../notebooks/02_privacidad_diferencial.ipynb) · [Modelo y ética](../notebooks/03_modelo_y_etica.ipynb).
