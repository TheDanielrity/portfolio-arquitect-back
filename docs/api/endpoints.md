Lee primero y considera obligatorios:

- `AGENTS.md`
- `PLANS.md`

Antes de modificar cualquier archivo, inspecciona el repositorio frontend actual y verifica qué archivos ya existen.

Quiero implementar **únicamente la Fase 0 — Angular Foundation / Bootstrap** definida en `PLANS.md`.

No avances a la Fase 1.

---

# 1. Objetivo

Crear la base técnica del frontend Angular para el portafolio profesional de arquitectura.

Esta aplicación contendrá posteriormente:

- el portafolio público;
- el panel administrativo privado.

En esta fase NO debes implementar funcionalidades de negocio.

---

# 2. Antes de comenzar

Verifica:

- versión instalada de Node.js;
- versión de npm;
- compatibilidad con la versión estable de Angular que se vaya a utilizar;
- contenido actual del repositorio;
- existencia de `AGENTS.md`;
- existencia de `PLANS.md`;
- existencia de `docs/design/PUBLIC_UI.md`, si ya fue agregado.

No elimines ni sobrescribas estos documentos.

Si el repositorio todavía no contiene una aplicación Angular, inicialízala dentro del repositorio frontend actual.

No crees un repositorio Git anidado.

No crees otra carpeta `frontend` dentro del frontend actual.

---

# 3. Angular

Inicializa el proyecto utilizando una versión estable y compatible de Angular.

Configura:

- Standalone Components;
- Angular Router;
- SCSS;
- strict TypeScript;
- SSR / hybrid rendering support;
- HttpClient disponible en la configuración de aplicación;
- Angular modern application configuration.

No utilizar NgModules para la arquitectura principal.

No desactivar strict mode.

No utilizar Zone.js de manera no estándar ni modificar la estrategia predeterminada sin una razón técnica clara.

---

# 4. SSR

SSR debe quedar funcionando desde esta primera fase.

El objetivo es que posteriormente las rutas públicas puedan beneficiarse de:

- SEO;
- metadata;
- mejor carga inicial;
- indexación;
- social sharing.

No implementes todavía estrategias avanzadas de prerendering.

No implementes SEO todavía.

Solo deja la infraestructura SSR correctamente creada y validada.

Debes comprobar que una ruta simple puede renderizar correctamente sin depender de APIs exclusivas del navegador.

---

# 5. Package manager

Usa `npm` para este proyecto.

No utilices:

- yarn;
- pnpm;
- bun.

No mezcles gestores de paquetes.

Debe existir únicamente el lockfile correspondiente a npm.

---

# 6. Dependencias

Mantén las dependencias iniciales al mínimo.

En esta fase puedes utilizar únicamente dependencias necesarias para:

- Angular;
- SSR;
- testing;
- linting;
- formatting.

No instales todavía:

- PrimeNG;
- Tailwind;
- Bootstrap;
- Angular Material;
- NgRx;
- Three.js;
- model-viewer;
- icon libraries;
- animation libraries;
- chart libraries;
- OpenAPI generators;
- authentication packages;
- upload libraries.

Estas dependencias se evaluarán cuando una fase concreta las necesite.

No instales una biblioteca simplemente porque pueda ser útil más adelante.

---

# 7. Linting y formatting

Configura una solución moderna y mantenida para linting de Angular y TypeScript.

Utiliza ESLint mediante la integración recomendada actualmente para Angular.

No utilices TSLint.

Configura Prettier para formatting si no existe ya una estrategia equivalente claramente establecida por el proyecto.

Evita reglas redundantes o conflictos entre ESLint y Prettier.

Agrega scripts claros en `package.json`, por ejemplo equivalentes a:

- `lint`
- `format`
- `format:check`
- `test`
- `build`

Adapta los nombres solo si las herramientas generadas por Angular ya establecen una convención mejor.

---

# 8. TypeScript

Mantén TypeScript en modo estricto.

No desactives opciones estrictas para hacer que el proyecto compile.

Evita `any`.

No agregues:

`skipLibCheck`

o relajaciones globales nuevas salvo que Angular las genere oficialmente o exista una necesidad técnica documentada.

Mantén activadas las comprobaciones estrictas de templates de Angular.

---

# 9. Estructura inicial

Usa como referencia la arquitectura definida en `AGENTS.md`.

Crea únicamente la estructura que realmente sea necesaria en esta fase.

La estructura objetivo futura es:

```text
src/app/
├── core/
├── shared/
├── layouts/
├── features/
├── app.config.ts
└── app.routes.ts
```

No crees decenas de carpetas vacías.

En esta fase basta con crear los elementos necesarios para demostrar:

- routing;
- layout público;
- layout administrativo;
- configuración base.

---

# 10. Layout público inicial

Crea un `PublicLayout` mínimo.

Debe servir únicamente como contenedor técnico.

No diseñes todavía la interfaz definitiva del portafolio.

No implementes hero, proyectos, servicios ni contacto.

Puede contener simplemente:

- `<router-outlet>`;
- estructura semántica mínima;
- marcador temporal discreto si es necesario.

No apliques todavía la dirección artística completa de `PUBLIC_UI.md`.

Ese documento será obligatorio cuando comiencen las fases de diseño público.

---

# 11. Layout administrativo inicial

Crea un `AdminLayout` mínimo.

No implementes todavía:

- sidebar definitivo;
- dashboard;
- autenticación;
- navegación administrativa real.

Debe funcionar únicamente como estructura técnica para comprobar rutas.

No utilices PrimeNG en esta fase.

---

# 12. Rutas iniciales

Configura como mínimo:

```text
/
```

usando el layout público.

Y:

```text
/admin
```

usando el layout administrativo.

Las páginas pueden ser placeholders mínimos.

Por ejemplo:

```text
Public portfolio
```

y:

```text
Administration
```

No agregues todavía:

```text
/admin/login
/projects
/contact
/about
```

ni otras rutas de fases futuras.

---

# 13. Lazy loading

Cuando sea razonable, prepara las rutas para utilizar lazy loading.

No sobrearquitectes dos páginas placeholder únicamente para demostrar lazy loading.

Sin embargo, la arquitectura debe quedar preparada para que posteriormente:

- `features/public`
- `features/admin`

puedan cargarse independientemente.

Especialmente evita que futuras dependencias administrativas terminen automáticamente dentro del bundle público.

---

# 14. Styles

Utiliza SCSS.

Crea una base global mínima.

Puedes definir tokens iniciales solamente para necesidades universales, por ejemplo:

```scss
--font-sans
--color-background
--color-text
--content-max-width
```

No diseñes todavía un sistema visual completo.

No inventes:

- paleta final;
- tipografías finales;
- sombras;
- componentes;
- estilos editoriales definitivos.

Eso se definirá mediante `PUBLIC_UI.md` y las fases públicas posteriores.

Implementa únicamente:

- reset/base razonable;
- `box-sizing`;
- estilos básicos de `html` y `body`;
- fuente del sistema temporal;
- comportamiento de imágenes razonable;
- accesibilidad básica.

---

# 15. No utilizar fuentes externas todavía

No agregues Google Fonts ni otra dependencia de tipografía externa.

Usa temporalmente una pila de fuentes del sistema.

La tipografía visual definitiva se decidirá antes de implementar el diseño público.

---

# 16. Configuración de entornos

Prepara una estrategia simple para configuración frontend.

No agregues secretos.

Recuerda que cualquier configuración Angular enviada al navegador es pública.

En esta fase puede quedar preparada una configuración de aplicación para posteriormente definir:

```text
API_BASE_URL
```

pero NO integres todavía FastAPI.

No hagas ninguna petición HTTP al backend en esta fase.

La conexión real pertenece a la Fase 1.

---

# 17. HttpClient

Configura la infraestructura Angular necesaria para utilizar `HttpClient` posteriormente.

No crees todavía:

- API services;
- interceptors;
- authentication logic;
- error handlers de dominio.

Solo deja Angular preparado para poder incorporarlos en la Fase 1.

---

# 18. Testing

Utiliza el stack de testing oficialmente generado o recomendado por la versión de Angular utilizada.

No introduzcas un segundo framework de tests.

Agrega pruebas mínimas para verificar:

1. creación correcta de la aplicación;
2. renderizado de la ruta pública;
3. renderizado de `/admin`;
4. routing básico;
5. ausencia de errores esenciales en los layouts iniciales.

No escribas pruebas triviales excesivas.

---

# 19. SSR validation

Verifica explícitamente que el proyecto SSR:

- compila;
- inicia;
- puede renderizar `/`;
- puede renderizar `/admin`;
- no produce errores por acceso a `window`, `document`, `localStorage` u otras APIs exclusivas del navegador.

No agregues hacks para SSR.

No utilices comprobaciones innecesarias de plataforma donde todavía no hacen falta.

---

# 20. Accesibilidad inicial

Usa HTML semántico incluso en los placeholders.

El documento debe:

- tener un `lang` adecuado;
- contener títulos razonables;
- no eliminar focus outlines globalmente;
- no impedir navegación mediante teclado.

No hace falta una auditoría completa de accesibilidad en esta fase.

---

# 21. No implementar todavía

Está explícitamente prohibido en esta fase implementar:

- autenticación;
- login;
- refresh tokens;
- interceptors de autenticación;
- consumo de FastAPI;
- generación OpenAPI;
- CRUD;
- proyectos;
- media;
- R2;
- subida de archivos;
- dashboard;
- perfil;
- servicios;
- contacto;
- PrimeNG;
- diseño público final;
- animaciones;
- modelo 3D;
- SEO avanzado;
- analytics;
- Docker.

No anticipes fases futuras.

---

# 22. package.json

Revisa los scripts generados y deja comandos claros para desarrollo.

Como mínimo debe existir una forma documentada de ejecutar:

```bash
npm start
npm test
npm run build
npm run lint
npm run format:check
```

Si SSR requiere un comando distinto para validar el servidor generado, documenta cuál es.

No crees scripts redundantes.

---

# 23. README

Si existe `README.md`, actualízalo únicamente con la información necesaria para levantar esta base frontend.

Debe incluir de forma concisa:

- versión mínima/requerida de Node;
- `npm install`;
- desarrollo local;
- tests;
- lint;
- formatting;
- build;
- SSR, si requiere un comando específico.

No documentes todavía funcionalidades que no existen.

---

# 24. Archivos generados

No modifiques manualmente archivos generados por Angular si no es necesario.

No agregues comentarios generados o boilerplate innecesario.

Elimina contenido demo que no tenga valor para el proyecto.

---

# 25. Estado de PLANS.md

Al comenzar:

```text
Phase 0 — Angular Foundation / Bootstrap
Status: IN PROGRESS
```

Solo cambia a:

```text
COMPLETED
```

si todos los criterios de aceptación de la Fase 0 se cumplen.

No modifiques el estado de la Fase 1.

---

# 26. Validaciones obligatorias

Antes de declarar la fase terminada ejecuta:

1. instalación limpia de dependencias según corresponda;
2. tests;
3. ESLint;
4. formatting check;
5. TypeScript/build;
6. production build;
7. validación SSR.

No ignores errores.

No desactives reglas para conseguir artificialmente que las validaciones pasen.

Corrige las causas reales de los errores introducidos en esta fase.

---

# 27. Criterios de aceptación

La Fase 0 solo se considera completada cuando:

- Angular está correctamente inicializado;
- npm es el único package manager;
- Standalone Components están habilitados;
- Router funciona;
- SCSS está configurado;
- strict TypeScript está activo;
- strict template checking está activo;
- SSR funciona;
- `/` funciona;
- `/admin` funciona;
- existen layouts mínimos separados;
- HttpClient está preparado;
- ESLint funciona;
- formatting check funciona;
- tests pasan;
- production build pasa;
- SSR validation pasa;
- no existen dependencias innecesarias;
- no se implementaron funcionalidades de fases futuras;
- no se agregó Docker.

---

# 28. Informe final

Al terminar, informa:

## Environment

- Node version;
- npm version;
- Angular version;
- TypeScript version.

## Created

Archivos y estructuras importantes creadas.

## Modified

Archivos existentes modificados.

## Dependencies

Dependencias agregadas y por qué fueron necesarias.

## Routes

Rutas disponibles al finalizar la fase.

## Validation

Resultado de:

- tests;
- ESLint;
- formatting;
- TypeScript;
- production build;
- SSR.

## Architecture

Decisiones técnicas relevantes tomadas durante la inicialización.

## Issues

Problemas o limitaciones conocidas.

## Next phase

Indica únicamente qué queda preparado para la Fase 1.

No implementes la Fase 1.

No continúes automáticamente después del informe.


# Endpoint inventory

Paths include the API prefix. Generated from the running route contracts; see
`/openapi.json` for parameters and complete component definitions.

| Method | Path | Authentication | Success |
| --- | --- | --- | --- |
| GET | /api/v1/health | Public | 200 |
| POST | /api/v1/auth/login | Public | 200 |
| POST | /api/v1/auth/refresh | Public | 200 |
| POST | /api/v1/auth/logout | Public | 204 |
| GET | /api/v1/auth/me | Bearer | 200 |
| GET | /api/v1/admin/media | Bearer | 200 |
| POST | /api/v1/admin/media | Bearer | 201 |
| GET | /api/v1/admin/media/{asset_id} | Bearer | 200 |
| PATCH | /api/v1/admin/media/{asset_id} | Bearer | 200 |
| DELETE | /api/v1/admin/media/{asset_id} | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/sections | Bearer | 200 |
| POST | /api/v1/admin/projects/{project_id}/sections | Bearer | 201 |
| PUT | /api/v1/admin/projects/{project_id}/sections/order | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/sections/{section_id} | Bearer | 200 |
| PATCH | /api/v1/admin/projects/{project_id}/sections/{section_id} | Bearer | 200 |
| DELETE | /api/v1/admin/projects/{project_id}/sections/{section_id} | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/sections/{section_id}/media | Bearer | 200 |
| POST | /api/v1/admin/projects/{project_id}/sections/{section_id}/media | Bearer | 201 |
| PUT | /api/v1/admin/projects/{project_id}/sections/{section_id}/media/order | Bearer | 204 |
| PATCH | /api/v1/admin/projects/{project_id}/sections/{section_id}/media/{media_id} | Bearer | 200 |
| DELETE | /api/v1/admin/projects/{project_id}/sections/{section_id}/media/{media_id} | Bearer | 204 |
| GET | /api/v1/admin/projects | Bearer | 200 |
| POST | /api/v1/admin/projects | Bearer | 201 |
| PUT | /api/v1/admin/projects/order | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id} | Bearer | 200 |
| PATCH | /api/v1/admin/projects/{project_id} | Bearer | 200 |
| DELETE | /api/v1/admin/projects/{project_id} | Bearer | 204 |
| GET | /api/v1/admin/categories | Bearer | 200 |
| POST | /api/v1/admin/categories | Bearer | 201 |
| GET | /api/v1/admin/categories/{item_id} | Bearer | 200 |
| PATCH | /api/v1/admin/categories/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/categories/{item_id} | Bearer | 204 |
| GET | /api/v1/admin/tags | Bearer | 200 |
| POST | /api/v1/admin/tags | Bearer | 201 |
| GET | /api/v1/admin/tags/{item_id} | Bearer | 200 |
| PATCH | /api/v1/admin/tags/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/tags/{item_id} | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/categories | Bearer | 200 |
| PUT | /api/v1/admin/projects/{project_id}/categories | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/tags | Bearer | 200 |
| PUT | /api/v1/admin/projects/{project_id}/tags | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/attributes | Bearer | 200 |
| POST | /api/v1/admin/projects/{project_id}/attributes | Bearer | 201 |
| PUT | /api/v1/admin/projects/{project_id}/attributes/order | Bearer | 204 |
| PATCH | /api/v1/admin/projects/{project_id}/attributes/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/projects/{project_id}/attributes/{item_id} | Bearer | 204 |
| GET | /api/v1/admin/projects/{project_id}/media | Bearer | 200 |
| POST | /api/v1/admin/projects/{project_id}/media | Bearer | 201 |
| PUT | /api/v1/admin/projects/{project_id}/media/order | Bearer | 204 |
| PATCH | /api/v1/admin/projects/{project_id}/media/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/projects/{project_id}/media/{item_id} | Bearer | 204 |
| PUT | /api/v1/admin/projects/{project_id}/cover | Bearer | 200 |
| GET | /api/v1/admin/profile | Bearer | 200 |
| POST | /api/v1/admin/profile | Bearer | 201 |
| PATCH | /api/v1/admin/profile | Bearer | 200 |
| GET | /api/v1/admin/profile/social-links | Bearer | 200 |
| POST | /api/v1/admin/profile/social-links | Bearer | 201 |
| PUT | /api/v1/admin/profile/social-links/order | Bearer | 204 |
| GET | /api/v1/admin/profile/social-links/{item_id} | Bearer | 200 |
| PATCH | /api/v1/admin/profile/social-links/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/profile/social-links/{item_id} | Bearer | 204 |
| GET | /api/v1/admin/services | Bearer | 200 |
| POST | /api/v1/admin/services | Bearer | 201 |
| PUT | /api/v1/admin/services/order | Bearer | 204 |
| GET | /api/v1/admin/services/{item_id} | Bearer | 200 |
| PATCH | /api/v1/admin/services/{item_id} | Bearer | 200 |
| DELETE | /api/v1/admin/services/{item_id} | Bearer | 204 |
| GET | /api/v1/admin/site-settings | Bearer | 200 |
| GET | /api/v1/admin/site-settings/{key} | Bearer | 200 |
| PUT | /api/v1/admin/site-settings/{key} | Bearer | 200 |
| POST | /api/v1/public/contact | Public | 201 |
| GET | /api/v1/admin/contact-messages | Bearer | 200 |
| GET | /api/v1/admin/contact-messages/{item_id} | Bearer | 200 |
| PATCH | /api/v1/admin/contact-messages/{item_id}/status | Bearer | 200 |
| GET | /api/v1/public/projects | Public | 200 |
| GET | /api/v1/public/featured-projects | Public | 200 |
| GET | /api/v1/public/projects/{slug} | Public | 200 |
| GET | /api/v1/public/categories | Public | 200 |
| GET | /api/v1/public/tags | Public | 200 |
| GET | /api/v1/public/profile | Public | 200 |
| GET | /api/v1/public/services | Public | 200 |
| GET | /api/v1/public/social-links | Public | 200 |
| GET | /api/v1/public/site-settings | Public | 200 |
| POST | /api/v1/admin/media/uploads/presign | Admin | 200 |
| POST | /api/v1/admin/media/uploads/confirm | Admin | 200 |
| PUT | /api/v1/admin/media/uploads/{upload_id}/content | Admin | 204 |
| DELETE | /api/v1/admin/media/uploads/{upload_id} | Admin | 204 |
| GET | /api/v1/admin/media/{asset_id}/content | Admin | 200 / 307 |
| GET | /api/v1/public/media/{asset_id}/content | Public reference required | 200 / 307 |
