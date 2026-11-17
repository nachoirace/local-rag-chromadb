# Gestión de incidentes en Turnito

Un incidente es cualquier situación que afecta, o puede afectar en el corto plazo, la
posibilidad de que los pacientes reserven turnos o de que las clínicas gestionen sus agendas.
Este documento explica cómo se clasifican, quién responde y qué se hace después.

## Niveles de severidad

| Severidad | Descripción | Tiempo de respuesta |
|---|---|---|
| SEV1 | La plataforma no permite reservar turnos, hay pérdida de datos o un problema de seguridad. | 15 minutos |
| SEV2 | Una funcionalidad importante falla para muchas clínicas (por ejemplo, no salen los recordatorios) o la API está muy lenta. | 30 minutos |
| SEV3 | Un problema que afecta a pocas clínicas o tiene una alternativa manual. | 1 día hábil |

El tiempo de respuesta es el tiempo máximo entre que se detecta el incidente y que una persona
lo reconoce y empieza a trabajar en él, no el tiempo que tarda en resolverse.

Ante la duda entre dos severidades, se elige la más alta. Siempre es posible bajarla después.

## Cómo se declara un incidente

Cualquier persona de la empresa puede declarar un incidente. Para hacerlo se usa el comando
`/incidente` en el chat interno, que crea automáticamente un canal con el formato
`#inc-AAAAMMDD-descripcion`, avisa a la persona de guardia y abre un documento de seguimiento.

En incidentes SEV1 y SEV2 se asignan tres roles:

- **Coordinador/a del incidente**: toma las decisiones, organiza al equipo y define cuándo se
  da por resuelto. No se pone a investigar el problema técnico; su trabajo es coordinar.
- **Responsable técnico/a**: investiga la causa y aplica la solución. Normalmente es la persona
  de guardia del servicio afectado.
- **Comunicaciones**: actualiza la página de estado y responde a soporte. En SEV1 se publica
  una actualización en la página de estado como mínimo cada 30 minutos.

## Durante el incidente

La prioridad es mitigar, no encontrar la causa raíz. Si un deploy reciente puede estar
relacionado, la primera acción es hacer rollback, aunque no se esté seguro de que sea la causa.

Todas las acciones se registran en el canal del incidente con la hora, para poder reconstruir
la línea de tiempo después. Las decisiones importantes se toman en el canal y no por mensajes
privados.

Si en 45 minutos un SEV1 no tiene una mitigación en curso, el coordinador escala al CTO.

## Incidentes frecuentes y primeras acciones

- **La API responde con errores 503**: revisar el tablero "Latencia de turnos-api" y la
  cantidad de conexiones a PostgreSQL. Si el pool de conexiones está agotado, reiniciar los
  pods de turnos-api de a uno para no cortar el servicio.
- **No salen los recordatorios**: revisar el tablero "Cola de Celery". Si la cola crece sin
  bajar, verificar primero que Redis esté disponible y después el estado de Mensajería Sur en
  su página de estado.
- **Turnos duplicados**: desactivar el feature flag de la última funcionalidad de reservas que
  se haya lanzado y avisar al equipo de datos para corregir los registros.

## Después del incidente: postmortem

Todo incidente SEV1 o SEV2 tiene un postmortem. El documento se escribe en los 5 días hábiles
siguientes a la resolución y sigue la plantilla de la wiki: resumen, impacto (cuántas clínicas
y pacientes se vieron afectados y durante cuánto tiempo), línea de tiempo, causa raíz, qué
funcionó bien, qué funcionó mal y acciones de seguimiento.

Los postmortems son sin culpables: el foco está en qué del sistema o del proceso permitió que
el error ocurriera, no en quién lo cometió. Cada acción de seguimiento tiene una persona
responsable y una fecha, y se revisa en la reunión semanal de operaciones de los miércoles.

Para los SEV3 alcanza con una nota breve en el ticket explicando la causa y la solución.
