import Link from "next/link";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { sequences } from "@/lib/repo";

async function createSequence(formData: FormData) {
  "use server";
  const name = String(formData.get("name") ?? "").trim();
  if (!name) return;
  const description = String(formData.get("description") ?? "").trim() || undefined;
  const seq = sequences.create(name, description);
  revalidatePath("/sequences");
  redirect(`/sequences/${seq.id}`);
}

async function deleteSequence(formData: FormData) {
  "use server";
  sequences.delete(Number(formData.get("id")));
  revalidatePath("/sequences");
}

export default function SequencesPage() {
  const list = sequences.list();
  return (
    <div>
      <h1>Sequences</h1>

      <div className="panel">
        <h2>New sequence</h2>
        <form action={createSequence} className="stack">
          <input name="name" placeholder="Sequence name" required />
          <input name="description" placeholder="Description (optional)" />
          <div>
            <button type="submit">Create</button>
          </div>
        </form>
      </div>

      <div className="panel">
        <h2>All sequences ({list.length})</h2>
        {list.length === 0 ? (
          <p className="muted">No sequences yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Steps</th>
                <th>Description</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => {
                const steps = sequences.steps(s.id);
                return (
                  <tr key={s.id}>
                    <td>
                      <Link href={`/sequences/${s.id}`}>{s.name}</Link>
                    </td>
                    <td>{steps.length}</td>
                    <td>{s.description ?? <span className="muted">—</span>}</td>
                    <td style={{ textAlign: "right" }}>
                      <form action={deleteSequence}>
                        <input type="hidden" name="id" value={s.id} />
                        <button className="ghost" type="submit">
                          Delete
                        </button>
                      </form>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
