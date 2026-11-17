# Arquitectura de Turnito

Turnito es la plataforma de reserva de turnos médicos que usan las clínicas y consultorios
asociados. Los pacientes reservan desde la web o la app, y las clínicas gestionan sus agendas
desde un panel de administración. Este documento describe los componentes principales del
sistema, cómo se comunican y dónde vive cada dato.

## Visión general

El sistema está dividido en cuatro servicios que corren en contenedores dentro de un cluster
de Kubernetes con tres nodos de trabajo:

- **turnos-api**: la API principal, escrita en Python con FastAPI. Expone los endpoints REST
  que consumen la web, la app y el panel de clínicas. Escucha en el puerto 8040 dentro del
  cluster y se publica hacia afuera a través del ingress en `api.turnito.example`.
- **agenda-worker**: procesa tareas en segundo plano con Celery. Se encarga de generar la
  disponibilidad de cada profesional para los próximos 60 días, liberar turnos que no se
  confirmaron y recalcular agendas cuando una clínica cambia sus horarios.
- **notificador**: envía recordatorios por WhatsApp y SMS a través del proveedor externo
  Mensajería Sur. Manda un recordatorio 24 horas antes del turno y otro 2 horas antes.
- **panel-web**: el frontend del panel de clínicas, hecho en React y servido como sitio
  estático detrás del mismo ingress.

## Base de datos

Los datos principales viven en PostgreSQL 15. Hay una instancia primaria, que recibe todas
las escrituras, y una réplica de lectura que usan los reportes del panel de clínicas para no
cargar a la primaria. La réplica tiene, en condiciones normales, menos de 5 segundos de
retraso respecto de la primaria.

Las tablas más importantes son `turnos`, `profesionales`, `clinicas` y `pacientes`. La tabla
`turnos` es la más grande: supera los 40 millones de filas y está particionada por mes. Por
eso cualquier consulta sobre turnos tiene que filtrar por fecha; una consulta sin filtro de
fecha recorre todas las particiones y puede tardar minutos.

Los backups completos de PostgreSQL se hacen cada 6 horas y se retienen durante 14 días. Además
se guarda el WAL de forma continua, lo que permite restaurar la base a cualquier momento de
los últimos 7 días (point-in-time recovery). La restauración completa de un backup tarda
alrededor de 45 minutos.

## Colas y caché

agenda-worker y notificador reciben sus tareas a través de Redis, que cumple dos funciones:
es el broker de Celery y también la caché de disponibilidad. La disponibilidad de cada
profesional se cachea durante 5 minutos, así que un cambio de horario puede tardar hasta 5
minutos en verse reflejado en la web si no se invalida la caché a mano.

Si Redis se cae, la API sigue funcionando pero más lenta, porque calcula la disponibilidad
directamente contra PostgreSQL. Lo que sí se detiene son los recordatorios y la liberación
de turnos no confirmados, porque dependen de la cola.

## Flujo de una reserva

1. El paciente elige profesional, día y horario en la web o la app.
2. turnos-api verifica la disponibilidad (primero en la caché de Redis y, si no está, en
   PostgreSQL) y crea el turno en estado `pendiente`.
3. El paciente tiene 10 minutos para confirmar. Si no confirma, agenda-worker libera el turno
   y vuelve a quedar disponible.
4. Cuando el paciente confirma, el turno pasa a `confirmado` y se encolan los dos recordatorios
   en el notificador.
5. Si la clínica cancela el turno, el notificador avisa al paciente de inmediato por WhatsApp.

## Observabilidad

Las métricas de todos los servicios se recolectan con Prometheus y se visualizan en Grafana.
Los logs se centralizan en Loki y se conservan 30 días. Los tableros más consultados son
"Latencia de turnos-api", "Cola de Celery" y "Envíos del notificador". La métrica clave del
negocio es la tasa de reservas confirmadas por hora; si cae más de un 40% respecto de la misma
hora de la semana anterior, se dispara una alerta automática.

## Límites conocidos

- turnos-api aplica un rate limit de 100 requests por minuto por IP en los endpoints públicos.
- Mensajería Sur acepta como máximo 50 mensajes por segundo; por encima de ese valor devuelve
  errores 429 y el notificador reintenta con espera exponencial.
- El panel de clínicas permite exportar reportes de hasta 12 meses; para períodos más largos
  hay que pedirlo al equipo de datos.
