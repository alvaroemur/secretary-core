# Política de clasificación de correo

Última actualización: YYYY-MM-DD

---

> Plantilla de ejemplo. Reemplaza los placeholders `<...>` y las filas
> de ejemplo con remitentes, dominios y reglas reales del usuario.

## Cola/Eliminar (para revisión final del usuario)

### Por remitente (eliminar siempre)

| Remitente | Dirección | Excepciones |
|---|---|---|
| Job alerts | `<sender@example.com>` | **NO eliminar.** Revisar cada alerta, evaluar relevancia vs. el perfil de `<USER_NAME>` (intereses profesionales, áreas temáticas, geografía) y dejar en inbox las que encajen. Archivar solo las claramente irrelevantes. |
| Notificaciones de agenda diaria | `<sender@example.com>` | Solo "Daily Agenda" o "no events scheduled" |
| Promos de servicio X | `<sender@example.com>` | — |
| Encuestas masivas | `<sender@example.com>` | — |
| Promos de retailer | `<sender@example.com>` | Excepto correos de cobro/pago |
| Newsletter promocional | `<sender@example.com>` | — |
| Promos de plataforma de diseño | `<sender@example.com>` | — |
| Promos de aerolínea | `<sender@example.com>` | — |
| Promos de agencia de viajes | `<sender@example.com>` | — |
| Promos de aseguradora | `<sender@example.com>` | NO las de seguro/débito/siniestros |
| Promos de banco | `<sender@example.com>` | — |
| Alertas de bolsas de empleo | `<sender@example.com>` | — |
| Newsletter de contenidos | `<sender@example.com>` | — |
| Promos de fintech | `<sender@example.com>` | — |
| Promos de SaaS | `<sender@example.com>` | NO los de pago fallido |
| Promos de juegos | — | — |
| Promos de cursos online | `<sender@example.com>` | — |
| Promos de software | `<sender@example.com>` | — |
| Anuncios de plataformas sociales | `<sender@example.com>` | — |

<!-- TODO: confirm if generic — completar con los remitentes reales del usuario -->

### Por contenido (eliminar)

- Promociones comerciales genéricas (ofertas, descuentos, marketing)
- Spam o correos irrelevantes
- Re-engagement emails ("we miss you", "come back")

### Salvaguarda

ANTES de etiquetar como eliminar, verificar que no haya nada relevante escondido: un evento interesante, una oportunidad profesional concreta, un pago pendiente. Si lo hay, NO etiquetar y mencionar en el resumen.

---

## Archivar (quitar del inbox)

### Por remitente (archivar siempre)

| Remitente | Dirección | Notas |
|---|---|---|
| Recibos de servicio de transporte | `<sender@example.com>` | Conservar, no en inbox |
| Alertas de seguridad de cuenta | `<sender@example.com>` | — |
| Recibos de pagos automáticos | `<sender@example.com>` | — |
| Newsletter técnico A | `<sender@example.com>` | — |
| Newsletter técnico B | `<sender@example.com>` | — |
| Plataforma de membresías | `<sender@example.com>` | Ya resumidos |
| Changelogs de producto | `<sender@example.com>` | — |
| Newsletters de herramientas dev | `<sender@example.com>` | — |
| Plataforma de gastos compartidos | `<sender@example.com>` | — |
| App de aprendizaje | `<sender@example.com>` | — |
| Tienda de videojuegos | `<sender@example.com>` | — |
| Newsletter de Substack/Quora | `<sender@example.com>` | — |
| Programa de lealtad de aerolínea | `<sender@example.com>` | — |
| Encuestas post-transacción de banco | `<sender@example.com>` | Si tienen >1 día |
| Notificaciones de consumo de banco | `<sender@example.com>` | Ya vistas |
| Extractos de banco | `<sender@example.com>` | — |
| Recibos de billing en la nube | `<sender@example.com>` | — |
| Newsletter de comunidad/ONG | `<sender@example.com>` | Ya resumidos |
| Updates de producto de SaaS | `<sender@example.com>` | Términos/producto |
| Notificaciones sociales de app | `<sender@example.com>` | — |
| Notificaciones de billetera/parqueo | `<sender@example.com>` | — |

<!-- TODO: confirm if generic — completar con los remitentes reales del usuario -->

### Por contenido (archivar)

- Newsletters y updates tecnológicos ya leídos/resumidos
- Correos informativos grupales donde no se requiere respuesta
- Hilos de conversación donde ya se resolvió el tema
- Invitaciones a eventos ya pasados

---

## Dejar en el inbox (nunca archivar automáticamente)

### Remitentes prioritarios

| Dominio | Contexto |
|---|---|
| `<org-domain-1.org>` | `<PROJECT_NAME>` — descripción breve |
| `<org-domain-2.org>` | `<PROJECT_NAME>` — descripción breve |
| `<org-domain-3.org>` | `<CONTACT_NAME>` — contacto comercial activo |

<!-- Listar dominios de proyectos/personas que NUNCA deben archivarse -->

### Alertas de seguridad

| Remitente | Dirección | Razón |
|---|---|---|
| Banco/servicio sensible | `<sender@example.com>` | El usuario no usa este producto activamente. Cualquier movimiento es red flag. Dejar + acción requerida. |

### Por contenido (dejar)

- Correos donde el usuario está en To: o Cc: directamente en temas de trabajo activo
- Correos con label IMPORTANT + CATEGORY_PERSONAL
- Correos que requieren respuesta (con borrador creado)
- Invitaciones a eventos que debe decidir si asistir
- Cualquier cosa con fecha límite próxima o urgencia

### Pagos/billing con problemas (siempre dejar + marcar acción requerida)

- Pagos rechazados de cualquier servicio
- Suspensiones de hosting/SaaS
- Pagos fallidos de suscripciones
- Billing de tiendas de apps
- Mora de seguros/EPS
- Cualquier correo de pago fallido, mora o suspensión de servicio

**Correos repetitivos de pago:** si hay múltiples del mismo problema, dejar solo el más reciente en inbox, archivar los anteriores. Mencionarlo como "problema recurrente sin resolver".

---

## Notas de evolución

<!-- Bitácora opcional: registrar cuándo se agregan/quitan remitentes o reglas -->

- YYYY-MM-DD: Archivo creado a partir de la plantilla de `secretary-core`.
