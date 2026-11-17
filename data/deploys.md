# Política de deploys de Turnito

Este documento define cuándo y cómo se pasan cambios a producción. El objetivo es que los
deploys sean frecuentes, chicos y fáciles de revertir, sin afectar las horas de mayor uso de
las clínicas.

## Ventanas de deploy

Los deploys a producción se hacen únicamente los martes y jueves, entre las 10:00 y las 16:00
(hora de Buenos Aires). Fuera de esas ventanas sólo se permiten hotfixes para incidentes SEV1
o SEV2, y siempre con la aprobación del responsable de guardia.

Nunca se hacen deploys los viernes, ni el día anterior a un feriado nacional. Tampoco durante
la primera semana de cada mes, porque es cuando las clínicas cargan las agendas del mes y el
tráfico del panel se triplica.

## Requisitos antes de deployar

Todo cambio que llegue a producción tiene que cumplir con lo siguiente:

1. Estar mergeado en la rama `main` a través de un pull request.
2. Tener al menos una aprobación de otra persona del equipo. Los cambios en migraciones de
   base de datos necesitan dos aprobaciones, y una de ellas tiene que ser del equipo de
   plataforma.
3. Tener todos los checks de CI en verde: tests unitarios, tests de integración y el análisis
   de seguridad de dependencias.
4. Haber pasado al menos 2 horas en el entorno de staging sin errores nuevos en los logs.

## Cómo se hace un deploy

Los deploys se lanzan desde el pipeline de CI con el job `deploy-prod`, nunca a mano desde la
computadora de nadie. El pipeline construye la imagen, la etiqueta con el hash del commit y
la despliega con una estrategia canary:

- Primero el 10% del tráfico va a la versión nueva durante 15 minutos.
- Si la tasa de errores 5xx de la versión nueva no supera el 1% y la latencia p95 se mantiene
  por debajo de 800 ms, se pasa al 50% durante otros 15 minutos.
- Si los indicadores siguen bien, se completa al 100%.

Si en cualquiera de las etapas se superan los umbrales, el pipeline frena el avance y vuelve
automáticamente a la versión anterior.

## Feature flags

Las funcionalidades nuevas que cambian el comportamiento para los pacientes se lanzan detrás
de un feature flag. Los flags se gestionan desde el panel interno de configuración y permiten
activar una funcionalidad por clínica, por porcentaje de usuarios o para todos.

Un flag no puede quedar activo para todos y sin limpiar en el código durante más de 30 días.
El equipo revisa los flags vencidos el primer lunes de cada mes.

## Migraciones de base de datos

Las migraciones se escriben con Alembic y tienen que ser compatibles hacia atrás: la versión
anterior de turnos-api tiene que poder seguir funcionando con el esquema nuevo. En la práctica
eso significa:

- Agregar columnas como opcionales (nullable) y completarlas después.
- No renombrar ni borrar columnas en el mismo deploy en el que se dejan de usar; se borran en
  un deploy posterior, como mínimo una semana después.
- Crear los índices sobre la tabla `turnos` con `CREATE INDEX CONCURRENTLY`, porque un índice
  normal bloquea la tabla y deja a las clínicas sin poder reservar.

## Rollback

Cualquier persona del equipo puede pedir un rollback si ve un problema después de un deploy.
El rollback se hace re-ejecutando el job `deploy-prod` con la etiqueta de la versión anterior
y tarda unos 10 minutos. Si el problema involucra una migración, primero hay que consultar al
equipo de plataforma, porque revertir una migración puede implicar pérdida de datos.

Después de cada rollback se abre un ticket con la etiqueta `rollback` y se analiza en la
reunión semanal de operaciones de los miércoles.

## Comunicación

Cada deploy se anuncia en el canal `#deploys` al empezar y al terminar, con el link al pull
request y al job del pipeline. Si el deploy incluye cambios visibles para las clínicas, el
equipo de producto avisa a las clínicas por email con al menos 48 horas de anticipación.
