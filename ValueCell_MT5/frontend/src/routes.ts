import {
  index,
  layout,
  prefix,
  type RouteConfig,
  route,
} from "@react-router/dev/routes";

export default [
  index("app/redirect-to-home.tsx"),

  ...prefix("/home", [
    layout("app/home/_layout.tsx", [
      index("app/home/home.tsx"),
      route("/stock/:stockId", "app/home/stock.tsx"),
    ]),
  ]),

  route("/market", "app/market/agents.tsx"),

  ...prefix("/mt5", [
    layout("app/mt5/_layout.tsx", [
      index("app/mt5/dashboard.tsx"),
      route("/trades", "app/mt5/trades.tsx"),
      route("/rongsokan", "app/mt5/rongsokan.tsx"),
      route("/performance", "app/mt5/performance.tsx"),
      route("/agents", "app/mt5/agents.tsx"),
      route("/settings", "app/mt5/settings.tsx"),
      route("/database", "app/mt5/database.tsx"),
      route("/replay", "app/mt5/replay.tsx"),
    ]),
  ]),
  
  route("/test-mt5", "app/test-mt5.tsx"),

  // route("/ranking", "app/rank/board.tsx"),

  ...prefix("/agent", [
    route("/:agentName", "app/agent/chat.tsx"),
    route("/:agentName/config", "app/agent/config.tsx"),
  ]),

  ...prefix("/setting", [
    layout("app/setting/_layout.tsx", [
      index("app/setting/models.tsx"),
      route("/general", "app/setting/general.tsx"),
      route("/memory", "app/setting/memory.tsx"),
    ]),
  ]),

  // router for test components
  route("/test", "app/test.tsx"),
] satisfies RouteConfig;
