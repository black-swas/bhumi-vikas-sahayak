import {
  index,
  layout,
  route,
  type RouteConfig,
} from "@react-router/dev/routes";

export default [
  layout("routes/app-layout.tsx", [
    index("routes/ask.tsx"),
    route("rule/:ruleId", "routes/rule.tsx"),
    route("accuracy", "routes/accuracy.tsx"),
    route("limits", "routes/limits.tsx"),
    route("*", "routes/not-found.tsx"),
  ]),
  // The print slip has no rail and no evidence panel.
  route("slip/:turnId", "routes/slip.tsx"),
] satisfies RouteConfig;
