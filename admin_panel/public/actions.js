let send;
let refresh;
let requestId;
let selected;
const names = { new: "صدور", extend: "تمدید", revoke: "ابطال", quota: "تغییر سهمیه" };
const when = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" });

export function licenseActions(license) {
  const target = document.createElement("td");
  const group = document.createElement("div");
  group.className = "row-actions";
  for (const action of ["extend", "quota", "revoke"]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary" + (action === "revoke" ? " danger" : "");
    button.textContent = names[action];
    button.setAttribute("aria-label", names[action] + " لایسنس " + license.customer);
    button.disabled = action === "revoke" && license.status === "revoked";
    button.addEventListener("click", () => openChange(license, action));
    group.append(button);
  }
  target.append(group);
  return target;
}

function openChange(license, action) {
  selected = { license, action, requestId: crypto.randomUUID() };
  document.getElementById("change-title").textContent = names[action] + " لایسنس";
  document.getElementById("change-customer").textContent = license.customer;
  document.getElementById("change-message").textContent = "";
  const input = document.getElementById("change-value");
  const revoke = action === "revoke";
  input.required = !revoke;
  input.max = action === "extend" ? "3650" : "100000";
  input.value = action === "extend" ? "30" : String(license.daily_limit);
  document.getElementById("change-value-group").hidden = revoke;
  document.getElementById("change-value-label").textContent = action === "extend" ? "تعداد روز تمدید" : "سهمیهٔ روزانهٔ جدید";
  document.getElementById("revoke-confirm").hidden = !revoke;
  document.getElementById("revoke-check").required = revoke;
  document.getElementById("revoke-check").checked = false;
  const descriptions = {
    extend: "تمدید از امروز یا پایان اعتبار فعلی، هرکدام دیرتر باشد، حساب می‌شود و لایسنس را دوباره فعال می‌کند.",
    quota: "شمارندهٔ مصرف امروز صفر نمی‌شود. اگر سهمیه از مصرف امروز کمتر شود، درخواست تازه تا روز بعد رد می‌شود.",
    revoke: "پس از تأیید، درخواست‌های تازهٔ این لایسنس رد می‌شوند. فعال‌سازی مجدد از طریق تمدید ممکن است.",
  };
  document.getElementById("change-description").textContent = descriptions[action];
  document.getElementById("change-dialog").showModal();
}

function showKey(key, customer) {
  document.getElementById("key-customer").textContent = customer;
  document.getElementById("issued-key").value = key;
  document.getElementById("issued-key").type = "password";
  document.getElementById("key-toggle").textContent = "نمایش کد";
  document.getElementById("key-message").textContent = "";
  document.getElementById("key-dialog").showModal();
}

async function issue(event) {
  event.preventDefault();
  const button = event.target.querySelector("button[type=submit]");
  const status = document.getElementById("issue-message");
  button.disabled = true;
  status.textContent = "در حال صدور…";
  try {
    const result = await send("/api/licenses/new", { request_id: requestId,
      customer: document.getElementById("customer").value.trim(), plan: document.getElementById("plan").value,
      daily_limit: Number(document.getElementById("daily-limit").value) });
    if (!result.key) {
      status.textContent = "این درخواست قبلاً ثبت شده و لایسنس دوباره صادر نشد. کد خام قبلی قابل بازیابی نیست؛ فهرست را بررسی کنید.";
      await refresh();
      return;
    }
    document.getElementById("issue-dialog").close();
    showKey(result.key, result.license.customer);
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function change(event) {
  event.preventDefault();
  const button = document.getElementById("change-submit");
  const status = document.getElementById("change-message");
  button.disabled = true;
  status.textContent = "در حال ثبت تغییر…";
  const body = { request_id: selected.requestId };
  if (selected.action === "extend") body.days = Number(document.getElementById("change-value").value);
  if (selected.action === "quota") body.daily_limit = Number(document.getElementById("change-value").value);
  try {
    await send(`/api/licenses/${selected.license.identifier}/${selected.action}`, body);
    document.getElementById("change-dialog").close();
    await refresh();
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

export async function loadEvents(api) {
  const result = await api("/api/events");
  const rows = result.events.map(event => {
    const row = document.createElement("tr");
    for (const value of [when.format(new Date(event.created_at * 1000)), names[event.action], event.customer || "مشتری حذف‌شده", event.actor]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  });
  document.getElementById("events").replaceChildren(...rows);
  document.getElementById("events-empty").hidden = rows.length !== 0;
}

function setupKey() {
  window.addEventListener("pagehide", () => {
    document.getElementById("issued-key").value = "";
  });
  document.getElementById("key-dialog").addEventListener("close", () => {
    document.getElementById("issued-key").value = "";
  });
  document.getElementById("key-toggle").addEventListener("click", () => {
    const field = document.getElementById("issued-key");
    field.type = field.type === "password" ? "text" : "password";
    document.getElementById("key-toggle").textContent = field.type === "password" ? "نمایش کد" : "پنهان‌کردن کد";
  });
  document.getElementById("key-copy").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(document.getElementById("issued-key").value);
      document.getElementById("key-message").textContent = "کد کپی شد؛ آن را فقط در محل خصوصی بچسبانید.";
    } catch {
      document.getElementById("key-message").textContent = "کپی خودکار ممکن نشد؛ کد را نمایش دهید و دستی کپی کنید.";
    }
  });
}

export function setupActions(api, refreshLists) {
  send = api;
  refresh = refreshLists;
  document.getElementById("issue-open").addEventListener("click", () => {
    requestId = crypto.randomUUID();
    document.getElementById("issue-form").reset();
    document.getElementById("issue-message").textContent = "";
    document.getElementById("issue-dialog").showModal();
  });
  document.getElementById("issue-form").addEventListener("submit", issue);
  document.getElementById("change-form").addEventListener("submit", change);
  for (const button of document.querySelectorAll("[data-close]")) {
    button.addEventListener("click", () => document.getElementById(button.dataset.close).close());
  }
  setupKey();
}
