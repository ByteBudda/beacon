var API = "/api";
var token = localStorage.getItem("auth_token") || null;
var user = null;
var searchTimer = null, adminSearchTimer = null, adminModTimer = null;
console.log("Beacon JS loaded");

function getDeviceId() {
    var deviceId = localStorage.getItem("device_id");
    if (!deviceId) {
        deviceId = "d_" + Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
        localStorage.setItem("device_id", deviceId);
    }
    return deviceId;
}

/* ==================== HTTP ==================== */

async function api(path, method = "GET", body) {
    const h = { 
        "Content-Type": "application/json",
        "Accept": "application/json"
    };
    if (token) h["Authorization"] = "Bearer " + token;
    try {
        const r = await fetch(API + path, { 
            method, 
            headers: h, 
            body: body ? JSON.stringify(body) : undefined
        });
        if (!r.ok && r.status === undefined) return { error: true, detail: "Ошибка сети" };
        const ct = r.headers?.get("content-type") || "";
        const d = ct.includes("json") ? await r.json() : { detail: "Статус " + r.status };
        return r.ok ? d : { error: true, status: r.status, detail: d.detail || "Ошибка" };
    } catch(e) {
        return { error: true, detail: e.message };
    }
}

function err(r) {
    if (!r) return "Неизвестная ошибка";
    const d = r.detail || "";
    const map = [
        [/already registered/i, "Этот email уже зарегистрирован"],
        [/Username already taken/i, "Имя пользователя занято"],
        [/Invalid email or password/i, "Неверный email или пароль"],
        [/Email not verified/i, "Подтвердите email перед входом"],
        [/Too many/i, "Слишком много попыток. Попробуйте позже"],
        [/Link not found/i, "Ссылка не найдена"],
        [/Link expired/i, "Срок действия ссылки истёк"],
        [/Slug already taken/i, "Этот алиас уже занят"],
        [/Link limit reached/i, "Лимит ссылок исчерпан. Обновите тариф"],
        [/Invalid token|Token expired/i, "Сессия истекла. Войдите снова"],
        [/User not found/i, "Пользователь не найден"],
        [/Admin access required/i, "Нужны права администратора"],
    ];
    for (const [re, msg] of map) if (re.test(d)) return msg;
    if (Array.isArray(r.detail)) return r.detail.map(e => e.msg || JSON.stringify(e)).join("\n");
    return d || "Произошла ошибка";
}

/* ==================== CAPTCHA ==================== */

let captchaCode = "";

function refreshCaptcha() {
    captchaCode = Array.from({ length: 6 }, () => "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"[Math.random() * 34 | 0]).join("");
    const el = document.getElementById("captcha-code");
    if (el) { el.textContent = captchaCode; el.style.transform = `rotate(${Math.random() * 4 - 2}deg)`; }
    const inp = document.getElementById("captcha-input");
    if (inp) inp.value = "";
}

function checkCaptcha() {
    return (document.getElementById("captcha-input")?.value || "").toUpperCase() === captchaCode;
}

/* ==================== AUTH VIEWS ==================== */

function showAuth(view) {
    const m = document.getElementById("auth-modal");
    m.style.display = "flex";
    ["login-view", "register-view", "forgot-view", "register-success-view", "forgot-success-view"].forEach(id => {
        const e = document.getElementById(id);
        if (e) e.style.display = "none";
    });
    document.getElementById(view + "-view").style.display = "block";
    if (view === "register") { refreshCaptcha(); hideEl("register-error"); }
    if (view === "login") hideEl("login-error");
}

function hideAuth() { document.getElementById("auth-modal").style.display = "none"; }
function hideVerificationRequired() { document.getElementById("verification-required-modal").style.display = "none"; }
function hideEl(id) { const e = document.getElementById(id); if (e) e.style.display = "none"; }
function showEl(id) { const e = document.getElementById(id); if (e) e.style.display = ""; }

/* ==================== AUTH ACTIONS ==================== */

async function login() {
    const email = document.getElementById("login-email").value.trim();
    const password = document.getElementById("login-password").value;
    const ed = document.getElementById("login-error");
    if (!email || !password) { ed.innerHTML = "<div>Введите email и пароль</div>"; ed.style.display = "block"; return; }

    const btn = document.querySelector("#login-form button");
    btn.disabled = true; btn.textContent = "Вход..."; ed.style.display = "none";

    const r = await api("/auth/login", "POST", { email, password });
    btn.disabled = false; btn.textContent = "Войти";

    if (r?.access_token) {
        if (r.user && !r.user.email_verified) {
            document.getElementById("verification-email").textContent = email;
            document.getElementById("verification-required-modal").style.display = "flex";
            return;
        }
        token = r.access_token; localStorage.setItem("auth_token", token);
        user = r.user; hideAuth(); onLogin();
    } else {
        ed.innerHTML = `<div>⚠️ ${err(r)}</div>`; ed.style.display = "block";
    }
}

async function register() {
    const username = document.getElementById("register-username").value.trim();
    const email = document.getElementById("register-email").value.trim();
    const pw = document.getElementById("register-password").value;
    const pw2 = document.getElementById("register-confirm-password").value;
    const refCode = document.getElementById("register-referral-code")?.value.trim();
    const ed = document.getElementById("register-error");
    ed.style.display = "none";

    const errs = [];
    if (!username || username.length < 3 || username.length > 50) errs.push("Имя: 3-50 символов");
    if (!/^[A-Za-z0-9_-]+$/.test(username)) errs.push("Имя: только буквы, цифры, дефис, подчёркивание");
    if (!email) errs.push("Email обязателен");
    if (!pw || pw.length < 8) errs.push("Пароль: минимум 8 символов");
    if (!/[A-Z]/.test(pw)) errs.push("Пароль: нужна заглавная буква");
    if (!/[0-9]/.test(pw)) errs.push("Пароль: нужна цифра");
    if (pw !== pw2) errs.push("Пароли не совпадают");
    if (!checkCaptcha()) { errs.push("Неверный код CAPTCHA"); refreshCaptcha(); }
    if (errs.length) { ed.innerHTML = errs.map(e => `<div>⚠️ ${e}</div>`).join(""); ed.style.display = "block"; return; }

    const btn = document.getElementById("register-btn");
    btn.disabled = true; btn.querySelector(".btn-text").style.opacity = "0.6"; btn.querySelector(".btn-spinner").style.display = "inline-block";

    const r = await api("/auth/register", "POST", { username, email, password: pw, referral_code: refCode });
    btn.disabled = false; btn.querySelector(".btn-text").style.opacity = "1"; btn.querySelector(".btn-spinner").style.display = "none";

    if (r?.access_token) {
        token = r.access_token; localStorage.setItem("auth_token", token); user = r.user;
        document.getElementById("reg-success-email").textContent = email;
        showAuth("register"); document.getElementById("register-view").style.display = "none";
        document.getElementById("register-success-view").style.display = "block";
        refreshCaptcha();
    } else {
        ed.innerHTML = `<div>⚠️ ${err(r)}</div>`; ed.style.display = "block"; refreshCaptcha();
    }
}

async function forgotPassword() {
    const email = document.getElementById("forgot-email").value.trim();
    if (!email) { alert("Введите email"); return; }
    const btn = document.querySelector("#forgot-form button");
    btn.disabled = true; btn.textContent = "Отправка...";
    await api("/auth/password-reset", "POST", { email });
    btn.disabled = false; btn.textContent = "Отправить ссылку";
    document.getElementById("forgot-view").style.display = "none";
    document.getElementById("forgot-success-view").style.display = "block";
}

function logout() {
    token = null; user = null; localStorage.removeItem("auth_token");
    document.getElementById("dashboard").style.display = "none";
    document.getElementById("hero-section").style.display = "flex";
    document.getElementById("btn-show-login").style.display = "";
    document.getElementById("btn-show-register").style.display = "";
    document.getElementById("topbar-user").style.display = "none";
    document.getElementById("my-links-btn").style.display = "none";
    document.getElementById("dashboard-tab-btn").style.display = "none";
}

function onLogin() {
    document.getElementById("btn-show-login").style.display = "none";
    document.getElementById("btn-show-register").style.display = "none";
    document.getElementById("topbar-user").style.display = "";
    document.getElementById("topbar-username").textContent = user.username;
    if (user.role === "admin") {
        document.getElementById("admin-tab").style.display = "";
        document.getElementById("dashboard-tab-btn").style.display = "";
    }
    document.getElementById("my-links-btn").style.display = "";
    document.getElementById("verify-page").style.display = "none";
    // Stay on main page after login, show hero section
    document.getElementById("hero-section").style.display = "flex";
    document.getElementById("dashboard").style.display = "none";
}

function goHome() {
    hideAuth(); hideStats(); hideQr();
    document.getElementById("verify-page").style.display = "none";
    document.getElementById("dashboard").style.display = "none";
    document.getElementById("hero-section").style.display = "flex";
}

function goDashboard() {
    hideAuth(); hideStats(); hideQr();
    document.getElementById("verify-page").style.display = "none";
    document.getElementById("hero-section").style.display = "none";
    document.getElementById("dashboard").style.display = "block";
    loadLinks();
}

/* ==================== FOLDERS ==================== */

let currentFolderId = null;

async function loadFolders() {
    const r = await api("/links/folders");
    const grid = document.getElementById("folders-grid");
    grid.innerHTML = "";
    
    // Populate dropdowns
    const folderSelect = document.getElementById("dash-folder-id");
    const bulkFolderSelect = document.getElementById("bulk-folder-id");
    [folderSelect, bulkFolderSelect].forEach(fs => {
        if (!fs) return;
        const opts = fs.querySelectorAll("option");
        opts.forEach(o => { if (o.value) o.remove(); });
        r.folders?.forEach(f => {
            const opt = document.createElement("option");
            opt.value = f.id;
            opt.textContent = f.name;
            fs.appendChild(opt);
        });
    });
    
    if (r?.error || !r?.folders?.length) {
        grid.innerHTML = '<p style="opacity:.5">Нет папок. Создайте первую!</p>';
        return;
    }
    r.folders.forEach(f => {
        const card = document.createElement("div");
        card.className = "folder-card" + (f.id === currentFolderId ? " active" : "");
        card.innerHTML = `
            <div class="folder-card-name" style="color:${f.color}">
                <span style="background:${f.color};width:12px;height:12px;border-radius:3px;display:inline-block;"></span>
                ${esc(f.name)}
            </div>
            <div class="folder-card-count">${f.link_count} ссылок</div>
            <button class="folder-edit" onclick="event.stopPropagation(); editFolder(${f.id}, '${esc(f.name)}', '${f.color}')">✏️</button>
            <button class="folder-delete" onclick="event.stopPropagation(); deleteFolder(${f.id})">🗑️</button>
        `;
        card.onclick = () => { currentFolderId = f.id; loadLinksByFolder(f.id); };
        grid.appendChild(card);
    });
}

async function createFolder() {
    const name = document.getElementById("new-folder-name").value.trim();
    const color = document.getElementById("new-folder-color").value;
    if (!name) { alert("Введите название"); return; }
    const r = await api("/links/folders", "POST", { name, color });
    if (r?.error) { alert(err(r)); return; }
    document.getElementById("new-folder-name").value = "";
    loadFolders();
}

async function editFolder(id, name, color) {
    const newName = prompt("Новое название:", name);
    if (!newName || newName === name) return;
    const newColor = prompt("Цвет (hex):", color);
    const r = await api(`/links/folders/${id}`, "PUT", { name: newName, color: newColor || color });
    if (r?.error) { alert(err(r)); return; }
    loadFolders();
}

async function deleteFolder(id) {
    if (!confirm("Удалить папку? Ссылки останутся.")) return;
    const r = await api(`/links/folders/${id}`, "DELETE");
    if (r?.error) { alert(err(r)); return; }
    currentFolderId = null;
    loadFolders();
}

async function loadLinksByFolder(folderId) {
    const r = await api(`/links?folder_id=${folderId}`);
    if (r?.error) return;
    loadFolders(); // highlight active folder
    const grid = document.getElementById("links-grid");
    grid.querySelectorAll(".link-card").forEach(e => e.remove());
    const empty = document.getElementById("links-empty");
    if (!r.links?.length) { empty.style.display = ""; return; }
    empty.style.display = "none";
    r.links.forEach(l => grid.appendChild(renderLink(l)));
}

/* ==================== EXPORT/IMPORT ==================== */

async function exportCsv() {
    window.open(API + "/v1/import-export/export/csv", "_blank");
}

async function exportJson() {
    window.open(API + "/v1/import-export/export/json", "_blank");
}

async function importFile() {
    const fileInput = document.getElementById("import-file");
    const file = fileInput?.files?.[0];
    if (!file) { alert("Выберите файл"); return; }
    
    const isJson = file.name.endsWith(".json");
    const endpoint = isJson ? "/v1/import-export/import/json" : "/v1/import-export/import/csv";
    
    const formData = new FormData();
    formData.append("file", file);
    
    const btn = document.getElementById("btn-import");
    btn.disabled = true; btn.textContent = "Импорт...";
    
    try {
        const token = localStorage.getItem("auth_token");
        const r = await fetch(API + endpoint, {
            method: "POST",
            headers: { "Authorization": "Bearer " + token },
            body: formData
        });
        const d = await r.json();
        const resultEl = document.getElementById("import-result");
        resultEl.style.display = "block";
        resultEl.innerHTML = `Импортировано: ${d.imported}<br>Ошибки: ${d.errors?.length || 0}`;
    } catch(e) {
        alert("Ошибка: " + e.message);
    }
    
    btn.disabled = false; btn.textContent = "Импортировать";
}

/* ==================== BULK CREATE ==================== */

async function bulkCreate() {
    const text = document.getElementById("bulk-urls").value.trim();
    if (!text) { alert("Введите ссылки"); return; }
    const urls = text.split("\n").map(u => u.trim()).filter(u => u.startsWith("http"));
    if (!urls.length) { alert("Нет валидных URL"); return; }
    const folderId = document.getElementById("bulk-folder-id")?.value;
    const folderIdNum = folderId ? parseInt(folderId) : undefined;
    const btn = document.getElementById("btn-bulk-create");
    btn.disabled = true; btn.textContent = "Создание...";
    const results = [];
    const errors = [];
    for (const url of urls) {
        const r = await api("/links", "POST", { url, folder_id: folderIdNum });
        if (r?.id) results.push(r);
        else if (r?.error) errors.push(`${url}: ${err(r)}`);
    }
    btn.disabled = false; btn.textContent = "Создать все";
    document.getElementById("bulk-results").style.display = "block";
    const container = document.getElementById("bulk-links");
    let html = "";
    if (results.length) {
        html += results.map(r => `
            <div class="bulk-link-item">
                <span class="bulk-link-url">${location.origin}/s/${r.slug}</span>
                <button class="btn-ghost" onclick="copyLink('${location.origin}/s/${r.slug}')">Копировать</button>
            </div>
        `).join("");
    }
    if (errors.length) {
        html += `<div class="bulk-errors"><strong>Ошибки:</strong>${errors.map(e => `<div>${esc(e)}</div>`).join("")}</div>`;
    }
    container.innerHTML = html || "Нет результатов";
    if (results.length) loadFolders();
}

/* ==================== ACCOUNT ==================== */

async function loadAccount() {
    if (!user) return;
    document.getElementById("account-username").value = user.username;
    document.getElementById("account-email").value = user.email;
    const r = await api("/v1/account/api-key");
    if (r?.has_api_key) {
        document.getElementById("api-key").value = "(уже есть ключ - нажмите Пересоздать)";
    } else {
        document.getElementById("api-key").value = "(ключ отсутствует)";
    }
}

async function changePassword() {
    const oldPw = document.getElementById("old-password").value;
    const newPw = document.getElementById("new-password").value;
    if (!oldPw || !newPw) { alert("Заполните все поля"); return; }
    if (newPw.length < 8) { alert("Новый пароль минимум 8 символов"); return; }
    const r = await api("/auth/change-password", "POST", { old_password: oldPw, new_password: newPw });
    if (r?.error) { alert(err(r)); return; }
    alert("Пароль изменён!");
    document.getElementById("old-password").value = "";
    document.getElementById("new-password").value = "";
}

async function changeEmail() {
    const newEmail = prompt("Введите новый email:", user.email);
    if (!newEmail || newEmail === user.email) return;
    const password = prompt("Введите пароль для подтверждения:");
    if (!password) return;
    const r = await api("/account/email", "PUT", { new_email: newEmail, password });
    if (r?.error) { alert(err(r)); return; }
    user.email = newEmail;
    document.getElementById("account-email").value = newEmail;
    alert("Email изменён! Подтвердите новый email.");
}

async function deleteAccount() {
    if (!confirm("Вы уверены? Это удалит ВСЕ ваши ссылки и данные. Невозможно отменить!")) return;
    if (!confirm("Точно удалить аккаунт?")) return;
    const password = prompt("Введите пароль для подтверждения:");
    if (!password) return;
    if (!confirm("ПОСЛЕДНЕЕ ПРЕДУПРЕЖДЕНИЕ: Все данные будут удалены.")) return;
    const r = await api("/account", "DELETE", { password });
    if (r?.error) { alert(err(r)); return; }
    alert("Аккаунт удалён. До свидания!");
    logout();
}

async function regenerateApiKey() {
    if (!confirm("Пересоздать API ключ? Старый перестанет работать.")) return;
    const r = await api("/v1/account/api-key", "POST");
    if (r?.error) { alert(err(r)); return; }
    document.getElementById("api-key").value = r.api_key;
}

async function redeemPromocode() {
    const code = document.getElementById("promocode-input").value.trim().toUpperCase();
    if (!code) { alert("Введите промокод"); return; }
    const resultEl = document.getElementById("promocode-result");
    resultEl.style.display = "none";
    
    const btn = document.getElementById("btn-redeem-promo");
    btn.disabled = true; btn.textContent = "Проверка...";
    
    const r = await api("/v1/promocodes/redeem", "POST", { code });
    
    btn.disabled = false; btn.textContent = "Активировать";
    resultEl.style.display = "block";
    
    if (r?.error) {
        resultEl.innerHTML = `<span style="color:#f55">Ошибка: ${err(r)}</span>`;
        return;
    }
    
    resultEl.innerHTML = `<span style="color:#4caf50">Промокод активирован! Тариф: ${r.plan}, на ${r.expires_days} дней</span>`;
    document.getElementById("promocode-input").value = "";
    
    // Refresh user data
    const me = await api("/auth/me");
    if (me?.id) user = me;
    loadPlans();
}

/* ==================== TABS ==================== */

function switchTab(name) {
    // Hide admin tab from non-admin users
    if (name === "admin" && user?.role !== "admin") {
        alert("Доступ только для администраторов");
        return;
    }
    document.querySelectorAll(".dash-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    document.querySelectorAll(".dash-panel").forEach(p => p.style.display = "none");
    const panel = document.getElementById("tab-" + name);
    if (panel) panel.style.display = "block";
    if (name === "plans") loadPlans();
    if (name === "admin") loadAdmin();
    if (name === "folders") loadFolders();
    if (name === "account") loadAccount();
}

/* ==================== EMAIL VERIFICATION ==================== */

async function verifyEmail(tokenParam) {
    const pg = document.getElementById("verify-page");
    pg.style.display = "flex";
    document.getElementById("verify-spinner").style.display = "block";
    document.getElementById("verify-actions").style.display = "none";
    const st = document.getElementById("verify-status");
    st.className = "verify-status";

    try {
        const res = await fetch(API + "/auth/verify-email?token=" + encodeURIComponent(tokenParam));
        const d = await res.json();
        document.getElementById("verify-spinner").style.display = "none";
        const title = document.getElementById("verify-title");
        const msg = document.getElementById("verify-message");
        const act = document.getElementById("verify-actions");
        act.style.display = "block";

        if (res.ok) {
            st.className = "verify-status success";
            title.textContent = "✓ Email подтверждён!";
            msg.textContent = "Аккаунт активирован. Теперь вы можете войти.";
            document.getElementById("verify-btn").textContent = "Войти";
            document.getElementById("verify-btn").onclick = () => { pg.style.display = "none"; showAuth("login"); };
            document.getElementById("verify-resend-btn").style.display = "none";
            localStorage.removeItem("auth_token"); token = null; user = null;
        } else {
            st.className = "verify-status error";
            title.textContent = "✗ Ошибка";
            msg.textContent = err(d);
            document.getElementById("verify-btn").textContent = "Попробовать снова";
            document.getElementById("verify-btn").onclick = () => { pg.style.display = "none"; showAuth("login"); };
        }
    } catch {
        document.getElementById("verify-spinner").style.display = "none";
        st.className = "verify-status error";
        document.getElementById("verify-title").textContent = "✗ Ошибка соединения";
        document.getElementById("verify-message").textContent = "Проверьте интернет.";
        document.getElementById("verify-actions").style.display = "block";
    }
}

async function resendVerification(email) {
    if (!email) { alert("Введите email"); return; }
    const r = await api("/auth/resend-verification", "POST", { email });
    alert(r?.error ? err(r) : "Письмо отправлено! Проверьте почту.");
}

function resendVerificationFromModal() { resendVerification(document.getElementById("verification-email").textContent); }
function resendVerificationFromSuccess() { resendVerification(document.getElementById("reg-success-email").textContent); }
function resendVerificationFromUrl() { const e = prompt("Введите email:"); if (e) resendVerification(e); }

/* ==================== PASSWORD STRENGTH ==================== */

function updatePasswordStrength() {
    const pw = document.getElementById("register-password").value;
    let s = 0;
    if (pw.length >= 8) s++; if (/[A-Z]/.test(pw)) s++; if (/[0-9]/.test(pw)) s++; if (/[^A-Za-z0-9]/.test(pw)) s++;
    const bar = document.getElementById("password-strength-bar");
    if (!bar) return;
    const levels = [{ w: "0%", c: "#e0e0e0", t: "Очень слабый" }, { w: "25%", c: "#f44336", t: "Слабый" }, { w: "50%", c: "#ff9800", t: "Средний" }, { w: "75%", c: "#4caf50", t: "Хороший" }, { w: "100%", c: "#0078d4", t: "Сильный" }];
    bar.style.width = levels[s].w; bar.style.background = levels[s].c;
    const txt = document.getElementById("password-strength-text");
    if (txt) txt.textContent = levels[s].t;
}

/* ==================== SHORTEN ==================== */

function toggleOptions() { const e = document.getElementById("search-options"); if (e) e.style.display = e.style.display === "none" ? "flex" : "none"; }
function toggleDashOptions() { const e = document.getElementById("dash-options"); if (e) e.style.display = e.style.display === "none" ? "flex" : "none"; }
function togglePassword(p) { const e = document.getElementById(p + "-password-row"); if (e) e.style.display = e.style.display === "none" ? "flex" : "none"; }
function toggleGeoOptions() { const e = document.getElementById("geo-options"); if (e) e.style.display = e.style.display === "none" ? "grid" : "none"; }
function toggleABOptions() { const e = document.getElementById("ab-options"); if (e) e.style.display = e.style.display === "none" ? "grid" : "none"; }

async function shortenUrl() {
    const url = document.getElementById("hero-url").value.trim();
    if (!url) { alert("Введите URL"); return; }
    
    const btn = document.getElementById("btn-shorten");
    btn.disabled = true; btn.textContent = "...";
    
    const body = { 
        url, 
        slug: document.getElementById("hero-slug")?.value.trim() || undefined, 
        title: document.getElementById("hero-title")?.value.trim() || undefined 
    };
    const pw = document.getElementById("hero-password")?.value;
    if (pw) { body.is_password_protected = true; body.password = pw; }
    
    // UTM params
    const utmSource = document.getElementById("utm-source")?.value.trim();
    const utmMedium = document.getElementById("utm-medium")?.value.trim();
    const utmCampaign = document.getElementById("utm-campaign")?.value.trim();
    if (utmSource) body.utm_source = utmSource;
    if (utmMedium) body.utm_medium = utmMedium;
    if (utmCampaign) body.utm_campaign = utmCampaign;
    
    // Geo-targeting
    const geoRU = document.getElementById("geo-ru")?.value.trim();
    const geoUS = document.getElementById("geo-us")?.value.trim();
    const geoEU = document.getElementById("geo-eu")?.value.trim();
    const geoTargets = {};
    if (geoRU?.startsWith("RU:")) geoTargets["RU"] = geoRU.replace("RU:", "").trim();
    if (geoUS?.startsWith("US:")) geoTargets["US"] = geoUS.replace("US:", "").trim();
    if (geoEU?.startsWith("EU:")) geoTargets["EU"] = geoEU.replace("EU:", "").trim();
    if (Object.keys(geoTargets).length > 0) body.geo_targets = geoTargets;
    
    // A/B testing
    const abUrl1 = document.getElementById("ab-url-1")?.value.trim();
    const abUrl2 = document.getElementById("ab-url-2")?.value.trim();
    const abUrl3 = document.getElementById("ab-url-3")?.value.trim();
    const abUrls = [];
    if (abUrl1?.startsWith("http")) abUrls.push(abUrl1);
    if (abUrl2?.startsWith("http")) abUrls.push(abUrl2);
    if (abUrl3?.startsWith("http")) abUrls.push(abUrl3);
    if (abUrls.length > 0) body.ab_urls = abUrls;
    
    // Try authenticated first, fall back to anonymous
    let r;
    if (token) {
        r = await api("/links", "POST", body);
        if (r?.id || r?.error?.includes("login") || r?.error?.includes("401")) {
            alert("Сессия истекла. Войдите снова.");
            logout(); return;
        }
    } else {
        // Anonymous with device_id
        const deviceId = getDeviceId();
        body.device_id = deviceId;
        body.is_anonymous = true;
        r = await api("/links/anonymous", "POST", body);
    }
    
    btn.disabled = false; btn.textContent = "Сократить";
    if (r?.id) {
        const sUrl = `${location.origin}/s/${r.slug}`;
        document.getElementById("result-link").href = sUrl; document.getElementById("result-link").textContent = sUrl;
        document.getElementById("result-card").style.display = "block";
if (r.qr_code) { const qr = document.getElementById("result-qr"); qr.src = r.qr_code; qr.style.display = "block"; qr.onclick = () => showQr(r.qr_code, sUrl, r.id); currentQrLinkId = r.id; }
        document.getElementById("hero-url").value = ""; document.getElementById("hero-slug").value = ""; document.getElementById("hero-password").value = "";
    } else alert("Ошибка:\n" + err(r));
}

async function dashShortenUrl() {
    const url = document.getElementById("dash-url").value.trim();
    if (!url) { alert("Введите URL"); return; }
    const btn = document.getElementById("btn-dash-shorten");
    btn.disabled = true; btn.textContent = "...";
    const folderId = document.getElementById("dash-folder-id")?.value;
    const body = { 
        url, 
        slug: document.getElementById("dash-slug")?.value.trim() || undefined, 
        title: document.getElementById("dash-title")?.value.trim() || undefined,
        folder_id: folderId ? parseInt(folderId) : undefined
    };
    const pw = document.getElementById("dash-password")?.value;
    if (pw) { body.is_password_protected = true; body.password = pw; }
    const r = await api("/links", "POST", body);
    btn.disabled = false; btn.textContent = "Сократить";
    if (r?.id) {
        const sUrl = `${location.origin}/s/${r.slug}`;
        document.getElementById("dash-result-link").href = sUrl; document.getElementById("dash-result-link").textContent = sUrl;
        document.getElementById("dash-result").style.display = "block";
        if (r.qr_code) { const qr = document.getElementById("dash-result-qr"); qr.src = r.qr_code; qr.style.display = "block"; qr.onclick = () => showQr(r.qr_code, sUrl, r.id); currentQrLinkId = r.id; }
        document.getElementById("dash-url").value = ""; document.getElementById("dash-slug").value = ""; document.getElementById("dash-password").value = "";
        loadLinks();
    } else alert("Ошибка:\n" + err(r));
}

function copyResult() { copyToClipboard(document.getElementById("result-link").textContent, document.querySelector("#result-card .btn-copy")); }
function copyDashResult() { copyToClipboard(document.getElementById("dash-result-link").textContent, document.querySelector("#dash-result .btn-copy")); }
function copyLink(t) { navigator.clipboard.writeText(t); }

function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        if (!btn) return;
        const orig = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18"><polyline points="20 6 9 17 4 12"/></svg> Скопировано!';
        setTimeout(() => btn.innerHTML = orig, 1500);
    });
}

/* ==================== QR MODAL ==================== */
let currentQrLinkId = null;

function showQr(code, url, linkId = null) {
    document.getElementById("qr-modal-img").src = code;
    document.getElementById("qr-modal-url").textContent = url;
    document.getElementById("qr-modal-title").textContent = "QR Код";
    document.getElementById("qr-modal-download").href = code;
    document.getElementById("qr-modal-download").download = `qr-${url.split("/").pop()}.png`;
    document.getElementById("qr-design").style.display = "none";
    currentQrLinkId = linkId;
    document.getElementById("qr-modal").style.display = "flex";
}

async function updateQRCustom() {
    if (!currentQrLinkId) {
        alert("QR-дизайн доступен из раздела 'Мои ссылки'");
        return;
    }
    const fill = document.getElementById("qr-fill-color").value;
    const back = document.getElementById("qr-back-color").value;
    console.log("QR colors:", fill, back);
    
    // Save colors to database first
    const saveR = await api(`/links/${currentQrLinkId}`, "PUT", { qr_fill_color: fill, qr_back_color: back });
    if (saveR?.error) { alert("Ошибка сохранения: " + err(saveR)); return; }
    
    // Then generate QR with colors
    const r = await api(`/links/${currentQrLinkId}/qr?fill=${encodeURIComponent(fill)}&back=${encodeURIComponent(back)}`);
    if (r?.qr_code) {
        document.getElementById("qr-modal-img").src = r.qr_code;
        document.getElementById("qr-modal-download").href = r.qr_code;
        document.getElementById("qr-modal-download").download = `qr-${fill.replace('#','')}-${back.replace('#','')}.png`;
    } else {
        alert("Ошибка: " + (r?.error || "Не удалось создать QR"));
    }
}

function hideQr() { document.getElementById("qr-modal").style.display = "none"; }

/* ==================== LINKS ==================== */

function esc(t) { if (!t) return ""; const d = document.createElement("div"); d.textContent = t; return d.innerHTML; }

function renderLink(link) {
    const sUrl = `${location.origin}/s/${link.slug}`;
    const date = new Date(link.created_at).toLocaleDateString("ru-RU", { month: "short", day: "numeric" });
    const lock = link.is_password_protected ? '<span class="link-badge badge-lock"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>Защищена</span>' : "";

    // Moderation status badge
    let modBadge = "";
    const ms = link.moderation_status || "";
    if (ms && ms !== "ok" && ms !== "pending" && ms !== "") {
        const labels = { blacklisted: "Чёрный список", phishing: "Фишинг", malware: "Malware", suspicious: "Подозр.", banned: "Забанен" };
        const colors = { blacklisted: "#880e4f", phishing: "#e65100", malware: "#c62828", suspicious: "#f57f17", banned: "#b71c1c" };
        modBadge = `<span class="link-badge" style="background:${colors[ms] || "#666"}22;color:${colors[ms] || "#666"}">${labels[ms] || ms}</span>`;
    } else if (ms === "pending") {
        modBadge = '<span class="link-badge" style="background:rgba(255,193,7,0.2);color:#ffc107">Проверка...</span>';
    }

    const qr = link.qr_code ? `<button class="btn-icon" title="QR" onclick='showQr("${link.qr_code}","${sUrl}",${link.id})'><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="2" y="2" width="8" height="8" rx="1"/><rect x="14" y="2" width="8" height="8" rx="1"/><rect x="2" y="14" width="8" height="8" rx="1"/><rect x="14" y="14" width="4" height="4"/><rect x="20" y="14" width="2" height="2"/><rect x="14" y="20" width="2" height="2"/><rect x="20" y="20" width="2" height="2"/></svg></button>` : "";

    const card = document.createElement("div");
    card.className = "link-card";
    card.innerHTML = `
        <div class="link-info">
            <div class="link-slug">${esc(link.title || link.slug)} ${lock} ${modBadge}</div>
            <div class="link-url">${esc(link.url)}</div>
        </div>
        <div class="link-meta">
            <div class="link-clicks"><div class="link-clicks-num">${link.clicks}</div><div class="link-clicks-label">переходов</div></div>
            <span style="opacity:.4;font-size:13px">${date}</span>
            <div class="link-actions">
                ${qr}
                <button class="btn-icon" title="Копировать" onclick="copyLink('${sUrl}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
                <button class="btn-icon" title="Статистика" onclick="showStats(${link.id})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></button>
                <button class="btn-icon danger" title="Удалить" onclick="deleteLink(${link.id})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg></button>
            </div>
        </div>`;
    return card;
}

async function loadLinks() {
    const q = document.getElementById("search-links")?.value || "";
    const r = await api(q ? `/links?q=${encodeURIComponent(q)}` : "/links");
    if (r?.error || !r?.links) return;
    const grid = document.getElementById("links-grid");
    grid.querySelectorAll(".link-card").forEach(e => e.remove());
    const empty = document.getElementById("links-empty");
    if (!r.links.length) { empty.style.display = ""; empty.querySelector("p").textContent = q ? "Ссылки не найдены." : "Пока нет ссылок."; return; }
    empty.style.display = "none";
    r.links.forEach(l => grid.appendChild(renderLink(l)));
}

function searchLinks() { clearTimeout(searchTimer); searchTimer = setTimeout(loadLinks, 300); }

async function deleteLink(id) {
    if (!confirm("Удалить ссылку?")) return;
    const r = await api(`/links/${id}`, "DELETE");
    if (r?.error) alert("Ошибка: " + err(r)); else loadLinks();
}

/* ==================== STATS ==================== */

function barChart(data, colors) {
    const total = Object.values(data).reduce((a, b) => a + b, 0);
    if (!total) return '<div class="bar-empty">Нет данных</div>';
    const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
    const c = colors || ["#0078d4", "#00b4d8", "#48cae4", "#90e0ef", "#caf0f8", "#ffd166", "#ef476f"];
    let h = '<div class="bar-stack">';
    sorted.forEach(([k, v], i) => { const p = (v / total * 100).toFixed(1); h += `<div class="bar-segment" style="width:${p}%;background:${c[i % c.length]}" title="${esc(k)}: ${v} (${p}%)"></div>`; });
    h += '</div><div class="bar-legend">';
    sorted.forEach(([k, v], i) => { const p = (v / total * 100).toFixed(1); h += `<div class="bar-legend-item"><span class="bar-dot" style="background:${c[i % c.length]}"></span><span class="bar-label">${esc(k)}</span><span class="bar-value">${v} <small>(${p}%)</small></span></div>`; });
    return h + '</div>';
}

let clicksChart = null;

async function showStats(linkId) {
    const r = await api(`/links/${linkId}/stats`);
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    document.getElementById("stats-title").textContent = "Статистика: " + r.slug;
    const ago = ts => { const d = Date.now() / 1000 - ts; if (d < 60) return Math.floor(d) + " сек"; if (d < 3600) return Math.floor(d / 60) + " мин"; if (d < 86400) return Math.floor(d / 3600) + " ч"; return new Date(ts * 1000).toLocaleString("ru-RU"); };
    const rows = (r.recent_clicks || []).map(c => `<tr><td>${ago(c.ts)}</td><td><span class="tag tag-${c.device_type}">${c.device_type === "desktop" ? "Компьютер" : c.device_type === "mobile" ? "��обильный" : c.device_type}</span></td><td>${esc(c.os)}</td><td>${esc(c.browser)}</td><td class="referer-cell">${c.referer === "direct" ? "<em>прямой</em>" : esc(c.referer)}</td><td class="ip-cell">${r.show_ip ? esc(c.ip) : "***"}</td></tr>`).join("");

    document.getElementById("stats-grid").innerHTML = `
        <div class="stats-summary">
            <div class="stat-big"><div class="stat-big-num">${r.total_clicks}</div><div class="stat-big-label">Всего кликов</div></div>
            <div class="stat-big"><div class="stat-big-num">${Object.keys(r.clicks_by_browser || {}).length}</div><div class="stat-big-label">Браузеров</div></div>
            <div class="stat-big"><div class="stat-big-num">${Object.keys(r.clicks_by_device || {}).length}</div><div class="stat-big-label">Устройств</div></div>
            <div class="stat-big"><div class="stat-big-num">${Object.keys(r.top_referrers || {}).length}</div><div class="stat-big-label">Источников</div></div>
        </div>
        <div class="stats-charts">
            <div class="chart-card"><h4>Устройства</h4>${barChart(r.clicks_by_device || {}, ["#0078d4", "#00b4d8", "#90e0ef"])}</div>
            <div class="chart-card"><h4>ОС</h4>${barChart(r.clicks_by_os || {})}</div>
            <div class="chart-card"><h4>Браузеры</h4>${barChart(r.clicks_by_browser || {})}</div>
        </div>
        <div class="chart-card"><h4>Источники</h4>${barChart(r.top_referrers || {})}</div>
        <div class="chart-card"><h4>Последние переходы</h4><div class="clicks-table-wrap"><table class="clicks-table"><thead><tr><th>Время</th><th>Устройство</th><th>ОС</th><th>Браузер</th><th>Источник</th><th>IP</th></tr></thead><tbody>${rows || "<tr><td colspan='6' style='text-align:center;opacity:.5'>Нет данных</td></tr>"}</tbody></table></div>`;
    
    // Render Chart.js line chart
    setTimeout(() => {
        const ctx = document.getElementById("clicks-chart")?.getContext("2d");
        if (!ctx) return;
        if (clicksChart) clicksChart.destroy();
        
        // Aggregate clicks by hour
        const clicksByHour = {};
        (r.recent_clicks || []).forEach(c => {
            const h = new Date(c.ts * 1000).toLocaleString("ru-RU", { hour: '2-digit', day: 'numeric' });
            clicksByHour[h] = (clicksByHour[h] || 0) + 1;
        });
        
        clicksChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Object.keys(clicksByHour).slice(-24),
                datasets: [{
                    label: 'Клики по времени',
                    data: Object.values(clicksByHour).slice(-24),
                    borderColor: '#0078d4',
                    backgroundColor: 'rgba(0,120,212,0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { ticks: { color: '#888' }, grid: { color: 'rgba(255,255,255,0.1)' }, beginAtZero: true }
                }
            }
        });
    }, 100);
    
    document.getElementById("stats-modal").style.display = "flex";
}

function hideStats() { document.getElementById("stats-modal").style.display = "none"; }

/* ==================== PLANS & PAYMENTS ==================== */

async function loadPlans() {
    const r = await api("/payments/plans");
    if (r?.error) return;
    const grid = document.getElementById("plans-grid");
    grid.innerHTML = "";
    const sub = await api("/payments/subscription/current");
    const cur = sub?.plan || user?.plan || "free";
    document.getElementById("current-plan-info").innerHTML = `Ваш тариф: <strong>${({ free: "Free", pro: "Pro", business: "Business" })[cur]}</strong>`;

    r.plans.forEach(plan => {
        const isCur = plan.id === cur;
        const isPop = plan.id === "pro";
        const boolF = ["custom_slug", "qr_codes", "password_protection", "api_access", "priority_support"];
        const fRu = { custom_slug: "Кастомные алиасы", qr_codes: "QR-коды", password_protection: "Защита паролем", api_access: "API доступ", priority_support: "Приоритетная поддержка" };
        let feats = "";
        boolF.forEach(f => feats += `<li class="${plan[f] ? '' : 'disabled'}">${fRu[f]}</li>`);
        feats += `<li>Ссылок: ${plan.links_limit >= 999999 ? "Безлимит" : plan.links_limit}</li>`;
        feats += `<li>Аналитика: ${plan.analytics_days} дней</li>`;

        let btn;
        if (isCur) btn = '<button class="btn-plan current" disabled>Текущий тариф</button>';
        else if (plan.price === 0) btn = '<button class="btn-plan current" disabled>Бесплатно</button>';
        else btn = `<button class="btn-plan primary" onclick="pay('${plan.id}')">Выбрать</button>`;

        const card = document.createElement("div");
        card.className = `plan-card${isCur ? ' current' : ''}${isPop ? ' popular' : ''}`;
        card.innerHTML = `${isPop ? '<div class="plan-badge">Популярный</div>' : ''}<div class="plan-name">${plan.name}</div><div class="plan-price">${plan.price === 0 ? 'Бесплатно' : plan.price + ' <small>руб/мес</small>'}</div><ul class="plan-features">${feats}</ul>${btn}`;
        grid.appendChild(card);
    });
    loadPayments();
    loadReferral();
}

async function loadReferral() {
    const r = await api("/referral");
    if (r?.error) return;
    const refLink = document.getElementById("referral-link");
    if (refLink && r.referral_link) {
        refLink.value = r.referral_link;
    }
    const refCount = document.getElementById("referral-count");
    if (refCount && r.referral_count !== undefined) {
        refCount.textContent = r.referral_count;
    }
    const refBonus = document.getElementById("referral-bonus");
    if (refBonus && r.bonus_earned !== undefined) {
        refBonus.textContent = r.bonus_earned;
    }
    const refPending = document.getElementById("referral-pending");
    if (refPending && r.pending_referrals !== undefined) {
        refPending.textContent = r.pending_referrals;
    }
}

async function loadReferralDetails() {
    const r = await api("/referral");
    if (r?.error) { alert(err(r)); return; }
    const details = document.getElementById("referral-details");
    const tbody = document.getElementById("referral-users-body");
    
    if (!r.referrals?.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;opacity:.5">Нет рефералов</td></tr>';
    } else {
        tbody.innerHTML = r.referrals.map(u => `<tr>
            <td>${esc(u.username)}</td>
            <td>${esc(u.email)}</td>
            <td><span class="admin-badge ${u.plan}">${u.plan}</span></td>
            <td>${new Date(u.created_at * 1000).toLocaleDateString("ru-RU")}</td>
        </tr>`).join("");
    }
    details.style.display = details.style.display === "none" ? "block" : "none";
}

async function pay(planId) {
    const prov = confirm("Оплатить через ЮKassa? (Отмена = Yandex Pay)") ? "yookassa" : "yandex_pay";
    const r = await api("/payments", "POST", { plan: planId, provider: prov });
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    if (r.confirmation_url?.includes("/demo/")) {
        const c = await api(`/payments/demo/${r.payment_id}`);
        if (!c?.error) { alert("Тариф активирован!"); const p = await api("/profile"); if (p?.id) user = p; loadPlans(); }
    } else if (r.confirmation_url) window.open(r.confirmation_url, "_blank");
}

async function loadPayments() {
    const r = await api("/payments");
    const el = document.getElementById("payment-history");
    if (r?.error || !r?.payments?.length) { el.style.display = "none"; return; }
    el.style.display = "block";
    const list = document.getElementById("payments-list");
    list.innerHTML = "";
    r.payments.forEach(p => {
        const d = document.createElement("div"); d.className = "payment-item";
        const s = { completed: "Оплачен", pending: "Ожидает", canceled: "Отменён" };
        d.innerHTML = `<span>${p.plan} — ${p.amount} ${p.currency}</span><span class="payment-status ${p.status}">${s[p.status] || p.status}</span><span style="opacity:.5">${new Date(p.created_at).toLocaleDateString("ru-RU")}</span>`;
        list.appendChild(d);
    });
}

/* ==================== ADMIN ==================== */

let adminPage = 1;

async function loadAdmin() {
    const r = await api("/admin/stats");
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    document.getElementById("admin-stats").innerHTML = [
        ["total_users", "Пользователей"], ["active_users", "Активных"], ["total_links", "Ссылок"],
        ["total_clicks", "Переходов"], ["links_today", "Сегодня"], ["clicks_today", "Кликов сегодня"],
        ["flagged_links", "Подозрительных"], ["banned_links", "Заблокировано"]
    ].map(([k, l]) => `<div class="admin-stat-card"><div class="admin-stat-num">${r[k]}</div><div class="admin-stat-label">${l}</div></div>`).join("");
    adminPage = 1; adminModPage = 1;
    adminSearch(); loadAdminPayments(); loadAdminModeration(); loadAdSettings();
}

async function adminSearch() {
    const s = document.getElementById("admin-search-users")?.value || "";
    const p = document.getElementById("admin-filter-plan")?.value || "";
    let ep = `/admin/users?page=${adminPage}&limit=20`;
    if (s) ep += `&search=${encodeURIComponent(s)}`;
    if (p) ep += `&plan=${p}`;
    const r = await api(ep);
    if (r?.error) return;
    const tb = document.getElementById("admin-users-body");
    tb.innerHTML = r.items.map(u => `<tr>
        <td>${u.id}</td>
        <td>${esc(u.username)}</td>
        <td>${esc(u.email)}</td>
        <td><span class="admin-badge ${u.plan}">${u.plan}</span></td>
        <td>${u.links_count}</td>
        <td>${u.referral_count || 0}</td>
        <td><span class="admin-badge ${u.is_active ? 'active' : 'inactive'}">${u.is_active ? 'Активен' : 'Забл.'}</span></td>
        <td class="admin-actions">
            <button class="btn-admin-edit" onclick="adminEdit(${u.id})">Изм.</button>
            <button class="btn-admin-view" onclick="adminViewRefs(${u.id})">Реф.</button>
            <button class="btn-admin-delete" onclick="adminDel(${u.id},'${esc(u.username)}')">Удл.</button>
        </td>
    </tr>`).join("");
    const pg = document.getElementById("admin-users-pagination");
    pg.innerHTML = "";
    for (let i = 1; i <= r.pages; i++) { const b = document.createElement("button"); b.textContent = i; b.className = i === r.page ? "active" : ""; b.onclick = () => { adminPage = i; adminSearch(); }; pg.appendChild(b); }
}

async function adminEdit(id) {
    const r = await api(`/admin/users/${id}`);
    if (r?.error) { alert(err(r)); return; }
    const refs = await api(`/admin/users/${id}/referrals`);
    const refInfo = refs?.referrals?.length ? `\nРефералов: ${refs.referrals.length}` : '';
    
    const currentSub = r.subscription ? `\nПодписка: ${r.subscription.plan || 'none'} (до ${r.subscription.expires_at ? new Date(r.subscription.expires_at * 1000).toLocaleDateString() : 'unknown'})` : '';
    
    const np = prompt(`Тариф (free/pro/business):\nТекущий: ${r.plan}${refInfo}${currentSub}`, r.plan);
    if (np === null) return;
    
    if (np !== r.plan) {
        if (np === 'pro' || np === 'business') {
            const action = confirm('Купить подписку? (Отмена = изменить тариф без оплаты)');
            if (action) {
                const pay = await api("/payments", "POST", { plan: np, user_id: id });
                if (pay?.payment_id) {
                    await api(`/payments/demo/${pay.payment_id}`);
                    alert('Подписка активирована!');
                }
            }
            await api(`/admin/users/${id}`, "PUT", { plan: np });
        } else if (r.plan !== 'free' && np === 'free') {
            const cancelAction = confirm('Отменить подписку?\nOK = отмена (сохранит оплаченные дни)\nОтмена = только изменить тариф');
            if (cancelAction) {
                await api(`/admin/users/${id}/cancel`, "POST");
                await api(`/admin/users/${id}`, "PUT", { plan: np });
                alert('Подписка отменена');
            } else {
                await api(`/admin/users/${id}`, "PUT", { plan: np });
            }
        } else {
            await api(`/admin/users/${id}`, "PUT", { plan: np });
        }
    }
    
    if (confirm('Продлить подписку на 30 дней?')) {
        const ext = await api(`/admin/users/${id}/extend`, "POST", { days: 30 });
        if (ext?.error) alert('Ошибка продления: ' + err(ext));
        else alert('Подписка продлена до ' + new Date(ext.new_expires_at * 1000).toLocaleDateString());
    }
    
    const nr = prompt(`Роль (user/admin):\nТекущая: ${r.role}`, r.role);
    if (nr === null) return;
    const na = confirm(`Активен? (Сейчас: ${r.is_active ? "Да" : "Нет"})`);
    const u = await api(`/admin/users/${id}`, "PUT", { plan: np || r.plan, role: nr, is_active: na });
    if (u?.error) alert(err(u)); else adminSearch();
}

async function adminDel(id, name) {
    if (!confirm(`Удалить ${name}?`)) return;
    const r = await api(`/admin/users/${id}`, "DELETE");
    if (r?.error) alert(err(r)); else adminSearch();
}

async function adminViewRefs(id) {
    const r = await api(`/admin/users/${id}/referrals`);
    if (r?.error) { alert(err(r)); return; }
    if (!r.referrals?.length) { alert('Нет рефералов'); return; }
    const list = r.referrals.map(u => `${u.username} (${u.email}) - ${u.plan}`).join('\n');
    alert(`Рефералы пользователя:\n\n${list}`);
}

async function loadAdminPayments() {
    const r = await api("/admin/payments?limit=20");
    if (r?.error) return;
    document.getElementById("admin-payments-body").innerHTML = r.items.map(p => `<tr><td>${p.payment_id.slice(0, 8)}…</td><td>${esc(p.username)}</td><td>${p.provider}</td><td><span class="admin-badge ${p.plan}">${p.plan}</span></td><td>${p.amount} ${p.currency}</td><td><span class="payment-status ${p.status}">${p.status}</span></td><td>${new Date(p.created_at).toLocaleDateString("ru-RU")}</td></tr>`).join("");
}

/* ==================== MODERATION ==================== */

let adminModPage = 1;

const MOD_STATUS_LABELS = { ok: "Ок", pending: "Проверка", blacklisted: "Чёрный список", phishing: "Фишинг", malware: "Malware", suspicious: "Подозр.", banned: "Забанен" };

async function loadAdminModeration() {
    const modFilter = document.getElementById("admin-filter-mod")?.value || "";
    let ep = `/admin/links/moderation?page=${adminModPage}&limit=20`;
    if (modFilter) {
        if (modFilter === "flagged") ep += "&status=flagged";
        else if (modFilter === "banned") ep += "&status=banned";
        else ep += `&mod_status=${modFilter}`;
    }
    const r = await api(ep);
    if (r?.error) return;
    const tb = document.getElementById("admin-mod-body");
    tb.innerHTML = r.items.map(l => {
        const sClass = l.moderation_status === "ok" ? "active" : (l.moderation_status === "pending" ? "pending" : "inactive");
        return `<tr>
            <td>${l.id}</td>
            <td>${esc(l.slug)}</td>
            <td class="referer-cell" title="${esc(l.url)}">${esc(l.url.slice(0, 50))}</td>
            <td><span class="admin-badge ${sClass}">${MOD_STATUS_LABELS[l.moderation_status] || l.moderation_status}</span></td>
            <td style="max-width:200px;white-space:normal;font-size:12px">${esc(l.moderation_reason)}</td>
            <td>${esc(l.username)}</td>
            <td class="admin-actions">
                ${l.is_active ? `<button class="btn-admin-delete" onclick="adminBanLink(${l.id},'${esc(l.slug)}')">Бан</button>` : `<button class="btn-admin-edit" onclick="adminUnbanLink(${l.id})">Разбан</button>`}
                <button class="btn-admin-edit" onclick="adminRecheckLink(${l.id})">Проверить</button>
            </td>
        </tr>`;
    }).join("");
    // Pagination
    const pg = document.getElementById("admin-mod-pagination");
    pg.innerHTML = "";
    const pages = Math.ceil(r.total / r.limit);
    for (let i = 1; i <= pages; i++) {
        const b = document.createElement("button");
        b.textContent = i; b.className = i === r.page ? "active" : "";
        b.onclick = () => { adminModPage = i; loadAdminModeration(); };
        pg.appendChild(b);
    }
}

async function adminBanLink(id, slug) {
    const reason = prompt(`Причина бана для ${slug}:`, "Нарушение правил");
    if (!reason) return;
    const r = await api(`/admin/links/${id}/ban`, "PUT", { reason });
    if (r?.error) alert(err(r)); else loadAdminModeration();
}

async function adminUnbanLink(id) {
    if (!confirm("Разблокировать ссылку?")) return;
    const r = await api(`/admin/links/${id}/unban`, "PUT");
    if (r?.error) alert(err(r)); else loadAdminModeration();
}

async function adminRecheckLink(id) {
    const r = await api(`/admin/links/${id}/recheck`, "POST");
    if (r?.error) { alert(err(r)); return; }
    const res = r.result;
    alert(res.safe ? "Ссылка безопасна" : `Обнаружена угроза: ${res.status} — ${res.reason}`);
    loadAdminModeration();
}

/* ==================== AD SETTINGS ==================== */

async function loadAdSettings() {
    const r = await api("/admin/settings/ads");
    if (r?.error) return;
    document.getElementById("ad-enabled").checked = r.ad_enabled === "true";
    document.getElementById("ad-delay").value = r.ad_delay_seconds || "5";
    document.getElementById("ad-title").value = r.ad_title || "Подождите...";
    document.getElementById("ad-skip-text").value = r.ad_skip_text || "Перейти к ссылке";
    document.getElementById("ad-exempt").value = r.ad_plans_exempt || "pro,business";
    document.getElementById("ad-html").value = r.ad_html || "";
    
    loadPromocodes();
}

async function saveAdSettings() {
    // Escape HTML to prevent breaking the site
    const escapeHtml = (str) => str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    
    let adHtml = document.getElementById("ad-html").value || "";
    // Only escape if not already escaped and contains potentially dangerous content
    if (adHtml.includes('<script') || adHtml.includes('</')) {
        // Store as-is, the backend will handle it
    }
    
    const data = {
        ad_enabled: document.getElementById("ad-enabled").checked ? "true" : "false",
        ad_delay_seconds: document.getElementById("ad-delay").value || "5",
        ad_title: document.getElementById("ad-title").value || "Подождите...",
        ad_skip_text: document.getElementById("ad-skip-text").value || "Перейти к ссылке",
        ad_plans_exempt: document.getElementById("ad-exempt").value || "pro,business",
        ad_html: adHtml,
    };
    const r = await api("/admin/settings/ads", "PUT", data);
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    alert("Настройки рекламы сохранены");
}

/* ==================== SYSTEM SETTINGS ==================== */

let systemSettingsData = {};

async function loadSystemSettings() {
    const r = await api("/admin/settings");
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    
    systemSettingsData = r.defaults || {};
    const overrides = r.overrides || {};
    
    const grid = document.getElementById("settings-grid");
    grid.innerHTML = "";
    
    const editableKeys = [
        "JWT_EXPIRATION_HOURS", "RATE_LIMIT_REGISTER", "RATE_LIMIT_LOGIN", 
        "RATE_LIMIT_CREATE_LINK", "FREE_PLAN_LIMIT", "PRO_PLAN_LIMIT", 
        "PRO_PLAN_PRICE", "BUSINESS_PLAN_PRICE", "MODERATION_ENABLED",
        "AUTO_BAN_ON_DETECTION", "QR_CODE_SIZE", "BCRYPT_ROUNDS"
    ];
    
    const nonEditable = ["JWT_SECRET", "YOOKASSA_SECRET_KEY", "YANDEX_PAY_SECRET_KEY", "SMTP_PASSWORD", "ADMIN_PASSWORD"];
    
    editableKeys.forEach(key => {
        const val = overrides[key] !== undefined ? overrides[key] : (systemSettingsData[key] || "");
        const isOverridden = overrides[key] !== undefined;
        
        const row = document.createElement("div");
        row.className = "settings-row";
        row.innerHTML = `
            <label>${key}</label>
            <input type="text" class="settings-input" data-key="${key}" value="${esc(val)}" ${nonEditable.includes(key) ? "readonly" : ""}>
            ${isOverridden ? '<span class="settings-badge">БД</span>' : '<span class="settings-badge default">по умолч.</span>'}
        `;
        grid.appendChild(row);
    });
    
    document.getElementById("system-settings").style.display = "block";
}

async function saveSystemSettings() {
    const inputs = document.querySelectorAll(".settings-input");
    const data = {};
    
    inputs.forEach(inp => {
        const key = inp.dataset.key;
        const val = inp.value;
        if (val !== String(systemSettingsData[key] || "")) {
            data[key] = val;
        }
    });
    
    if (Object.keys(data).length === 0) {
        alert("Нет изменений");
        return;
    }
    
    const r = await api("/admin/settings", "PUT", data);
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    
    alert("Настройки сохранены в базу данных");
    loadSystemSettings();
}

/* ==================== PROMOCODES (ADMIN) ==================== */

async function loadPromocodes() {
    const r = await api("/v1/promocodes");
    if (r?.error) return;
    const tb = document.getElementById("admin-promo-body");
    if (!r.items?.length) {
        tb.innerHTML = '<tr><td colspan="7" style="text-align:center;opacity:.5">Нет промокодов</td></tr>';
        return;
    }
    const now = Date.now() / 1000;
    tb.innerHTML = r.items.map(p => {
        const isExpired = p.expires_at > 0 && now > p.expires_at;
        const isActive = p.is_active && !isExpired;
        const isUsedUp = p.used_count >= p.max_uses;
        const status = !p.is_active ? "Выкл" : isExpired ? "Истёк" : isUsedUp ? "Использован" : "Активен";
        const statusClass = isActive ? "active" : "inactive";
        return `<tr>
            <td><strong>${esc(p.code)}</strong></td>
            <td><span class="admin-badge ${p.plan}">${p.plan}</span></td>
            <td>${p.duration_days}</td>
            <td>${p.used_count}</td>
            <td>${p.max_uses}</td>
            <td><span class="admin-badge ${statusClass}">${status}</span></td>
            <td class="admin-actions">
                <button class="btn-admin-delete" onclick="deletePromocode(${p.id}, '${esc(p.code)}')">Удалить</button>
            </td>
        </tr>`;
    }).join("");
}

async function showCreatePromocode() {
    const code = prompt("Введите код промокода (минимум 4 символа):");
    if (!code || code.length < 4) { alert("Код слишком короткий"); return; }
    const plan = prompt("Тариф (pro/business):", "pro");
    if (!plan || !["pro", "business"].includes(plan)) { alert("Неверный тариф"); return; }
    const days = prompt("Дней:", "30");
    const daysNum = parseInt(days) || 30;
    const uses = prompt("Лимит использований:", "1");
    const usesNum = parseInt(uses) || 1;
    const expires = prompt("Истекает через (часов, 0 = никогда):", "0");
    const expiresNum = parseInt(expires) || 0;
    
    const r = await api("/v1/promocodes", "POST", { 
        code: code.toUpperCase(), 
        plan, 
        duration_days: daysNum, 
        max_uses: usesNum,
        expires_hours: expiresNum 
    });
    if (r?.error) { alert("Ошибка: " + err(r)); return; }
    alert("Промокод создан!");
    loadPromocodes();
}

async function deletePromocode(id, code) {
    if (!confirm(`Удалить промокод ${code}?`)) return;
    const r = await api(`/v1/promocodes/${id}`, "DELETE");
    if (r?.error) { alert(err(r)); return; }
    loadPromocodes();
}

/* ==================== CLEANUP ==================== */

async function runCleanup() {
    if (!confirm("Запустить очистку базы данных? Удалятся просроченные ссылки и клики старше 90 дней.")) return;
    const resultEl = document.getElementById("cleanup-result");
    resultEl.style.display = "none";
    resultEl.innerHTML = "Выполнение...";
    resultEl.style.display = "block";
    
    const r = await api("/admin/cleanup", "POST");
    resultEl.style.display = "none";
    if (r?.error) { alert(err(r)); return; }
    resultEl.innerHTML = `<span style="color:#4caf50">Очистка завершена: ${r.expired_links} ссылок, ${r.old_clicks} кликов удалено</span>`;
    resultEl.style.display = "block";
}

/* ==================== INIT ==================== */

document.addEventListener("DOMContentLoaded", () => {
    refreshCaptcha();
    document.getElementById("register-password")?.addEventListener("input", updatePasswordStrength);
    
    // Bind all button clicks via JS (not inline onclick)
    document.getElementById("brand-logo")?.addEventListener("click", goHome);
    document.getElementById("my-links-btn")?.addEventListener("click", () => { goDashboard(); switchTab("links"); });
    document.getElementById("dashboard-tab-btn")?.addEventListener("click", () => { goDashboard(); switchTab("admin"); });
    document.getElementById("btn-show-login")?.addEventListener("click", () => showAuth("login"));
    document.getElementById("btn-show-register")?.addEventListener("click", () => showAuth("register"));
    document.getElementById("btn-logout")?.addEventListener("click", logout);
    document.getElementById("btn-shorten")?.addEventListener("click", shortenUrl);
    document.getElementById("btn-copy")?.addEventListener("click", copyResult);
    document.getElementById("btn-copy-referral")?.addEventListener("click", () => {
        const refLink = document.getElementById("referral-link").value;
        copyToClipboard(refLink, document.getElementById("btn-copy-referral"));
    });
    document.getElementById("btn-dash-shorten")?.addEventListener("click", dashShortenUrl);
    
    // Modal closes
    document.querySelectorAll(".modal-close").forEach(b => {
        b.addEventListener("click", () => {
            const modal = b.closest("[id$='-modal']");
            if (modal) modal.style.display = "none";
        });
    });
    
    // Options toggles
    document.querySelectorAll(".btn-options-toggle").forEach(b => {
        b.addEventListener("click", () => {
            const txt = b.textContent || "";
            if (txt.includes("Доп")) toggleOptions();
            else if (txt.includes("Пароль")) togglePassword("hero");
            else if (txt.includes("Гео")) toggleGeoOptions();
            else if (txt.includes("A/B")) toggleABOptions();
        });
    });
    
    // Folder create
    document.getElementById("btn-create-folder")?.addEventListener("click", createFolder);
    
    // Bulk create
    document.getElementById("btn-bulk-create")?.addEventListener("click", bulkCreate);
    document.getElementById("bulk-password")?.addEventListener("change", e => {
        document.getElementById("bulk-password-value").style.display = e.target.checked ? "block" : "none";
    });
    
    // Account
    document.getElementById("btn-change-password")?.addEventListener("click", changePassword);
    document.getElementById("btn-change-email")?.addEventListener("click", changeEmail);
    document.getElementById("btn-delete-account")?.addEventListener("click", deleteAccount);
    document.getElementById("btn-copy-api-key")?.addEventListener("click", () => {
        copyToClipboard(document.getElementById("api-key").value, document.getElementById("btn-copy-api-key"));
    });
    document.getElementById("btn-regenerate-api-key")?.addEventListener("click", regenerateApiKey);
    document.getElementById("btn-redeem-promo")?.addEventListener("click", redeemPromocode);
    document.getElementById("btn-redeem-promo-tab")?.addEventListener("click", redeemPromocode);
    
    // Export/Import
    document.getElementById("btn-export-csv")?.addEventListener("click", exportCsv);
    document.getElementById("btn-export-json")?.addEventListener("click", exportJson);
    document.getElementById("btn-import")?.addEventListener("click", importFile);
    
    // Ad preview
    document.getElementById("btn-preview-ad")?.addEventListener("click", () => {
        window.open(API + "/v1/ad/iframe", "_blank", "width=400,height=500");
    });

    // Tab clicks
    document.querySelectorAll(".dash-tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));

    // Admin filters
    document.getElementById("admin-search-users")?.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(adminSearch, 300); });
    document.getElementById("admin-filter-plan")?.addEventListener("change", adminSearch);
    document.getElementById("admin-filter-mod")?.addEventListener("change", () => { adminModPage = 1; loadAdminModeration(); });

    // URL params
    const p = new URLSearchParams(location.search);
    if (p.get("verify")) { verifyEmail(p.get("verify")); history.replaceState({}, "", location.pathname); return; }
    if (p.get("reset")) {
        const pw = prompt("Новый пароль:");
        if (pw) api("/auth/password-reset-confirm", "POST", { token: p.get("reset"), new_password: pw })
            .then(() => alert("Пароль изменён!")).catch(() => alert("Ошибка"));
        return;
    }

    // Auto-login
    if (token) {
        api("/auth/me").then(r => {
            if (r?.id) {
                if (r.email_verified) { 
                    user = r; onLogin(); 
                } else {
                    localStorage.removeItem("auth_token");
                    token = null;
                    document.getElementById("verification-email").textContent = r.email;
                    document.getElementById("verification-required-modal").style.display = "flex";
                }
            } else {
                console.log("Auth failed:", r);
                logout();
            }
        }).catch(e => {
            console.log("Auth error:", e);
            logout();
        });
    }

    // Form handlers
    document.getElementById("login-form")?.addEventListener("submit", e => { e.preventDefault(); login(); });
    document.getElementById("register-form")?.addEventListener("submit", e => { e.preventDefault(); register(); });
    document.getElementById("forgot-form")?.addEventListener("submit", e => { e.preventDefault(); forgotPassword(); });
    document.getElementById("main-shorten-form")?.addEventListener("submit", e => { e.preventDefault(); shortenUrl(); });
    document.getElementById("dash-shorten-form")?.addEventListener("submit", e => { e.preventDefault(); dashShortenUrl(); });
    document.getElementById("search-links")?.addEventListener("input", searchLinks);
    
    // Also add direct click handlers for form buttons (mobile backup)
    document.querySelectorAll("button[type=submit]").forEach(b => {
        b.addEventListener("click", e => {
            e.preventDefault();
            if (b.id === "btn-shorten") shortenUrl();
            else if (b.id === "btn-dash-shorten") dashShortenUrl();
            else if (b.form?.id === "login-form") login();
            else if (b.form?.id === "register-form") register();
            else if (b.form?.id === "forgot-form") forgotPassword();
        });
    });

    // Modal close on backdrop
    ["auth-modal", "stats-modal", "qr-modal", "verification-required-modal"].forEach(id => {
        document.getElementById(id)?.addEventListener("click", e => { if (e.target === e.currentTarget) e.target.style.display = "none"; });
    });
});

// Expose all functions to window for inline onclick handlers
window.showAuth = showAuth;
window.hideAuth = hideAuth;
window.goHome = goHome;
window.goDashboard = goDashboard;
window.logout = logout;
window.shortenUrl = shortenUrl;
window.dashShortenUrl = dashShortenUrl;
window.copyResult = copyResult;
window.copyDashResult = copyDashResult;
window.toggleOptions = toggleOptions;
window.toggleDashOptions = toggleDashOptions;
window.togglePassword = togglePassword;
window.toggleGeoOptions = toggleGeoOptions;
window.toggleABOptions = toggleABOptions;
window.showQr = showQr;
window.hideQr = hideQr;
window.hideStats = hideStats;
window.refreshCaptcha = refreshCaptcha;
window.hideVerificationRequired = hideVerificationRequired;
window.resendVerificationFromModal = resendVerificationFromModal;
window.resendVerificationFromSuccess = resendVerificationFromSuccess;
window.resendVerificationFromUrl = resendVerificationFromUrl;
window.saveAdSettings = saveAdSettings;
window.loadSystemSettings = loadSystemSettings;
window.saveSystemSettings = saveSystemSettings;
window.updateQRCustom = updateQRCustom;
window.copyLink = copyLink;
window.redeemPromocode = redeemPromocode;
window.showCreatePromocode = showCreatePromocode;
window.deletePromocode = deletePromocode;
window.runCleanup = runCleanup;
window.loadReferralDetails = loadReferralDetails;
