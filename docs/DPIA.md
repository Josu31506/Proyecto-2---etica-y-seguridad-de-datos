# Evaluación de impacto del prototipo

**Alcance y finalidad.** El club propone usar actividad, sueño, frecuencia cardíaca, peso y grasa corporal para acompañar entrenamientos solicitados por el cliente. El uso secundario de actividad para estimar tendencias grupales es opcional. El club es el responsable propuesto. El entrenador actúa dentro de su asignación. El operador técnico custodia claves, respaldos y el presupuesto de privacidad. Supabase y Render serían proveedores del despliegue. La demostración local utiliza personas ficticias. Un archivo de investigación importado solo alimenta la estadística del estudio.

| Etapa | Datos y acceso | Decisión y riesgo residual |
|---|---|---|
| Obtención | CSV de investigación locales, registros voluntarios del programa | Documentar origen y finalidad. El permiso original de un estudio no autoriza contactar a participantes ni convertirlos en clientes. Antes de una operación real, definir y documentar la base para el seguimiento y revisar los términos de las fuentes. |
| Preparación | El operador valida actividad por persona y día. El identificador de origen se reemplaza por HMAC con clave independiente | Fechas y patrones de actividad pueden permitir vinculación incluso con seudónimo. Los archivos originales quedan fuera de Git y de los paneles. El modelo Gym se evalúa en su propia fuente. |
| Conservación | Mediciones y metas cifradas en el servidor. Las fechas y relaciones necesarias para autorizar consultas quedan visibles a la base | Separar claves y almacenamiento y restringir el operador. Definir un plazo de conservación y una vía de eliminación verificable antes de incorporar clientes reales. |
| Acceso individual | El cliente y su entrenador asignado consultan la ficha. Se registra el acceso. El administrador consulta eventos y publicaciones | Probar el intento de acceso cruzado, revisar asignaciones y retirar permisos al terminar una relación. El entrenador puede ver información sensible durante una sesión autorizada. |
| Estadísticas | El administrador publica una estimación por mes. El entrenador lee lo ya publicado. La participación de clientes operativos empieza desactivada | Mostrar propósito, método y efecto de retirar el permiso. Las consultas nuevas toman la preferencia vigente. Un resultado previamente divulgado permanece en el historial. |
| Respaldo y cierre | Copia cifrada y restauración verificada en entorno aislado | La operación requiere responsables, copias fuera del equipo, expiración verificable y recuperación del historial de publicaciones. Un borrado debe contemplar copias, accesos y plazo de purga. |

## Riesgos y acciones

La prioridad combina probabilidad e impacto en esta demo. El riesgo residual presupone que funcionan los controles descritos. Los responsables propuestos deben reevaluarla al desplegar.

| Escenario y daño | Riesgo inicial → residual | Medida, comprobación y responsable |
|---|---|---|
| Un entrenador consulta medidas de otro cliente | Alto → medio | Autorizar cada objeto en la API y auditar denegaciones. Prueba con dos clientes de distintos entrenadores. Equipo backend. |
| Un tercero reconoce una rutina al comparar promedios | Alto → medio | Acotar un aporte por persona, perturbar suma y conteo, fijar consultas y conservar resultados. Pruebas de simultaneidad y presupuesto. Responsable de analítica. |
| Un perfil con menos días registrados queda subrepresentado, o el tope penaliza a personas muy activas | Medio → medio | Promediar por persona, distinguir ausencias y cuantificar el efecto del tope. En abril cambió la media de 34,69 a 34,05. Equipo de datos. |
| Una predicción sesgada cambia el plan de una persona | Alto → bajo en la demo | Restringir el modelo al laboratorio, comparar utilidad por grupo y mantener revisión humana. Las categorías disponibles dejan fuera otras experiencias. Entrenador y equipo de datos. |
| La participación en estadísticas se percibe como una condición del servicio | Alto → bajo | Pantalla de consentimiento con propósito, opción desactivada por defecto, retiro y registro de la preferencia. El cliente conserva acceso a su plan. Responsable del club. |
| Se filtra una copia o se vuelve a publicar tras restaurar un presupuesto antiguo | Alto → medio | Cifrar la copia con clave separada, verificar contenido y restaurar en aislamiento. Conciliar el último historial previo a cualquier nueva publicación. Operador. |

## Decisión ética de diseño

Un día sin reloj no equivale a un día inactivo. La adherencia se calcula con sesiones programadas y declaradas como cumplidas. La barra de progreso usa una meta acordada y señala si faltan mediciones corporales. La alerta avisa de una sesión pendiente. El entrenador comprueba lo ocurrido con el cliente antes de cambiar el plan. La analítica grupal tiene ruido deliberado y se presenta con su unidad y periodo para evitar decisiones individuales basadas en una estimación del grupo.

**Antes de un piloto real**, acordar quién atiende solicitudes de acceso, rectificación y eliminación, revisar la conservación y las transferencias de los proveedores elegidos, verificar consentimiento y accesibilidad con usuarios y ensayar un incidente con el equipo. Esta evaluación de diseño registra esas decisiones pendientes.
