export const appConfig = {
  name: "NovaNusa",
  title: "NovaNusa Dashboard",
  description: "Platform intelijen pengadaan berbasis bukti",
  url: process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000",
  apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:3000/api",
  environment: process.env.NODE_ENV ?? "development",
};

export type AppConfig = typeof appConfig;
