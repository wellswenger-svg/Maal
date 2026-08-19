import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App.jsx";
import PinGate from "./PinGate.jsx";
import "./index.css";

// Auto-apply new builds: PWA otherwise keeps the previous JS (no Controls).
const updateSW = registerSW({
  immediate: true,
  onNeedRefresh() {
    updateSW?.(true);
  },
  onRegisteredSW(_swUrl, registration) {
    if (!registration) return;
    const ping = () => registration.update().catch(() => {});
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") ping();
    });
    window.setInterval(ping, 60_000);
  },
});

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <PinGate>
      <App />
    </PinGate>
  </StrictMode>
);
