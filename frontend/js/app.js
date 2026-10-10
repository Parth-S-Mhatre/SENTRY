/* SecureView dashboard — Vanilla JS. Browser talks ONLY to FastAPI.
   No Supabase, no secrets, no frameworks. Lazy-loads evidence. */
"use strict";
const API_BASE = (window.SENTRY_API_BASE || "http://localhost:8000").replace(/\/$/, "");
const api = (p) => API_BASE + p;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmtTime = (iso) => { try { return new Date(iso).toLocaleString([], {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}); } catch { return iso || "—"; } };
const ago = (iso) => { const m = Math.round((Date.now() - new Date(iso)) / 60000); return m < 1 ? "just now" : m < 60 ? m + " min ago" : Math.round(m/60) + " hr ago"; };
const label = (t) => t === "SUSPICIOUS_ACTIVITY" ? "Suspicious Activity" : t === "PERSON_DETECTED" ? "Person Detected" : (t || "Incident");
const isSus = (t) => t === "SUSPICIOUS_ACTIVITY";
const seenIds = new Set();
let toastCount = 0;

function toast(msg) {
  if (toastCount > 2) return;
  toastCount++;
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<span class="dot ok"></span><span>${esc(msg)}</span>`;
  $("toast-wrap").appendChild(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 320); }, 4200);
}

function countUp(el, target) {
  const t0 = performance.now(), dur = 700;
  const step = (t) => {
    const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(target * e);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function applyTheme() {
  const dark = localStorage.getItem("sentry-theme") === "dark" ||
    (!localStorage.getItem("sentry-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "";
  $("theme-toggle").textContent = dark ? "☀" : "◐";
}

async function getJSON(path) { const r = await fetch(api(path)); if (!r.ok) throw new Error(path + " → " + r.status); return r.json(); }

function greeting() {
  const h = new Date().getHours();
  $("greeting").textContent = "Good " + (h < 12 ? "Morning" : h < 17 ? "Afternoon" : "Evening") + ", Admin";
  const tick = () => { const d = new Date();
    $("date").textContent = d.toLocaleDateString([], {month:"short",day:"numeric",year:"numeric"});
    $("time").textContent = d.toLocaleTimeString([], {hour:"numeric",minute:"2-digit"}); };
  tick(); setInterval(tick, 15000);
}

async function loadStatus() {
  try {
    const [health, cam] = await Promise.all([getJSON("/api/health"), getJSON("/api/camera/status")]);
    const online = cam.status === "online";
    $("sys-pill").innerHTML = `<span class="dot ${online ? "ok" : "warn"}"></span>${online ? "System Online" : esc(cam.status)}`;
    $("live-status").textContent = online
      ? `Online • ${cam.live.resolution} • ~${cam.live.fpsApprox} fps • frame ${cam.live.lastFrameAgeSec}s ago`
      : esc(cam.status);
    $("live-res").textContent = cam.live.resolution !== "unknown" ? cam.live.resolution : "480p";
    $("live-sub").textContent = `1 camera connected — ${esc(cam.camera)} (${esc(cam.ip)}:${cam.port}/${esc(cam.stream)}).`;
    $("cam-title").textContent = `Camera 1 — ${cam.camera}`;
    $("live-name").textContent = cam.camera;
    return { health, cam };
  } catch { $("sys-pill").innerHTML = `<span class="dot bad"></span>Backend unreachable`; return null; }
}

async function loadIncidents(limit = 20) { try { return (await getJSON("/api/incidents?limit=" + limit)).incidents; } catch { return []; } }

function alertRow(i) {
  return `<div class="alert-row" data-id="${esc(i.id)}">
    <img class="thumb" loading="lazy" src="${api("/api/incidents/" + i.id + "/screenshot")}" alt="">
    <div><div class="t">${esc(label(i.event_type))}</div>
    <div class="s">${esc(i.camera_name)}<br>${fmtTime(i.created_at)} • ${(i.clip_path ? "10s clip" : "Screenshot")}</div></div>
    <span class="tag ${i.status === "NEW" ? "new" : "rev"}">${esc(i.status)}</span></div>`;
}
function incidentRow(i) {
  return `<div class="incident-row" data-id="${esc(i.id)}">
    <span class="dot ${isSus(i.event_type) ? "bad" : "warn"}"></span>
    <div><div class="t">${fmtTime(i.created_at)} — ${esc(label(i.event_type))}</div>
    <div class="s">${esc(i.description || "")}${i.confidence ? " • conf " + Number(i.confidence).toFixed(2) : ""}</div></div>
    <img class="thumb" loading="lazy" src="${api("/api/incidents/" + i.id + "/screenshot")}" alt=""></div>`;
}

async function renderDashboard() {
  $("dash-feed").src = api("/api/stream");
  $("recent-alerts").innerHTML = `<div class="skel"></div><div class="skel"></div>`;
  $("recent-incidents").innerHTML = `<div class="skel"></div><div class="skel"></div>`;
  const [incidents, st] = await Promise.all([loadIncidents(20), loadStatus()]);
  const news = incidents.filter((i) => i.status === "NEW");
  incidents.forEach((i) => { if (!seenIds.has(i.id)) { if (seenIds.size) toast(label(i.event_type) + " — " + i.camera_name); seenIds.add(i.id); } });
  $("nav-alert-count").hidden = !news.length; $("nav-alert-count").textContent = news.length;
  $("stats").innerHTML = [
    ["Total Cameras", "1", "Online", false], ["Active Alerts", news.length, "NEW incidents", true],
    ["Total Incidents", incidents.length, "All time", true], ["System Status", st && st.cam.status === "online" ? "Online" : "Degraded", st ? esc(st.cam.live.resolution) : "—", false],
  ].map(([k, v, s, num]) => `<div class="stat"><small>${k}</small><div class="big"${num ? " data-count" : ""}>${v}</div><div class="sub">${s}</div></div>`).join("");
  document.querySelectorAll("#stats [data-count]").forEach((el) => countUp(el, +el.textContent || 0));
  $("recent-alerts").innerHTML = incidents.slice(0, 4).map(alertRow).join("") || `<div class="empty">No alerts yet.</div>`;
  $("recent-incidents").innerHTML = incidents.slice(0, 4).map(incidentRow).join("") || `<div class="empty">No incidents yet.</div>`;
  const latest = incidents[0];
  $("latest-evidence").innerHTML = latest
    ? `<img class="evidence-img" loading="lazy" src="${api("/api/incidents/" + latest.id + "/screenshot")}" alt="Latest evidence">
       <p class="muted">${esc(label(latest.event_type))} • ${ago(latest.created_at)}</p>`
    : `<div class="empty">No evidence yet.</div>`;
  $("dash-meta").textContent = "Live Feed • " + (st ? st.cam.live.resolution : "");
}

function renderLive() { $("live-feed").src = api("/api/stream"); loadStatus(); $("btn-full").onclick = () => { const el = $("live-feed"); el.requestFullscreen && el.requestFullscreen(); }; }

async function renderIncidents() {
  const incidents = await loadIncidents(50);
  $("incident-table").innerHTML = incidents.map(incidentRow).join("") || `<div class="empty">No incidents yet.</div>`;
}

async function renderDetail(id) {
  let i; try { const r = await fetch(api("/api/incidents/" + id)); if (!r.ok) throw 0; i = await r.json(); }
  catch { $("detail-title").textContent = "Incident not found"; return; }
  $("detail-title").textContent = label(i.event_type) + " — " + fmtTime(i.created_at);
  const st = $("detail-status"); st.textContent = i.status; st.className = "chip" + (i.status === "NEW" ? " red" : "");
  $("detail-shot").src = api("/api/incidents/" + id + "/screenshot");
  const clip = $("detail-clip"); clip.removeAttribute("src"); clip.load();
  if (i.clip_path) clip.src = api("/api/incidents/" + id + "/clip");  // loads only on demand
  $("detail-meta").innerHTML = [["Camera", i.camera_name + " (" + i.camera_id + ")"],
    ["Event", label(i.event_type)], ["Confidence", i.confidence ?? "—"], ["Status", i.status],
    ["Time", fmtTime(i.created_at)], ["Description", i.description || "—"],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("") + (i.ai_analysis
    ? `<dt>AI Analysis</dt><dd>${esc(i.ai_analysis)}</dd>` : "");
}

async function renderEvidence() {
  const incidents = await loadIncidents(50);
  $("evidence-grid").innerHTML = incidents.map((i) =>
    `<div class="ev-cell" data-id="${esc(i.id)}">
      <img loading="lazy" src="${api("/api/incidents/" + i.id + "/screenshot")}" alt="">
      <div><strong>${esc(label(i.event_type))}</strong><br><small>${fmtTime(i.created_at)}${i.clip_path ? " • video" : ""}</small></div>
    </div>`).join("") || `<div class="empty">No evidence yet.</div>`;
}

async function renderSettings() {
  const st = await loadStatus(); if (!st) return;
  $("settings-cam").innerHTML = [["Name", st.cam.camera + " (" + st.cam.cameraId + ")"],
    ["Address", st.cam.ip + ":" + st.cam.port + " / " + st.cam.stream],
    ["Stream", "MJPEG 480p ~10fps (browser)"], ["Status", st.cam.status],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
  $("settings-api").innerHTML = [["Health", st.health.status], ["Stage", "7 — API + dashboard"],
    ["Evidence", "Private Supabase bucket via signed URLs"], ["Auth", "Not implemented (MVP)"],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
}

function route() {
  const parts = (location.hash || "#dashboard").replace(/^#/, "").split("/");
  const name = parts[0] || "dashboard", arg = parts[1];
  document.querySelectorAll(".view").forEach((v) => { v.hidden = true; v.classList.remove("enter"); });
  document.querySelectorAll("#nav a").forEach((a) => a.classList.toggle("active", a.dataset.route === name || (name === "incident" && a.dataset.route === "incidents")));
  ({ dashboard: () => { show("view-dashboard"); renderDashboard(); },
     live: () => { show("view-live"); renderLive(); },
     incidents: () => { show("view-incidents"); renderIncidents(); },
     incident: () => { show("view-detail"); renderDetail(arg); },
     evidence: () => { show("view-evidence"); renderEvidence(); },
     settings: () => { show("view-settings"); renderSettings(); },
  }[name] || (() => { show("view-dashboard"); renderDashboard(); }))();
}

function show(id) {
  const v = $(id);
  v.hidden = false;
  void v.offsetWidth;  // restart the enter animation
  v.classList.add("enter");
}

document.addEventListener("click", (e) => {
  const row = e.target.closest("[data-id]");
  if (row) location.hash = "#incident/" + row.dataset.id;
});
$("search").addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("#incident-table .incident-row").forEach((r) => {
    r.style.display = r.textContent.toLowerCase().includes(q) ? "" : "none";
  });
});
$("theme-toggle").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  localStorage.setItem("sentry-theme", dark ? "dark" : "light");
  applyTheme();
});
$("btn-refresh").addEventListener("click", (e) => {
  const b = e.currentTarget;
  b.classList.add("spinning");
  renderIncidents().finally(() => setTimeout(() => b.classList.remove("spinning"), 600));
});
window.addEventListener("hashchange", route);
applyTheme(); greeting(); route();
setInterval(() => { if ((location.hash || "#dashboard") === "#dashboard") renderDashboard(); }, 30000);
