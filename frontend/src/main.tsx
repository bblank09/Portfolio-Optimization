import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { OptimizeWorkspace } from "./pages/OptimizeWorkspace";
import "./styles.css";

// BacktestWorkspace.tsx (the sibling project's original 3-step flow) is
// kept in the tree unmodified for reference -- per CLAUDE.md, it is not
// deleted, just no longer the mounted root. See docs/mock-ui-spec.md.
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <OptimizeWorkspace />
  </StrictMode>
);
