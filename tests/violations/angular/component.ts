// expect: @angular-eslint/prefer-inject, @angular-eslint/prefer-signals, @angular-eslint/prefer-on-push-component-change-detection, @angular-eslint/template/prefer-control-flow
import { ChangeDetectionStrategy, Component, Input } from "@angular/core";

import { Clock } from "./greetings/clock";

/** Breaks the NG rules on purpose. */
@Component({
  selector: "app-legacy",
  template: `<p *ngIf="name">{{ name }}</p>`,
  changeDetection: ChangeDetectionStrategy.Eager,
})
export class Legacy {
  @Input() name = "";

  constructor(private readonly clock: Clock) {}
}
