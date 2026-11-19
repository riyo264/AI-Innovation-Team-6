import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { MockAuthProvider } from "./auth/MockAuth";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MockAuthProvider>
      <App />
    </MockAuthProvider>
  </StrictMode>,
);
