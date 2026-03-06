import type { ReactNode } from "react";

type LayoutShellProps = {
  children: ReactNode;
  lastUpdated: string | null;
  onRefresh: () => void;
  statusError: string | null;
};

export function LayoutShell(props: LayoutShellProps) {
  return (
    <div className="layout-shell">
      <header className="top-bar">
        <div>
          <h1>Portable AI Drive Control Center</h1>
          <p>Dashboard v0.1 - internal developer/testing cockpit</p>
        </div>
        <div className="top-bar-actions">
          <button onClick={props.onRefresh}>Refresh</button>
          <div className="stamp">{props.lastUpdated ? `Updated ${props.lastUpdated}` : "Not loaded"}</div>
        </div>
      </header>

      {props.statusError ? <div className="global-error">Backend unavailable: {props.statusError}</div> : null}

      <main className="dashboard-grid">{props.children}</main>
    </div>
  );
}
