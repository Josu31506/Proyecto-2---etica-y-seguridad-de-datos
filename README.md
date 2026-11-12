# Alzace Fitness · DS3031

Aplicación de seguimiento de entrenamiento virtual. La ficha individual muestra mediciones y planes. En otra pantalla, el club puede publicar una media mensual de actividad con privacidad diferencial. La web usa Next.js, la API usa FastAPI y el código de análisis vive en tres notebooks que comparten funciones con el backend.

## Abrir en Windows

Desde PowerShell, en la raíz de este repositorio:

~~~powershell
# Solo en un clon nuevo. Requisitos: Python 3.12, Node.js 22 y npm.
.\scripts\preparar.ps1

# Cada vez que quieras abrir la aplicación
.\scripts\iniciar.ps1
~~~

Abrir **http://127.0.0.1:3000** y elegir Cliente, Entrenador o Administrador. El lanzador comprueba los puertos 3000 y 8000, prepara la base y supervisa ambos servicios. Ctrl+C en esa terminal termina la demo. El primer inicio genera claves locales y perfiles de ejemplo. Los siguientes conservan las mediciones, los permisos y el presupuesto gastado. Para trabajar con recarga automática, inicia las dos terminales de la [guía de operación](docs/operacion.md).

## Recorrido para demostrar en clase

1. **Cliente → Mi actividad.** Registrar una medición o abrir **Historial → Importar mediciones CSV**. Comprobar la nueva fila y el avance de la meta mensual o trimestral. En **Mi privacidad**, activar o retirar el permiso para contribuir a estadísticas futuras.
2. **Entrenador → Mis clientes.** Elegir un cliente asignado, editar la meta y programar una sesión. En **Seguimiento**, registrar la primera atención de una alerta y observar el tiempo medio del mes.
3. **Administrador → Estadísticas.** Elegir **Estudio Fitbit / 2016-04** si se importó la fuente, o **Programa de entrenamiento** para la demo autocontenida. Publicar una estimación. Volver a abrirla y verificar el mismo valor y el mismo gasto de ε. Un conteo protegido bajo puede producir una omisión válida.
4. **Administrador → Auditoría.** Identificar el evento de publicación. En los notebooks se compara precisión y sesgo usando exclusivamente archivos de estudio. La web solo expone el resultado grupal protegido y deja el detalle personal al cliente y a su entrenador.

## Datos y notebooks

Las identidades de la demo y sus historias de entrenamiento son ficticias. El estudio Fitbit conserva un identificador seudónimo y actividad diaria cifrada, separado de los clientes. El archivo Gym se usa para evaluar un modelo y el efecto del ruido sobre sus predicciones. Las fuentes carecen de un identificador de persona compartido. Una asignación aleatoria entre ellas solo serviría para ilustrar el producto.

Para reproducir el estudio en otro equipo, indicar las rutas reales a los dos CSV. En los datos facilitados se usa la exportación **12 de abril – 12 de mayo de 2016**. La exportación anterior contiene fechas solapadas con valores contradictorios. La importación comprueba conflictos antes de guardar. El formulario web acepta un CSV de una sola ficha en el formato indicado en pantalla. Los CSV originales de investigación se preparan por separado:

~~~powershell
.\scripts\preparar-datos.ps1 -FitbitCsv 'C:\ruta\abril-mayo\dailyActivity_merged.csv' -GymCsv 'C:\ruta\gym_members_exercise_tracking.csv'
.\.venv\Scripts\python -m backend.cli init
.\.venv\Scripts\python -m backend.cli import-fitbit data/raw/dailyActivity_merged.csv
.\.venv\Scripts\python scripts/ejecutar-notebooks.py
.\.venv\Scripts\python -m backend.experiment
~~~

Los cuadernos originales están en **notebooks**. El ejecutor conserva copias con gráficas y salidas en **.local/notebooks**. En VS Code también puedes abrirlos y elegir el intérprete **.venv**. Las 300 repeticiones experimentales no acceden a la base o al presupuesto del panel. [Resultados y justificación bibliográfica](docs/privacidad.md) · [Datos Fitbit](https://www.kaggle.com/datasets/arashnic/fitbit) · [Datos Gym](https://www.kaggle.com/datasets/valakhorasani/gym-members-exercise-dataset).

## Cómo comprobar los requisitos técnicos

| Requisito | Evidencia |
|---|---|
| Frontend, API y base | Flujos por rol en Next.js y FastAPI. Demo persistente con SQLite. Esquema privado, autorización y presupuesto transaccional probados también sobre PostgreSQL. |
| Privacidad diferencial y utilidad | Consulta Laplace por participante, presupuesto común, experimento Fitbit y comparación de modelo Gym con y sin protección. [Método y resultados](docs/privacidad.md). |
| Ética y evaluación de impacto | Consentimiento verificable en la interfaz, análisis de cobertura y subgrupos, riesgos y responsables a lo largo del ciclo de vida. [DPIA](docs/DPIA.md). |
| Seguridad del proyecto | Control por registro, cifrado autenticado, auditoría, rotación, respaldos de demo y escaneo pasivo local. [Matriz de permisos y operaciones](docs/operacion.md). |
| Verificación | API e integración, caso de concurrencia real en PostgreSQL, navegador de escritorio y móvil, resultados de ZAP en **evidence**. |

~~~powershell
.\.venv\Scripts\python -m pytest -q
npm.cmd --prefix frontend run build
Push-Location frontend
npx.cmd playwright test
Pop-Location
~~~

Los recorridos de navegador crean otra base con perfiles ficticios y usan puertos 13090 y 18090. Requieren Chrome instalado o un canal Playwright compatible. El caso específico de PostgreSQL se ejecuta al definir **ALZACE_TEST_PG** apuntando a una base de pruebas vacía, con permisos para crear un esquema. El despliegue de Render/Supabase, la política programada de respaldos y una validación de HTTPS y sesiones con cuentas del equipo pertenecen a la siguiente etapa. El informe de curso está fuera de este repositorio de implementación.
