let csrf = "";
let page = 1;
const number = new Intl.NumberFormat("fa-IR");
const date = new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium", timeStyle: "short" });
const statusNames = { active: "فعال", expired: "منقضی", revoked: "باطل‌شده" };

function message(text, failed = false) {
  const target = document.getElementById("message");
  target.textContent = text;
  target.classList.toggle("error", failed);
}

async function api(path, body) {
  const options = { credentials: "same-origin", cache: "no-store" };
  if (body !== undefined) {
    options.method = "POST";
    options.headers = { "Content-Type": "application/json", "X-CSRF-Token": csrf };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/login") location.replace("/");
    throw new Error(value.message || "درخواست انجام نشد؛ دوباره تلاش کنید.");
  }
  return value;
}

async function login(event) {
  event.preventDefault();
  const button = event.target.querySelector("button");
  button.disabled = true;
  message("در حال بررسی اطلاعات ورود…");
  try {
    await api("/api/login", { username: document.getElementById("username").value.trim(),
      password: document.getElementById("password").value });
    document.getElementById("password").value = "";
    location.replace("/panel");
  } catch (error) {
    message(error.message === "Failed to fetch" ? "ارتباط با سرور برقرار نشد." : error.message, true);
  } finally {
    button.disabled = false;
  }
}

function cell(row, value, className = "") {
  const target = document.createElement("td");
  target.textContent = value;
  if (className) target.className = className;
  row.append(target);
  return target;
}

function renderLicense(license) {
  const row = document.createElement("tr");
  cell(row, license.customer);
  cell(row, license.plan === "monthly" ? "ماهانه" : "سالانه");
  cell(row, statusNames[license.status], "status " + license.status);
  cell(row, date.format(new Date(license.expires_at * 1000)));
  cell(row, number.format(license.daily_limit));
  cell(row, number.format(license.used_today));
  const identifier = cell(row, license.identifier.slice(0, 10) + "…", "identifier");
  identifier.title = license.identifier;
  return row;
}

async function loadLicenses() {
  message("در حال دریافت لایسنس‌ها…");
  try {
    const params = new URLSearchParams({ search: document.getElementById("search").value,
      status: document.getElementById("status").value, page: String(page) });
    const result = await api("/api/licenses?" + params);
    document.getElementById("licenses").replaceChildren(...result.licenses.map(renderLicense));
    document.getElementById("empty").hidden = result.licenses.length !== 0;
    document.getElementById("total").textContent = number.format(result.total) + " لایسنس";
    document.getElementById("page-label").textContent = "صفحهٔ " + number.format(page);
    document.getElementById("previous").disabled = page <= 1;
    document.getElementById("next").disabled = page * result.page_size >= result.total;
    message("");
  } catch (error) {
    message(error.message, true);
  }
}

async function startPanel() {
  try {
    const current = await api("/api/me");
    csrf = current.csrf;
    document.getElementById("admin-name").textContent = current.username;
    document.getElementById("logout").addEventListener("click", async () => {
      try { await api("/api/logout", {}); location.replace("/"); }
      catch (error) { message(error.message, true); }
    });
    document.getElementById("search-form").addEventListener("submit", event => {
      event.preventDefault(); page = 1; loadLicenses();
    });
    document.getElementById("previous").addEventListener("click", () => { page--; loadLicenses(); });
    document.getElementById("next").addEventListener("click", () => { page++; loadLicenses(); });
    await loadLicenses();
  } catch (error) {
    message(error.message, true);
  }
}

if (document.getElementById("login-form")) document.getElementById("login-form").addEventListener("submit", login);
if (document.getElementById("panel")) startPanel();
