import type { Routes } from "@angular/router";

import { GreetingPage } from "./greetings/greeting-page";

/** One route per feature page. */
export const routes: Routes = [{ path: "", component: GreetingPage }];
