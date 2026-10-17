// expect: no-restricted-properties
import type { SafeHtml, DomSanitizer } from "@angular/platform-browser";

/** Trusts raw HTML instead of letting Angular sanitize it (NG-11). */
export function trustHtml(sanitizer: DomSanitizer, html: string): SafeHtml {
  return sanitizer.bypassSecurityTrustHtml(html);
}
