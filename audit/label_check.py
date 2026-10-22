"""Write label_check.html: a blind labelling page for the author's check of 50 sampled reviews.

The page does not show the existing labels, so the author's answers are independent.
Export the result as data/author_labels.csv, then run `python3 build.py`.

Usage:  python3 -m audit.label_check [--n 50]
"""
import argparse
import json
from pathlib import Path

from audit.validate import load_rows

ROOT = Path(__file__).resolve().parent.parent
DEFINITIONS = {
    "PAID_PENDING": "Paid (in the app or through it), but the challan is still pending on Parivahan or in court",
    "FALSE_SETTLED": "The app showed Settled or Paid, but the government still shows it pending",
    "WRONG_DATA": "Challan shown that does not exist, belongs to someone else, is missing, or is out of date",
    "REFUND_STUCK": "The user says a refund was not received (failed or rejected payment, or refund promised or asked for)",
    "OVERCHARGE": "Charged far above the fine, or a fee the user did not see before paying",
    "COURT_ROUTING": "A court is involved in a paid-challan complaint (moved to court, court fees added)",
    "OTHER_CHALLAN": "About challans, but none of the above",
    "NOT_CHALLAN": "Not about a challan problem at all",
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Label check</title><style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1a;--muted:#6b6b66;--line:#e3e2dd;--accent:#e85d1a}
@media (prefers-color-scheme: dark){:root{--bg:#121211;--card:#1b1b19;--ink:#ecebe6;--muted:#a3a29b;--line:#2e2e2b;--accent:#ff7a3d}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.text{font-size:17px;white-space:pre-wrap}
label{display:block;padding:8px;border:1px solid var(--line);border-radius:8px;margin:6px 0;cursor:pointer}
label small{display:block;color:var(--muted)}
button{font:inherit;padding:10px 16px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
button.primary{background:var(--accent);color:#fff;border:0}
.row{display:flex;gap:8px;justify-content:space-between;align-items:center;flex-wrap:wrap}
.muted{color:var(--muted);font-size:14px}
</style></head><body><main>
<h1>Label check</h1>
<p class="muted">Read each review and tick every problem it describes. Your answers are saved in this browser as you go. When you finish, press Export and save the file as <b>data/author_labels.csv</b>.</p>
<div class="row"><span id="progress" class="muted"></span><span><button id="prev">Back</button> <button id="next" class="primary">Next</button></span></div>
<div class="card"><div class="muted" id="meta"></div><div class="text" id="text"></div></div>
<div id="opts"></div>
<div class="row"><span class="muted" id="done"></span><button id="export">Export CSV</button></div>
</main><script>
const ITEMS = __ITEMS__, DEFS = __DEFS__, KEY = "label-check-v1";
let state = {}, i = 0;
try { state = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
function render() {
  const it = ITEMS[i], picked = new Set(state[it.id] || []);
  document.getElementById("progress").textContent = `Review ${i + 1} of ${ITEMS.length}`;
  document.getElementById("meta").textContent = `${it.app} · ${it.at.slice(0, 10)}`;
  document.getElementById("text").textContent = it.text;
  const opts = document.getElementById("opts");
  opts.replaceChildren(...Object.entries(DEFS).map(([k, d]) => {
    const box = document.createElement("input"); box.type = "checkbox"; box.checked = picked.has(k);
    box.onchange = () => { box.checked ? picked.add(k) : picked.delete(k); state[it.id] = [...picked]; save(); count(); };
    const lab = document.createElement("label"), s = document.createElement("small");
    s.textContent = d; lab.append(box, " " + k.replace(/_/g, " ").toLowerCase(), s); return lab;
  }));
  count();
}
function count() {
  const n = ITEMS.filter(it => (state[it.id] || []).length).length;
  document.getElementById("done").textContent = `${n} of ${ITEMS.length} labelled`;
}
document.getElementById("next").onclick = () => { if (i < ITEMS.length - 1) { i++; render(); } };
document.getElementById("prev").onclick = () => { if (i > 0) { i--; render(); } };
document.getElementById("export").onclick = () => {
  const lines = ["id,labels"].concat(ITEMS.filter(it => (state[it.id] || []).length).map(it => `${it.id},${state[it.id].join(";")}`));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\\n") + "\\n"], {type: "text/csv"}));
  a.download = "author_labels.csv"; a.click();
};
render();
</script></body></html>
"""


def write_page(n: int = 50, out: Path = ROOT / "label_check.html") -> Path:
    rows = [r for r in load_rows(ROOT / "data" / "validation.csv") if r["split"] == "test"][:n]
    items = [{"id": r["id"], "app": r["app"], "at": "", "text": r["text"]} for r in rows]
    at = {r["id"]: r["at"] for r in json.loads((ROOT / "data" / "reviews.json").read_text())}
    for it in items:
        it["at"] = at[it["id"]]
    html = PAGE.replace("__ITEMS__", json.dumps(items, ensure_ascii=False).replace("</", "<\\/"))
    out.write_text(html.replace("__DEFS__", json.dumps(DEFINITIONS)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    print(write_page(ap.parse_args().n))
