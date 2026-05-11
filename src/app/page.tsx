import { contacts, enrollments, messages, sequences } from "@/lib/repo";

export default function Home() {
  const cs = contacts.list();
  const ss = sequences.list();
  const es = enrollments.list();
  const recent = messages.recent(10) as Array<{
    handle: string;
    body: string;
    status: string;
    error: string | null;
    sent_at: number;
  }>;

  const active = es.filter((e) => e.status === "active").length;
  const failed = es.filter((e) => e.status === "failed").length;
  const done = es.filter((e) => e.status === "completed").length;

  return (
    <div>
      <h1>Overview</h1>
      <div className="panel">
        <div className="row">
          <Stat label="Contacts" value={cs.length} />
          <Stat label="Sequences" value={ss.length} />
          <Stat label="Active" value={active} />
          <Stat label="Completed" value={done} />
          <Stat label="Failed" value={failed} />
        </div>
      </div>

      <h2>Recent messages</h2>
      <div className="panel">
        {recent.length === 0 ? (
          <p className="muted">No messages sent yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Handle</th>
                <th>Status</th>
                <th>Body</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((m, i) => (
                <tr key={i}>
                  <td>{new Date(m.sent_at * 1000).toLocaleString()}</td>
                  <td>@{m.handle}</td>
                  <td>
                    <span className={`badge ${m.status === "sent" ? "ok" : "failed"}`}>
                      {m.status}
                    </span>
                  </td>
                  <td>{m.body.slice(0, 80)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 12 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
    </div>
  );
}
