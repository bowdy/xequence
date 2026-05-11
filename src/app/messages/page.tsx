import { messages } from "@/lib/repo";

type Row = {
  id: number;
  handle: string;
  body: string;
  status: string;
  error: string | null;
  sent_at: number;
};

export default function MessagesPage() {
  const list = messages.recent(200) as Row[];
  return (
    <div>
      <h1>Messages</h1>
      <div className="panel">
        {list.length === 0 ? (
          <p className="muted">No messages logged yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Handle</th>
                <th>Status</th>
                <th>Body</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {list.map((m) => (
                <tr key={m.id}>
                  <td>{new Date(m.sent_at * 1000).toLocaleString()}</td>
                  <td>@{m.handle}</td>
                  <td>
                    <span className={`badge ${m.status === "sent" ? "ok" : "failed"}`}>
                      {m.status}
                    </span>
                  </td>
                  <td style={{ maxWidth: 480 }}>{m.body}</td>
                  <td className="muted">{m.error ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
