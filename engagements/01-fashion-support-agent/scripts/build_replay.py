"""Build a self-contained static replay page from recorded eval runs (no API calls when viewing).

CLI: python -m scripts.build_replay --run evals/results/published/<run_id> --ids a,b,c --out demo/index.html
"""
import argparse
import json
from pathlib import Path

_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fadenwerk Agent Replay</title>
<style>
:root{--bg:#f6f4f1;--surface:#fff;--ink:#1f1d1a;--muted:#6b665f;--accent:#7a3e2b;--line:#e4dfd8;--bot:#f1ece6;
--user:#7a3e2b;--user-ink:#fff;--err:#a3261e;--ok:#2f6b3b}
@media (prefers-color-scheme:dark){:root{--bg:#151412;--surface:#1e1c1a;--ink:#f0ece6;--muted:#a39d94;
--accent:#d08a6c;--line:#34302c;--bot:#2a2724;--user:#9c5238;--err:#ff8a80;--ok:#8fd19e}}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
.banner{background:var(--accent);color:#fff;text-align:center;font-size:13px;padding:6px 16px}
header{max-width:1200px;margin:0 auto;padding:20px 16px 4px}
header h1{margin:0 0 4px;font-size:22px}
header p{margin:0;color:var(--muted);max-width:760px}
.picker{max-width:1200px;margin:12px auto 0;padding:0 16px;display:flex;flex-wrap:wrap;gap:8px}
.picker button{font:inherit;font-size:13px;padding:6px 12px;border-radius:999px;border:1px solid var(--line);
background:var(--surface);color:var(--ink);cursor:pointer}
.picker button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.layout{display:flex;gap:16px;max-width:1200px;margin:0 auto;padding:16px}
.chat,.hood{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}
.chat{flex:1 1 560px;display:flex;flex-direction:column;gap:10px}
.hood{flex:0 1 440px;font-size:13px}
.hood h2{margin:0 0 8px;font-size:15px}
.msg{max-width:85%;padding:10px 14px;border-radius:14px;white-space:pre-wrap}
.msg.bot{background:var(--bot);align-self:flex-start;border-bottom-left-radius:4px}
.msg.user{background:var(--user);color:var(--user-ink);align-self:flex-end;border-bottom-right-radius:4px}
.verdict{font-size:13px;color:var(--muted)}
.verdict b.pass{color:var(--ok)}.verdict b.fail{color:var(--err)}
.turn{border-top:1px solid var(--line);padding:10px 0}
.meta{display:flex;flex-wrap:wrap;gap:4px 12px;color:var(--muted);font-variant-numeric:tabular-nums}
.tool{margin:6px 0;border:1px solid var(--line);border-radius:8px;padding:6px 8px}
.tool .name{font-weight:600}.tool .name.ok{color:var(--ok)}.tool .name.error{color:var(--err)}
pre{margin:4px 0 0;white-space:pre-wrap;word-break:break-word;font-size:12px;background:var(--bg);padding:6px;
border-radius:6px;max-height:200px;overflow:auto}
@media (max-width:800px){.layout{flex-direction:column}.msg{max-width:92%}}
</style>
</head>
<body>
<div class="banner">Simulated engagement: fictional company, synthetic data</div>
<header>
<h1>Fadenwerk support agent: replay</h1>
<p>Real conversations of the agent (__MODEL__) with the mock shop, recorded by the eval suite. Viewing this page
calls no API. Pick a scenario; the right panel shows each tool call, tokens, cost and latency.</p>
</header>
<nav class="picker" id="picker"></nav>
<main class="layout">
<section class="chat" id="chat"></section>
<aside class="hood"><h2>Under the hood</h2><div id="turns"></div></aside>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; return e; };
const pretty = (v) => { try { return JSON.stringify(typeof v === "string" ? JSON.parse(v) : v, null, 2); }
  catch { return String(v); } };
function show(i) {
  const s = DATA[i];
  document.querySelectorAll("#picker button").forEach((b, j) => b.setAttribute("aria-pressed", j === i));
  const chat = document.getElementById("chat"), turns = document.getElementById("turns");
  chat.replaceChildren(); turns.replaceChildren();
  const v = el("div", "verdict"); v.append(`Scenario ${s.id} (${s.category}) · eval: `);
  const b = el("b", s.passed ? "pass" : "fail", s.passed ? "passed" : "failed: " + s.failures.join("; "));
  v.append(b); chat.append(v);
  s.turns.forEach((t, n) => {
    chat.append(el("div", "msg user", t.user_text), el("div", "msg bot", t.reply_text));
    const box = el("div", "turn"); box.append(el("strong", "", `Turn ${n + 1}`));
    const u = t.usage, meta = el("div", "meta");
    [`stop: ${t.stop_reason}`, `requests: ${t.api_requests}`, `in: ${u.input_tokens}`, `out: ${u.output_tokens}`,
     `cache read: ${u.cache_read_input_tokens}`, `cost: $${t.cost_usd.toFixed(5)}`, `${t.latency_ms} ms`]
      .forEach((x) => meta.append(el("span", "", x)));
    box.append(meta);
    t.tool_calls.forEach((c) => {
      const tool = el("div", "tool");
      tool.append(el("div", "name " + (c.is_error ? "error" : "ok"), c.name + (c.is_error ? " (error)" : "")),
                  el("pre", "", "input: " + pretty(c.input)), el("pre", "", "result: " + pretty(c.content)));
      box.append(tool);
    });
    turns.append(box);
  });
}
DATA.forEach((s, i) => { const b = el("button", "", s.id); b.onclick = () => show(i);
  document.getElementById("picker").append(b); });
show(0);
</script>
</body>
</html>
"""


def build_replay(results_path: Path, scenario_ids: list[str], out_path: Path) -> None:
    results_path = Path(results_path)
    by_id = {}
    for line in results_path.read_text().splitlines():
        row = json.loads(line)
        by_id[row["id"]] = row
    chosen = [by_id[i] for i in scenario_ids]  # KeyError for an unknown id
    data = [{k: r[k] for k in ("id", "category", "passed", "failures", "turns")} for r in chosen]
    summary_path = results_path.parent / "summary.json"
    model = json.loads(summary_path.read_text())["model"] if summary_path.exists() else "Claude"
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_PAGE.replace("__MODEL__", model).replace("__DATA__", payload))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, required=True, help="run dir containing results.jsonl")
    p.add_argument("--ids", required=True, help="comma-separated scenario ids, in display order")
    p.add_argument("--out", type=Path, default=Path("demo/index.html"))
    args = p.parse_args(argv)
    build_replay(args.run / "results.jsonl", args.ids.split(","), args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
