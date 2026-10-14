import { Component } from "@angular/core";
import { RouterOutlet } from "@angular/router";

/** The root component: renders the page the router picks. */
@Component({
  selector: "app-root",
  imports: [RouterOutlet],
  template: "<router-outlet />",
})
export class App {}
