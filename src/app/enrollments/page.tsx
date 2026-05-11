import { revalidatePath } from "next/cache";
import { enrollments } from "@/lib/repo";

async function pause(formData: FormData) {
  "use server";
  enrollments.pause(Number(formData.get("id")));
  revalidatePath("/enrollments");
}

async function resume(formData: FormData) {
  "use server";
  enrollments.resume(Number(formData.get("id")));
  revalidatePath("/enrollments");
}

async function remove(formData: FormData) {
  "use server";
  enrollments.delete(Number(formData.get("id")));
  revalidatePath("/enrollments");
}

export default function EnrollmentsPage() {
  const list = enrollments.list();
  return (
    <div>
      <h1>Enrollments</h1>
      <div className="panel">
        {list.length === 0 ? (
          <p className="muted">No enrollments yet. Enroll a contact from a sequence page.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Handle</th>
                <th>Sequence</th>
                <th>Status</th>
                <th>Next step</th>
                <th>Next run</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((e) => (
                <tr key={e.id}>
                  <td>@{e.handle}</td>
                  <td>{e.sequence_name}</td>
                  <td>
                    <span
                      className={`badge ${
                        e.status === "active"
                          ? "ok"
                          : e.status === "failed"
                            ? "failed"
                            : e.status === "paused"
                              ? "paused"
                              : ""
                      }`}
                    >
                      {e.status}
                    </span>
                  </td>
                  <td>{e.next_step_order}</td>
                  <td>
                    {e.status === "active"
                      ? new Date(e.next_run_at * 1000).toLocaleString()
                      : "—"}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    {e.status === "active" && (
                      <form action={pause} style={{ display: "inline" }}>
                        <input type="hidden" name="id" value={e.id} />
                        <button className="ghost" type="submit">
                          Pause
                        </button>
                      </form>
                    )}
                    {e.status === "paused" && (
                      <form action={resume} style={{ display: "inline" }}>
                        <input type="hidden" name="id" value={e.id} />
                        <button className="ghost" type="submit">
                          Resume
                        </button>
                      </form>
                    )}
                    <form action={remove} style={{ display: "inline", marginLeft: 6 }}>
                      <input type="hidden" name="id" value={e.id} />
                      <button className="danger" type="submit">
                        Remove
                      </button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
