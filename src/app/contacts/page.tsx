import { revalidatePath } from "next/cache";
import { contacts } from "@/lib/repo";

async function addContact(formData: FormData) {
  "use server";
  const handle = String(formData.get("handle") ?? "").trim();
  if (!handle) return;
  const display_name = String(formData.get("display_name") ?? "").trim() || undefined;
  const notes = String(formData.get("notes") ?? "").trim() || undefined;
  contacts.create(handle, display_name, notes);
  revalidatePath("/contacts");
}

async function deleteContact(formData: FormData) {
  "use server";
  const id = Number(formData.get("id"));
  contacts.delete(id);
  revalidatePath("/contacts");
}

export default function ContactsPage() {
  const list = contacts.list();
  return (
    <div>
      <h1>Contacts</h1>

      <div className="panel">
        <h2>Add contact</h2>
        <form action={addContact} className="stack">
          <input name="handle" placeholder="@handle" required />
          <input name="display_name" placeholder="Display name (optional)" />
          <textarea name="notes" placeholder="Notes (optional)" />
          <div>
            <button type="submit">Add contact</button>
          </div>
        </form>
      </div>

      <div className="panel">
        <h2>All contacts ({list.length})</h2>
        {list.length === 0 ? (
          <p className="muted">No contacts yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Handle</th>
                <th>Name</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.id}>
                  <td>@{c.handle}</td>
                  <td>{c.display_name ?? <span className="muted">—</span>}</td>
                  <td>{c.notes ?? <span className="muted">—</span>}</td>
                  <td style={{ textAlign: "right" }}>
                    <form action={deleteContact}>
                      <input type="hidden" name="id" value={c.id} />
                      <button className="ghost" type="submit">
                        Delete
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
