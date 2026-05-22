# 👋 Hola — ¿quieres probar esto del asistente con IA?

¡Hola, soy Álvaro! Te comparto esto porque a mí me está funcionando bien — pero quiero ser honesto: hay tantas soluciones como personas inteligentes en el mundo, y al final usar IA se trata de personalizarla a *tus* necesidades. Lo que me sirve a mí puede no ser tu estilo, y eso está perfecto.

Dicho esto, si has escuchado sobre "agentes de IA" pero no tienes muy claro qué son ni cómo empezar — este repo ("repositorio", básicamente una carpeta con código) es un **kit de inicio rápido**. Lo agarras, le apuntas tu herramienta de IA, y ella solita se configura para hacer un montón de cosas por ti: leer tu correo, hacer seguimiento a tus reuniones, organizar tu Drive y armar una wiki personal. 🤖✨

> 🧑‍💻 **¿Eres técnico?** No sigas leyendo 🫣 jeje. Anda directo al [README](../README.md) — tiene la arquitectura, el split core/instancia y un prompt para copiar y pegar.

---

## Primero, un "¿cómo así?" rápido 🤔

Tú sabes cómo funciona ChatGPT: escribes, te responde. Es una conversación. Genial para preguntas, pero no puede *hacer* nada fuera de esa ventana de chat.

Hay un tipo más nuevo de herramienta de IA — los **agentes de IA** — que sí pueden hacer cosas en tu computadora. Abrir archivos, crear carpetas, conectarse a tu Gmail, ejecutar programas. Es la diferencia entre *hablar de* ordenar tu escritorio y *que alguien lo ordene de verdad*. 🪄

**secretary** es un sistema que usa estos agentes como tu asistente personal. Lo configuras una vez, y después todos los días:

- 📧 Lee tu correo y limpia tu inbox
- 💬 Procesa tus conversaciones de WhatsApp
- 🎙️ Resume tus reuniones
- 📁 Organiza tu Google Drive
- 📚 Arma una wiki personal privada con todo lo que aprende

Tú mantienes el control — te reporta todo lo que hizo y te pregunta antes de tomar acciones importantes.

## OK, ¿qué necesito? 📋

Solo tres cosas:

1. 💻 Una computadora (Mac, Windows o Linux)
2. 🛠️ Una de las herramientas gratuitas de abajo
3. ⏱️ Unos 30 minutos — la IA hace el trabajo pesado, tú solo respondes sus preguntas

## Elige tu herramienta 🧰

### Cursor — gratis, la mejor para empezar ⭐

[Cursor](https://cursor.com) parece una app normal, pero tiene una IA integrada que puede leer y modificar archivos. Tiene un plan gratuito que alcanza para arrancar.

**Pasos:**

1. Entra a [cursor.com](https://cursor.com) y descárgalo
2. Instala y abre — se ve como un editor de texto, no te asustes
3. Ve al menú: **Terminal → New Terminal** (va a aparecer una cajita negra abajo — es normal)
4. Escribe esto y presiona Enter:
   ```
   git clone https://github.com/alvaroemur/secretary-core.git
   ```
5. Después escribe: `cd secretary-core`
6. Ahora abre el panel de IA: presiona **Cmd+L** (Mac) o **Ctrl+L** (Windows)
7. Pega este mensaje en el chat de la IA:

> Clone https://github.com/alvaroemur/secretary-core and help me set it up as my personal assistant. Read the README.md first, then walk me through creating my instance, picking channels, and scheduling the routines. Ask me questions as you go. Speak to me in Spanish.

Listo. La IA lee todo el proyecto, entiende cómo funciona y te guía paso a paso. Te va a preguntar cosas como "¿cuál es tu correo?" y "¿qué chats de WhatsApp quieres rastrear?" — solo responde con naturalidad.

### Windsurf — también gratis 🏄

[Windsurf](https://windsurf.com) funciona igual que Cursor. Descargas, instalas, abres terminal, clonas el repo, pegas el prompt. Elige el que más te guste.

### Claude Code — de pago, pero el más potente 💪

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) es con lo que se construyó secretary. Corre en la terminal (sin interfaz gráfica). Requiere suscripción Claude Pro o Max.

La gran ventaja: soporta **tareas programadas** — las rutinas corren automáticamente todos los días sin que hagas nada. Con Cursor/Windsurf tendrías que ejecutarlas manualmente o montar un programador externo.

### ¿Y ChatGPT? 🤷

ChatGPT no puede acceder a tu computadora, así que no puede configurar ni correr secretary. Pero puedes leer los [templates de rutinas](../routines/) para entender el sistema y sacar ideas. Si te gusta lo que ves, agarra una de las herramientas de arriba para ponerlo a andar.

## ¿Cómo se ve en la práctica? 🌅

Una vez configurado, tu día típico se ve así:

☀️ **Te despiertas** — secretary ya revisó tu correo durante la noche. Hay un reporte esperándote en GitHub con un resumen: mensajes importantes, borradores de respuesta que preparó para ti, qué archivó, seguimientos que sugiere. Lo revisas, ajustas un par de borradores, envías.

🌙 **Al final del día** — procesó tus chats de WhatsApp y reuniones. Contactos y proyectos nuevos se agregan a tu wiki privada automáticamente. Los pendientes quedan rastreados.

📚 **Con el tiempo** — tu wiki crece y se convierte en una base de conocimiento personal. "¿Quién era esa persona que conocí en la conferencia?" "¿Qué decidimos en esa reunión?" "¿Cuándo fue la última vez que hablé con este cliente?" Todo buscable, todo conectado.

## Preguntas frecuentes ❓

**¿Necesito saber programar?**
¡No! El agente de IA se encarga de toda la parte técnica. Tú solo le cuentas sobre ti y tus preferencias. 🙌

**¿Mis datos están seguros?** 🔒
Sí. Todo se queda en tu computadora y en tu repositorio privado de GitHub. Este repo (secretary-core) es solo el plano — no tiene ningún dato personal.

**¿Funciona en español?** 🌍
¡Sí! El motor está en inglés, pero durante la configuración la IA te pregunta tu idioma preferido y adapta todo — tus políticas, wiki, prompts, reportes — a español (o al idioma que quieras).

**¿Qué hago si me trabo?** 🆘
Deja un mensaje en [GitHub Issues](https://github.com/alvaroemur/secretary-core/issues) describiendo qué pasó. Incluye qué herramienta usas y qué ves en pantalla. Alguien te ayudará.

**¿Puedo empezar de a poco?** 🐣
Claro que sí. Puedes activar solo el correo y nada más. O solo WhatsApp. Vas agregando canales cuando quieras — el sistema es modular.
