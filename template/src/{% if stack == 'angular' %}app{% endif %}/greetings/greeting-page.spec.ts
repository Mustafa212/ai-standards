import { TestBed } from "@angular/core/testing";

import { Clock } from "./clock";
import { GreetingPage } from "./greeting-page";

/** A clock stopped at 15:00, so the test never depends on the real time (TST-4). */
class AfternoonClock extends Clock {
  override now(): Date {
    return new Date(2026, 0, 1, 15, 0, 0);
  }
}

describe("GreetingPage", () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [GreetingPage],
      providers: [{ provide: Clock, useClass: AfternoonClock }],
    });
  });

  it("greets the name the user types", async () => {
    const fixture = TestBed.createComponent(GreetingPage);
    const page = fixture.nativeElement as HTMLElement;
    const input = page.querySelector<HTMLInputElement>('[data-testid="name"]');

    if (input === null) throw new Error("name input is missing");
    input.value = "Mostafa";
    input.dispatchEvent(new Event("input"));
    await fixture.whenStable();

    expect(page.querySelector('[data-testid="greeting"]')?.textContent).toBe("Hello, Mostafa!");
  });

  it("greets the world before anything is typed", async () => {
    const fixture = TestBed.createComponent(GreetingPage);
    await fixture.whenStable();

    const greeting = (fixture.nativeElement as HTMLElement).querySelector(
      '[data-testid="greeting"]',
    );
    expect(greeting?.textContent).toBe("Hello, world!");
  });
});
