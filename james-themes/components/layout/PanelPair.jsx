import './layout.css';

// Two FindingPanels side by side; stacks when narrow
export function PanelPair({ children }) {
  return <div className="jt-pair">{children}</div>;
}
