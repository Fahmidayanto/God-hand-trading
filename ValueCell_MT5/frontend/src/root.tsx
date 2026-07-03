import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Links, Meta, Outlet, Scripts, ScrollRestoration, useLocation } from "react-router";
import "@/i18n";
import AppSidebar from "@/components/valuecell/app/app-sidebar";
import { useLanguage } from "@/store/settings-store";
import { Toaster } from "./components/ui/sonner";

import "./global.css";
import { SidebarProvider } from "./components/ui/sidebar";

export function Layout({ children }: { children: React.ReactNode }) {
  const language = useLanguage();
  const htmlLang =
    {
      en: "en",
      zh_CN: "zh-CN",
      zh_TW: "zh-TW",
      ja: "ja",
    }[language] ?? "en";

  return (
    <html lang={htmlLang} suppressHydrationWarning>
      <head>
        <meta charSet="UTF-8" />
        <link rel="icon" type="image/svg+xml" href="/logo.svg" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>God Hand Trading</title>
        <link 
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" 
          rel="stylesheet" 
        />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // Global default 5 minutes fresh time
      gcTime: 30 * 60 * 1000, // Global default 30 minutes garbage collection time
      refetchOnWindowFocus: false, // Don't refetch on window focus by default
      retry: 1, // Default retry 1 times on failure
    },
    mutations: {
      retry: 1, // Default retry 1 time for mutations
    },
  },
});

import { AutoUpdateCheck } from "@/components/valuecell/app/auto-update-check";
import { BackendHealthCheck } from "@/components/valuecell/app/backend-health-check";
import { TrackerProvider } from "./provider/tracker-provider";

export default function Root() {
  const location = useLocation();
  const isMT5 = location.pathname.startsWith("/mt5");

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        enableColorScheme
        storageKey="godhand-theme"
      >
        <BackendHealthCheck>
          <TrackerProvider>
            <SidebarProvider>
              <div className="fixed flex size-full overflow-hidden">
                {!isMT5 && <AppSidebar />}

                <main
                  className="relative flex flex-1 overflow-hidden"
                  id="main-content"
                >
                  <Outlet />
                </main>
                <Toaster />
              </div>
            </SidebarProvider>
          </TrackerProvider>
          <AutoUpdateCheck />
        </BackendHealthCheck>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
