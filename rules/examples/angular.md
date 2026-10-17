# Break shapes: angular stack rules

What a break of a `[review]` rule usually looks like, for the audit's rule auditors. Never rendered
into AGENTS.md.

## NG-7

- Search: `\(\w+\)="on[A-Z]\w*\(`
- Break: `<button (click)="onClick()">`

## NG-9

- Search: `\[ngClass\]|\[ngStyle\]|\bNgClass\b|\bNgStyle\b`
- Break: `<li [ngClass]="{ active: isActive }">`

## NG-10

- Search: `\.subscribe\(`, then keep the ones in a component with no `takeUntilDestroyed`
- Break: `this.store.select(selectUser).subscribe(user => (this.user = user));`

## NG-12

- Search: `(localStorage|sessionStorage)\.setItem\(.*(token|jwt|auth|Token|Jwt|Auth)`
- Break: `localStorage.setItem("access_token", response.accessToken);`
