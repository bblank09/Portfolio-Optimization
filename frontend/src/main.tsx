import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BacktestWorkspace } from "./pages/BacktestWorkspace";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BacktestWorkspace />
  </StrictMode>
);
