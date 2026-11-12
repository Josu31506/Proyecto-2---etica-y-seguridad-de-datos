# Operar el prototipo

## Permisos efectivos

| Operación | Cliente | Entrenador | Administrador |
|---|---|---|---|
| Consultar e ingresar mediciones, incluido CSV | Su ficha | Solo clientes asignados | Sin acceso |
| Consultar plan y progreso | Propios | Solo clientes asignados | Sin acceso |
| Programar sesiones y metas | Consulta | Solo clientes asignados | Sin acceso |
| Marcar sesión cumplida | Sesión propia, desde la fecha programada | Consulta | Sin acceso |
| Gestionar consentimiento de analítica | El propio | Sin acceso | Sin acceso |
| Responder a la alerta | Consulta de su plan | Solo clientes asignados | Sin acceso |
| Estadísticas protegidas | Sin acceso | Leer publicaciones | Publicar y leer |
| Auditoría y retención | Sin acceso | Sin acceso | Consulta |

La API valida rol y propietario en el servidor. Un operador con acceso controlado aprovisiona las cuentas reales y sus roles. El panel de administración no muestra historias biométricas. Las cuentas de demostración aparecen exclusivamente en el modo local.

**Qué mide el panel.** Adherencia es la fracción de sesiones semanales completadas sobre las programadas. La meta de uno o tres meses combina la fracción de minutos alcanzada y la reducción de grasa respecto a la primera medición del periodo. Los pesos los fija el entrenador y cada componente se acota de 0 a 100 %. La alerta se activa a las 00:00 de Lima al empezar el segundo día posterior a una sesión pendiente. La primera atención queda registrada una sola vez. La retención mide cuántas membresías activas al inicio de un mes cerrado continúan al final. La demo ya contiene ejemplos de membresías.

## Desarrollo local con recarga automática

Desde la raíz, en la primera terminal:

~~~powershell
.\.venv\Scripts\python -m backend.cli init
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
~~~

Desde la misma raíz, en la segunda:

~~~powershell
npm.cmd --prefix frontend run dev
~~~

La web y su ruta /api comparten un origen. La documentación interactiva de la API está en http://127.0.0.1:8000/docs en la demo. Para comprobar el flujo de contraseña local, usar **python -m backend.cli password cliente** dentro del entorno y **DEMO_SHORTCUTS=0** antes de iniciar la API. La cuenta de ejemplo es **cliente@demo.invalid**; el operador elige la contraseña en la terminal.

## Cifrado, claves y sesiones

Las mediciones y los valores de las metas se cifran antes de la inserción con AES-256-GCM, nonce aleatorio de 96 bits y etiqueta autenticada. Como datos asociados se incluyen tabla, propietario, fecha y versión de clave. Una manipulación del registro o traslado a otra ficha invalida el descifrado. Los IDs Fitbit se derivan por HMAC-SHA-256 con una clave separada. Fechas, roles, asignaciones, nombres, eventos y títulos de sesiones son datos de operación legibles para el servidor. No escribir diagnósticos ni datos sensibles en el título libre de un plan.

En la demo opcional con contraseña se usa bcrypt con coste 12 y sal individual. La cookie de sesión se limita a la API, es HttpOnly y SameSite=Strict. En el modo alojado también usa Secure. Se comprueban el origen de las escrituras, un encabezado propio y la asignación de cliente. En Supabase la autenticación se delega a Auth y cada petición comprueba la identidad remota y su rol en la base privada. El coste concreto de la infraestructura gestionada corresponde al proveedor. [Supabase Auth](https://supabase.com/docs/guides/auth/password-security).

Durante una ventana de mantenimiento, detener las escrituras, respaldar y ejecutar **python -m backend.cli rotate**. En la demo se crea una nueva clave y se vuelven a cifrar los registros en una transacción. En el modo alojado, primero incorporar al secreto una nueva clave de 32 bytes y marcar su versión activa, conservando las antiguas. Luego ejecutar el comando y reiniciar todos los procesos con el mismo llavero. Mantener las versiones históricas hasta que expiren sus respaldos. La clave HMAC conserva el enlace de importación y necesita su propia migración si se sustituye.

## Recuperación e incidentes

~~~powershell
.\.venv\Scripts\python -m backend.backup create E:\AlzaceRespaldos
.\.venv\Scripts\python -m backend.backup verify 'E:\AlzaceRespaldos\NOMBRE_DEL_ARCHIVO.azb'
~~~

La copia local es cifrada con una clave distinta. El verificador restaura en memoria, comprueba integridad y relaciones, descifra las mediciones y contrasta el presupuesto con las publicaciones. Las sesiones se excluyen del respaldo. Custodiar el llavero y la clave de respaldo por separado del medio que contiene las copias. La propuesta operativa es una copia diaria con retención de 30 días. Hay que asignar responsable, configurar destino independiente y programar y comprobar esa política en el despliegue.

Ante exposición o pérdida, el operador registra el incidente sin valores de salud, restringe el servicio afectado, revoca accesos, preserva evidencias y delimita personas y fechas afectadas. El responsable del club coordina las comunicaciones que correspondan. Recuperar en aislamiento y verificar la base, las claves y el último historial de publicaciones antes de habilitar el servicio. **Una restauración antigua puede permitir repetir consultas con ruido nuevo. Si falta el historial más reciente, mantener bloqueadas las publicaciones.** Registrar causa, corrección y pruebas de recuperación.

## Preparar staging con Supabase y Render

1. Crear un proyecto de pruebas y descargar de Supabase su certificado de CA. Usar conexión directa o pooler en modo sesión compatible con la configuración de PostgreSQL. Montar el certificado de confianza y usar **sslmode=verify-full**. La aplicación trabaja en el esquema privado **alzace**. Mantenerlo fuera de los esquemas expuestos por la Data API. [Conexiones PostgreSQL de Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres).
2. Configurar en el servicio Python **ALZACE_MODE=supabase**, **DATABASE_URL**, **SUPABASE_URL**, **SUPABASE_PUBLISHABLE_KEY**, **FRONTEND_ORIGIN** (origen HTTPS exacto) y **ALZACE_KEYRING**. El llavero es un objeto JSON con **active**, **keys** (versiones con 32 bytes aleatorios en base64 URL-safe) y **pseudonym** (clave independiente). Generar un llavero nuevo para staging, protegerlo en el gestor de secretos y restringir acceso. La API no necesita la clave service_role de Auth. [Formato de configuración](../.env.example).
3. Instalar **backend/requirements.txt**. En una operación de migración con permisos de DDL ejecutar **python -m backend.cli init**. Separar la identidad de migración y la de ejecución. A esta última conceder lo necesario para operar en el esquema, manteniendo la auditoría de solo inserción y consulta. Iniciar la API con **uvicorn backend.main:app --host 0.0.0.0 --port $PORT**.
4. Crear las identidades de prueba en Supabase Auth. Para asociarlas, usar **python -m backend.cli provision UUID entrenador "Nombre"** y después **python -m backend.cli provision UUID_CLIENTE cliente "Nombre" --trainer UUID_ENTRENADOR**. Para el administrador, usar el rol **administrador**. Supabase nunca recibe los perfiles sintéticos mediante init.
5. Para Next.js usar la carpeta **frontend**, definir **API_INTERNAL_URL** al origen HTTPS del backend durante el build y ejecución, ejecutar **npm ci** y **npm run build**. En hosting iniciar **npx next start --hostname 0.0.0.0 --port $PORT**. Verificar TLS en ambos extremos, el login real, los tres roles y la carpeta de respaldos del proveedor. La política pública de publicación se aprueba antes de habilitar nuevos análisis.

## Escaneo reproducible

Con Java 17+ y una distribución portátil completa de ZAP, ejecutar el siguiente comando desde la raíz. El script inicia otra base temporal con datos ficticios y visita rutas de la web, autenticación, fichas, denegaciones, consentimiento, auditoría y estadísticas a través del proxy. Guarda solo el resumen agregado de alertas. El destino se limita a loopback.

~~~powershell
.\.venv\Scripts\python scripts/zap-local.py 'C:\ruta\ZAP\zap-2.17.0.jar'
~~~

El resultado identifica las rutas observadas mediante el número de solicitudes y los posibles hallazgos por regla. Un análisis activo autorizado y la revisión del despliegue TLS con Supabase son comprobaciones posteriores. [Resultado local](../evidence/zap-pasivo.json) · [Documentación oficial de ZAP](https://www.zaproxy.org/getting-started/).
