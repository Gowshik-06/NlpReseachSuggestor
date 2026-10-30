interface StatusRowProps {
  label: string;
  ok: boolean;
  value: string;
}

export default function StatusRow({ label, ok, value }: StatusRowProps) {
  return (
    <div className="status-row">
      <span className="status-label">{label}</span>
      <span className={ok ? "status-ok" : "status-fail"}>
        {ok ? "✓" : "✗"} {value}
      </span>
    </div>
  );
}
