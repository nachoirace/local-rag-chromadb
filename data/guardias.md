# Guardias (on-call) en Turnito

El equipo de ingeniería tiene una guardia activa las 24 horas, todos los días, para responder
a las alertas de producción y a los incidentes. Este documento explica cómo funciona la
rotación, qué se espera de quien está de guardia y cómo se compensa.

## Rotación

La guardia rota semanalmente. Cada turno empieza el lunes a las 9:00 y termina el lunes
siguiente a las 9:00, cuando se hace el traspaso con la persona que entra. El traspaso es una
reunión corta de 15 minutos en la que se repasan los incidentes de la semana, las alertas que
sonaron y cualquier tarea pendiente.

Hay siempre dos personas de guardia:

- **Guardia primaria**: recibe todas las alertas y es la primera en responder.
- **Guardia secundaria**: recibe la alerta si la primaria no la reconoce en 10 minutos, y
  también da apoyo en incidentes SEV1.

Las personas nuevas en el equipo no entran en la rotación hasta completar su segundo mes y
haber hecho al menos una semana de guardia "en sombra", acompañando a alguien con experiencia.

## Qué se espera de la persona de guardia

- Tener la computadora y conexión a internet disponibles y poder empezar a trabajar en
  menos de 15 minutos desde que suena una alerta.
- Reconocer las alertas en la herramienta de alertas para que no escalen a la secundaria.
- Declarar un incidente cuando corresponda, siguiendo el documento de gestión de incidentes.
- Registrar en el resumen semanal cada alerta que sonó, aunque haya sido un falso positivo,
  para poder ajustar las alertas que generan ruido.

Durante la semana de guardia, la persona no tiene asignadas tareas de proyectos con fecha de
entrega. Su trabajo principal es atender producción y, en el tiempo libre, mejorar alertas,
runbooks y automatizaciones.

## Escalamiento

Si la persona de guardia necesita ayuda, el orden de escalamiento es:

1. Guardia secundaria.
2. Líder técnico del servicio afectado.
3. Gerente de ingeniería.
4. CTO, únicamente en incidentes SEV1.

Nunca está mal escalar. Es preferible despertar a alguien por un problema que resulta menor
que dejar un incidente grave sin la ayuda necesaria.

## Compensación

Cada semana de guardia se compensa con un día libre, que se puede tomar dentro de los 30 días
siguientes. Además, si la persona tuvo que trabajar en un incidente entre las 22:00 y las
7:00, al día siguiente puede empezar a trabajar más tarde, compensando las horas trabajadas
durante la noche.

Los cambios de guardia entre personas están permitidos siempre que se avise en el canal
`#guardias` con al menos 48 horas de anticipación y se actualice el calendario de la rotación.

## Herramientas

- **Alertas**: las alertas llegan por la aplicación móvil de la herramienta de alertas y,
  si no se reconocen en 5 minutos, también por llamada telefónica.
- **Runbooks**: cada alerta tiene un link a su runbook en la wiki, con los pasos para
  diagnosticarla y resolverla.
- **Accesos**: la persona de guardia tiene acceso de lectura a producción de forma
  permanente. El acceso de escritura a la base de datos se pide por la herramienta de accesos
  y dura 4 horas; queda registrado y se revisa en la reunión semanal de operaciones.
