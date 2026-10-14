import { Injectable } from "@angular/core";

/** The current time, behind a service so tests can stop it (TST-4). */
@Injectable({ providedIn: "root" })
export class Clock {
  /** Returns the current moment. */
  now(): Date {
    return new Date();
  }
}
