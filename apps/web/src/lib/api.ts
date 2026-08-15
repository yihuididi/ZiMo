export interface HealthResponse {
  ok: boolean;
  service: string;
}

const apiBaseUrl = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${apiBaseUrl}/health`, {
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`API returned HTTP ${response.status}`);
  }

  const health = (await response.json()) as HealthResponse;

  if (health.ok !== true || health.service !== "mahjong-api") {
    throw new Error("API returned an unexpected health response");
  }

  return health;
}
