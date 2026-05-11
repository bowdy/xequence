import { notFound } from "next/navigation";
import { revalidatePath } from "next/cache";
import { contacts, enrollments, sequences } from "@/lib/repo";

async function saveSteps(formData: FormData) {
  "use server";
  const id = Number(formData.get("sequence_id"));
  const delays = formData.getAll("delay_hours").map((v) => Number(v));
  const bodies = formData.getAll("body").map((v) => String(v));
  const steps = bodies
    .map((body, i) => ({ body: body.trim(), delay_hours: Math.max(0, delays[i] ?? 0) }))
    .filter((s) => s.body.length > 0);
  sequences.replaceSteps(id, steps);
  revalidatePath(`/sequences/${id}`);
}

async function enroll(formData: FormData) {
  "use server";
  const sequence_id = Number(formData.get("sequence_id"));
  const contact_id = Number(formData.get("contact_id"));
  enrollments.enroll(contact_id, sequence_id);
  revalidatePath(`/sequences/${sequence_id}`);
  revalidatePath(`/enrollments`);
}

export default async function SequenceDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const sequenceId = Number(id);
  const seq = sequences.get(sequenceId);
  if (!seq) notFound();

  const steps = sequences.steps(sequenceId);
  // Pad with one empty step so the user always has a slot to fill.
  const editorSteps = steps.length
    ? steps.map((s) => ({ delay_hours: s.delay_hours, body: s.body }))
    : [{ delay_hours: 0, body: "" }];
  editorSteps.push({ delay_hours: 24, body: "" });

  const allContacts = contacts.list();

  return (
    <div>
      <h1>{seq.name}</h1>
      {seq.description && <p className="muted">{seq.description}</p>}

      <div className="panel">
        <h2>Steps</h2>
        <p className="muted">
          Use <code>{"{{ name }}"}</code> or <code>{"{{ handle }}"}</code> in the message body.
          Step 1's delay is measured from enrollment time; later steps are measured from the
          previous step.
        </p>
        <form action={saveSteps} className="stack">
          <input type="hidden" name="sequence_id" value={seq.id} />
          {editorSteps.map((s, i) => (
            <div key={i} className="step">
              <header>
                <strong>Step {i + 1}</strong>
                <label className="muted" style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  Delay (hours)
                  <input
                    type="number"
                    name="delay_hours"
                    defaultValue={s.delay_hours}
                    min={0}
                    style={{ width: 90 }}
                  />
                </label>
              </header>
              <textarea name="body" defaultValue={s.body} placeholder="Message body…" />
            </div>
          ))}
          <div>
            <button type="submit">Save steps</button>
            <span className="muted" style={{ marginLeft: 8 }}>
              Empty trailing steps are ignored. Save again to add another slot.
            </span>
          </div>
        </form>
      </div>

      <div className="panel">
        <h2>Enroll a contact</h2>
        {allContacts.length === 0 ? (
          <p className="muted">Add a contact first.</p>
        ) : (
          <form action={enroll} className="row">
            <input type="hidden" name="sequence_id" value={seq.id} />
            <select name="contact_id" required>
              {allContacts.map((c) => (
                <option key={c.id} value={c.id}>
                  @{c.handle}
                  {c.display_name ? ` — ${c.display_name}` : ""}
                </option>
              ))}
            </select>
            <button type="submit">Enroll</button>
          </form>
        )}
      </div>
    </div>
  );
}
