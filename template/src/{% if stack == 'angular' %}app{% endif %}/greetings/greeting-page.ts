import { Component, computed, inject, signal } from "@angular/core";

import { Clock } from "./clock";
import { buildGreeting } from "./greeting";

/** Asks for a name and greets it for the current time of day. */
@Component({
  selector: "app-greeting-page",
  templateUrl: "./greeting-page.html",
})
export class GreetingPage {
  private readonly clock = inject(Clock);

  protected readonly name = signal("");
  protected readonly greeting = computed(() =>
    buildGreeting(this.name(), this.clock.now().getHours()),
  );

  /** Keeps the name in step with the input field. */
  protected updateName(event: Event): void {
    this.name.set((event.target as HTMLInputElement).value);
  }
}
