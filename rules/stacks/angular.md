## Stack: Angular

The TypeScript rules above apply too.

- **NG-1 [tool]** Components stay standalone and `OnPush`, Angular's defaults: never opt out with `ChangeDetectionStrategy.Eager`.
- **NG-2 [tool]** Dependencies come from `inject()`, not constructor parameters.
- **NG-3 [tool]** State is signals (`signal`, `computed`, `input()`, `output()`), not decorators and setters.
- **NG-4 [tool]** Templates use `@if`, `@for` and `@switch`; `@for` always has `track`.
- **NG-5 [review]** Components only present. Validation, transformation and data access live in services or plain functions, and complex template logic becomes a `computed`.
- **NG-6 [review]** Members used only by the template are `protected`; inputs, outputs, models and queries are `readonly`.
- **NG-7 [review]** Event handlers are named for what they do (`saveDraft()`), not for the event (`onClick()`).
- **NG-8 [review]** One concept per file (a component, a directive or a service), named in kebab-case after it. Folders by feature, not by type (no `components/` or `services/`), with specs next to the code.
- **NG-9 [review]** `class` and `style` bindings instead of `NgClass` and `NgStyle`; lifecycle hooks stay short and call well-named methods.
- **NG-10 [review]** Long-lived subscriptions end with the component (`takeUntilDestroyed`, the `async` pipe, `toSignal`); one-shot HTTP calls need nothing.
- **NG-11 [tool]** Never call `DomSanitizer.bypassSecurityTrust*`, and never touch `innerHTML` or `outerHTML` through an element: bind in the template so Angular sanitizes the value.
- **NG-12 [review]** Never store access tokens, refresh tokens or personal data in `localStorage` or `sessionStorage`, because one XSS reads all of it. Keep tokens in memory, or in an `HttpOnly`, `Secure` cookie.

| Task | Command |
| --- | --- |
| Everything CI runs | `npm run check` |
| Auto-fix format + lint | `npm run fix` |
| Run the app | `npm start` |
| Tests (watch) | `npx ng test` |
