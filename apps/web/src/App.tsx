import { useState } from "react";

import { getHealth } from "./lib/api";

type ApiStatus = "not tested" | "testing" | "OK" | "failed";

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("not tested");
  const [error, setError] = useState<string | null>(null);

  async function testApi() {
    setApiStatus("testing");
    setError(null);

    try {
      await getHealth();
      setApiStatus("OK");
    } catch (reason) {
      setApiStatus("failed");
      setError(reason instanceof Error ? reason.message : "Unknown error");
    }
  }

  return (
    <main className="status-card">
      <h1>Mahjong</h1>
      <dl>
        <div>
          <dt>Frontend:</dt>
          <dd className="status-ok">OK</dd>
        </div>
        <div>
          <dt>API:</dt>
          <dd className={apiStatus === "OK" ? "status-ok" : undefined}>
            {apiStatus}
          </dd>
        </div>
      </dl>
      <button type="button" onClick={testApi} disabled={apiStatus === "testing"}>
        {apiStatus === "testing" ? "Testing…" : "Test API"}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </main>
  );
}

export default App;
