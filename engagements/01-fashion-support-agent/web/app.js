const $ = (id) => document.getElementById(id);
let conversationId = null;
let turnNo = 0;

function addMessage(text, who, extra = "") {
  const div = document.createElement("div");
  div.className = `msg ${who} ${extra}`.trim();
  div.textContent = text;
  $("messages").appendChild(div);
  $("messages").scrollTop = $("messages").scrollHeight;
  return div;
}

function pretty(value) {
  try { return JSON.stringify(typeof value === "string" ? JSON.parse(value) : value, null, 2); }
  catch { return String(value); }
}

function renderTurn(turn) {
  turnNo += 1;
  const box = document.createElement("div");
  box.className = "turn";
  const u = turn.usage;
  box.innerHTML = `<strong>Turn ${turnNo}</strong>
    <div class="turn-meta">
      <span>stop: ${turn.stop_reason}</span><span>requests: ${turn.api_requests}</span>
      <span>in: ${u.input_tokens}</span><span>out: ${u.output_tokens}</span>
      <span>cache read: ${u.cache_read_input_tokens}</span>
      <span>cost: $${turn.cost_usd.toFixed(5)}</span><span>${turn.latency_ms} ms</span>
    </div>`;
  for (const call of turn.tool_calls) {
    const t = document.createElement("div");
    t.className = "tool";
    const name = document.createElement("div");
    name.className = `name ${call.is_error ? "error" : "ok"}`;
    name.textContent = `${call.name}${call.is_error ? " (error)" : ""}`;
    const input = document.createElement("pre");
    input.textContent = "input: " + pretty(call.input);
    const out = document.createElement("pre");
    out.textContent = "result: " + pretty(call.content);
    t.append(name, input, out);
    box.appendChild(t);
  }
  $("turns").prepend(box);
}

$("composer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("input").value.trim();
  if (!text) return;
  $("input").value = "";
  addMessage(text, "user");
  const pending = addMessage("…", "bot", "pending");
  $("composer").querySelector("button").disabled = true;
  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message: text }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    conversationId = body.conversation_id;
    pending.remove();
    addMessage(body.reply, "bot");
    renderTurn(body.turn);
  } catch (err) {
    pending.textContent = `Fehler: ${err.message}`;
  } finally {
    $("composer").querySelector("button").disabled = false;
    $("input").focus();
  }
});

$("reset").addEventListener("click", async () => {
  if (conversationId) {
    await fetch("/api/reset", { method: "POST", headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ conversation_id: conversationId }) });
  }
  conversationId = null; turnNo = 0;
  $("turns").innerHTML = "";
  $("messages").querySelectorAll(".msg:not(:first-child)").forEach((m) => m.remove());
});

$("hood-toggle").addEventListener("change", (e) => { $("hood").hidden = !e.target.checked; });
