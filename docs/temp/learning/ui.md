# Server-rendered UI

`app/api/v1/endpoints/ui.py` serves Jinja2 templates and handles form posts for
login, signup, upload, analysis, search, Ask ICIA, comparison, legal, and admin
views. `templates/icia.html` and partials render HTML/CSS from server-provided
context. Browser -> HTTP form -> FastAPI auth/service call -> Jinja2 render ->
HTML response is the full interaction model.

There is no JavaScript, TypeScript, Node, React, Next, Vite, Vue, Angular, or
Svelte. This keeps the product surface Python/FastAPI-compatible and reduces
frontend build/dependency state. The tradeoff is less client-side interactivity;
server-side authorization remains the source of truth.
