const DEFAULT_API = 'https://qntx.ru';

// Get current tab URL
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
        document.getElementById('current-url').value = tabs[0].url;
    }
});

// Load settings
chrome.storage.sync.get(['apiUrl', 'apiToken'], (data) => {
    if (data.apiUrl) document.getElementById('api-url').value = data.apiUrl;
    if (data.apiToken) document.getElementById('api-token').value = data.apiToken;
});

async function getApiBase() {
    const url = document.getElementById('api-url').value.trim() || DEFAULT_API;
    return url.replace(/\/$/, '') + '/api';
}

async function getToken() {
    return document.getElementById('api-token').value.trim() || '';
}

async function shorten() {
    const url = document.getElementById('current-url').value.trim();
    const slug = document.getElementById('custom-slug').value.trim();
    const btn = document.getElementById('btn-shorten');
    const error = document.getElementById('error');
    const result = document.getElementById('result');

    if (!url) { showError('Нет URL'); return; }

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    error.style.display = 'none';
    result.classList.remove('show');

    try {
        const apiBase = await getApiBase();
        const token = await getToken();

        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const body = { url };
        if (slug) body.slug = slug;

        const resp = await fetch(apiBase + '/links', {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });

        const data = await resp.json();

        if (!resp.ok) {
            showError(data.detail || 'Ошибка создания ссылки');
            return;
        }

        const shortUrl = `${apiBase.replace('/api', '')}/s/${data.slug}`;

        document.getElementById('short-url').href = shortUrl;
        document.getElementById('short-url').textContent = shortUrl;
        result.classList.add('show');

        // QR
        if (data.qr_code) {
            const qr = document.getElementById('qr-img');
            qr.src = data.qr_code;
            qr.style.display = 'block';
        }

        // Auto-copy
        navigator.clipboard.writeText(shortUrl);

    } catch (e) {
        showError('Ошибка: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Сократить';
    }
}

function showError(msg) {
    const el = document.getElementById('error');
    el.textContent = msg;
    el.style.display = 'block';
}

function copyShort() {
    const url = document.getElementById('short-url').textContent;
    navigator.clipboard.writeText(url).then(() => {
        const btn = document.querySelector('.copy-btn');
        btn.textContent = '✓';
        setTimeout(() => btn.textContent = 'Копировать', 1500);
    });
}

function share(network) {
    const url = document.getElementById('short-url').textContent;
    const encoded = encodeURIComponent(url);
    const urls = {
        telegram: `https://t.me/share/url?url=${encoded}`,
        vk: `https://vk.com/share.php?url=${encoded}`,
        whatsapp: `https://wa.me/?text=${encoded}`,
    };
    if (urls[network]) {
        chrome.tabs.create({ url: urls[network] });
    }
}

function downloadQR() {
    const img = document.getElementById('qr-img');
    const a = document.createElement('a');
    a.href = img.src;
    a.download = 'beacon-qr.png';
    a.click();
}

function toggleSettings() {
    document.getElementById('settings-body').classList.toggle('show');
}

function saveSettings() {
    const apiUrl = document.getElementById('api-url').value.trim();
    const apiToken = document.getElementById('api-token').value.trim();
    chrome.storage.sync.set({ apiUrl, apiToken }, () => {
        const btn = document.querySelector('.settings-body .btn');
        btn.textContent = '✓ Сохранено';
        setTimeout(() => btn.textContent = 'Сохранить', 1500);
    });
}

// Keyboard shortcut: Enter to shorten
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.target.closest('.settings-body')) {
        shorten();
    }
});
