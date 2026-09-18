import { useEffect, useState } from "react";
import { PageHeader, DataTable, Modal, Field, Input, Select, Button, StatusPill, useCRUD } from "./_shared";
import { api, fmtDate, fmtIDR, formatErr } from "@/lib/api";
import { toast } from "sonner";

export default function CRM() {
  const { rows: customers } = useCRUD("customers");
  const { rows: activities, save: saveActivity, reload } = useCRUD("crm_activities");
  const [orders, setOrders] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  useEffect(() => { api.get("/sales_orders").then((response) => setOrders(response.data)).catch(() => {}); }, []);
  const customerActivities = activities.filter((item) => item.customer_id === selected?.id);
  const customerOrders = orders.filter((item) => item.customer_id === selected?.id);
  const addActivity = async () => {
    if (await saveActivity({ ...form, customer_id: selected.id, status: "open" }, form.id)) {
      setForm(null);
      reload();
    }
  };
  return (
    <div>
      <PageHeader title="Light CRM" subtitle="Customer relationships & follow-ups" />
      <div className="grid lg:grid-cols-[1fr_380px] gap-4">
        <DataTable rows={customers} columns={[
          { header: "Customer", cell: (row) => <button className="font-semibold text-left hover:underline" onClick={() => setSelected(row)}>{row.name}</button> },
          { header: "Contact", cell: (row) => row.phone ? <a className="text-blue-600 hover:underline" href={`https://wa.me/${String(row.phone).replace(/\D/g, "")}`} target="_blank" rel="noreferrer">{row.phone}</a> : row.email || "-" },
          { header: "Segment", cell: (row) => <StatusPill status={row.customer_type || "new"} /> },
          { header: "Orders", cell: (row) => row.total_orders || 0 },
          { header: "Lifetime value", cell: (row) => fmtIDR(row.total_spending || 0) },
          { header: "Last order", cell: (row) => fmtDate(row.last_order) },
        ]} />
        {selected && <div className="p-5 rounded-lg border border-border bg-card h-fit space-y-4">
          <div><div className="text-xs text-muted-foreground">Customer</div><h2 className="text-xl font-bold">{selected.name}</h2><p className="text-sm">{selected.email || "-"} · {selected.phone || "-"}</p></div>
          {selected.phone && <a className="block text-center px-3 py-2 rounded-md bg-emerald-600 text-white text-sm font-semibold" href={`https://wa.me/${String(selected.phone).replace(/\D/g, "")}`} target="_blank" rel="noreferrer">Chat via WhatsApp</a>}
          <div className="grid grid-cols-2 gap-2 text-sm"><Summary label="Orders" value={selected.total_orders || 0} /><Summary label="Value" value={fmtIDR(selected.total_spending || 0)} /></div>
          <div><b>Order history</b>{customerOrders.slice(0, 5).map((order) => <div key={order.id} className="border-t pt-2 mt-2 text-sm flex justify-between"><span>{order.order_number}<br /><span className="text-xs text-muted-foreground">{fmtDate(order.date)}</span></span><b>{fmtIDR(order.total)}</b></div>)}{customerOrders.length === 0 && <div className="text-sm text-muted-foreground mt-2">No orders yet.</div>}</div>
          <div className="flex justify-between items-center"><b>Activities</b><Button variant="outline" onClick={() => setForm({ type: "note", subject: "", description: "", due_date: "" })}>+ Activity</Button></div>
          {customerActivities.map((activity) => <div key={activity.id} className="border-t pt-2 text-sm"><div className="font-semibold">{activity.subject || activity.type}</div><div>{activity.description}</div><div className="text-xs text-muted-foreground">{fmtDate(activity.due_date)} · {activity.status}</div></div>)}
        </div>}
      </div>
      {form && <Modal open onClose={() => setForm(null)} title="Customer activity"><div className="space-y-3">
        <Field label="Type"><Select value={form.type} onChange={(event) => setForm({ ...form, type: event.target.value })}><option value="note">Note</option><option value="call">Call</option><option value="task">Task</option><option value="follow_up">Follow-up</option></Select></Field>
        <Field label="Subject"><Input value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} /></Field>
        <Field label="Description"><Input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
        <Field label="Due date"><Input type="date" value={form.due_date} onChange={(event) => setForm({ ...form, due_date: event.target.value })} /></Field>
        <Button onClick={addActivity}>Save</Button>
      </div></Modal>}
    </div>
  );
}

function Summary({ label, value }) {
  return <div className="p-2 bg-stone-100 dark:bg-stone-900 rounded"><div className="text-xs text-muted-foreground">{label}</div><b>{value}</b></div>;
}
