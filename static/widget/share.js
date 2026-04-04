/**
 * QNTX.Beacon Share Widget
 * 
 * Usage:
 *   <script src="https://qntx.ru/static/widget/share.js" data-domain="qntx.ru"></script>
 *   <div class="beacon-share" data-url="https://example.com/page" data-title="Check this out!"></div>
 * 
 * Or programmatic:
 *   BeaconShare.init({ domain: 'qntx.ru' });
 *   BeaconShare.create('https://example.com', { title: 'My link' });
 */
(function() {
    'use strict';

    const CONFIG = {
        domain: 'qntx.ru',
        apiBase: 'https://qntx.ru/api',
        theme: 'auto', // 'light', 'dark', 'auto'
        position: 'bottom-right', // 'bottom-right', 'bottom-left', 'inline'
        showQR: true,
        showCount: true,
        networks: ['telegram', 'vk', 'whatsapp', 'copy'],
    };

    const ICONS = {
        telegram: '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/></svg>',
        vk: '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M13.162 18.994c.ʓ 0 .321-.008.44-.046a.506.506 0 00.234-.174c.076-.1.108-.243.108-.422v-2.493h1.72c.19 0 .345-.03.464-.091a.504.504 0 00.265-.265c.06-.12.09-.275.09-.465v-.266a.635.635 0 00-.09-.392.65.65 0 00-.264-.264.95.95 0 00-.465-.091h-1.72v-1.363h2.59c.19 0 .345-.03.464-.09a.505.505 0 00.266-.266c.06-.12.09-.275.09-.465V9.692a.634.634 0 00-.09-.391.648.648 0 00-.266-.265.948.948 0 00-.464-.09H13.74V7.58c.76-.113 1.356-.424 1.788-.934.432-.51.648-1.155.648-1.936v-.227a.95.95 0 00-.09-.465.505.505 0 00-.266-.265.947.947 0 00-.464-.09h-1.927a.506.506 0 00-.355.137.482.482 0 00-.137.354v.683c0 .266-.037.47-.11.61-.075.14-.19.266-.346.382a1.368 1.368 0 01-.565.265 4.07 4.07 0 01-.721.091c-.347 0-.664-.046-.952-.137a2.28 2.28 0 01-.776-.421 1.883 1.883 0 01-.528-.647c-.129-.256-.192-.557-.192-.906v-.407a.948.948 0 00-.09-.465.505.505 0 00-.266-.265.947.947 0 00-.464-.09H6.26a.95.95 0 00-.465.09.505.505 0 00-.265.266.634.634 0 00-.09.391v.407c0 .395-.063.744-.191 1.047a2.287 2.287 0 01-.528.759c-.23.22-.496.386-.8.5a3.16 3.16 0 01-.97.265 5.98 5.98 0 01-1.017.073.948.948 0 00-.465.09.506.506 0 00-.265.266.948.948 0 00-.09.464v1.33c0 .19.03.345.09.464a.506.506 0 00.265.266c.12.06.275.09.465.09h1.46v1.364H3.49a.95.95 0 00-.465.09.506.506 0 00-.265.265.634.634 0 00-.09.392v.265c0 .19.03.345.09.465a.506.506 0 00.265.265c.12.061.275.091.465.091h1.46v2.492c0 .459-.16.828-.478 1.108a1.593 1.593 0 01-1.083.418c-.22 0-.456-.025-.708-.073-.252-.05-.456-.117-.61-.202a.506.506 0 01-.266-.265.95.95 0 01-.09-.465v-2.64a.95.95 0 00-.09-.465.506.506 0 00-.265-.265.948.948 0 00-.465-.09H.56a.95.95 0 00-.465.09.506.506 0 00-.265.265.634.634 0 00-.09.392v.662c0 1.225.37 2.148 1.108 2.768.738.62 1.742.93 3.012.93h.664c1.147 0 2.123-.248 2.927-.745.803-.496 1.393-1.183 1.768-2.061a5.45 5.45 0 00.36-1.047h.164c.572.99 1.356 1.71 2.353 2.16.997.45 2.103.674 3.318.674h.737a.95.95 0 00.465-.09.506.506 0 00.265-.266.95.95 0 00.09-.464v-.683z"/></svg>',
        whatsapp: '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>',
        copy: '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>',
        link: '<svg viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/></svg>',
        close: '<svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
    };

    const STYLES = `
.beacon-share-widget{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;display:inline-flex;align-items:center;gap:8px;padding:8px 12px;background:rgba(0,0,0,.05);border-radius:12px;transition:all .3s}
.beacon-share-widget:hover{background:rgba(0,0,0,.08)}
.beacon-share-btn{display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:10px;border:none;background:rgba(0,0,0,.06);color:#333;cursor:pointer;transition:all .2s}
.beacon-share-btn:hover{background:rgba(0,0,0,.12);transform:scale(1.1)}
.beacon-share-btn.telegram{color:#0088cc}.beacon-share-btn.vk{color:#4a76a8}.beacon-share-btn.whatsapp{color:#25d366}
.beacon-share-short{font-size:13px;font-weight:500;color:#0078d4;text-decoration:none;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.beacon-share-popup{position:fixed;bottom:20px;right:20px;background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.15);padding:20px;z-index:99999;min-width:280px;animation:beaconSlideUp .3s ease;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
.beacon-share-popup.dark{background:#1a1a2e;color:#fff}
.beacon-share-popup h3{font-size:16px;margin:0 0 12px;font-weight:600}
.beacon-share-popup .beacon-short-url{display:flex;gap:8px;margin-bottom:12px}
.beacon-share-popup .beacon-short-url input{flex:1;padding:8px 12px;border:1px solid #ddd;border-radius:8px;font-size:13px;background:transparent;color:inherit}
.beacon-share-popup .beacon-short-url button{padding:8px 14px;background:#0078d4;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500}
.beacon-share-popup .beacon-networks{display:flex;gap:6px;justify-content:center;margin-top:8px}
.beacon-share-popup .beacon-close{position:absolute;top:10px;right:10px;background:none;border:none;color:#999;cursor:pointer}
.beacon-share-popup .beacon-qr{display:block;margin:12px auto 0;border-radius:8px}
@keyframes beaconSlideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
    `;

    let initialized = false;

    function injectStyles() {
        if (document.getElementById('beacon-share-styles')) return;
        const style = document.createElement('style');
        style.id = 'beacon-share-styles';
        style.textContent = STYLES;
        document.head.appendChild(style);
    }

    async function shortenUrl(url) {
        try {
            const resp = await fetch(CONFIG.apiBase + '/links', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });
            if (!resp.ok) return null;
            const data = await resp.json();
            return data.slug ? `https://${CONFIG.domain}/s/${data.slug}` : null;
        } catch {
            return null;
        }
    }

    function shareTo(network, url, title) {
        const encodedUrl = encodeURIComponent(url);
        const encodedTitle = encodeURIComponent(title || '');
        const urls = {
            telegram: `https://t.me/share/url?url=${encodedUrl}&text=${encodedTitle}`,
            vk: `https://vk.com/share.php?url=${encodedUrl}&title=${encodedTitle}`,
            whatsapp: `https://wa.me/?text=${encodedTitle}%20${encodedUrl}`,
        };
        if (urls[network]) {
            window.open(urls[network], '_blank', 'width=600,height=400');
        }
    }

    function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showToast('Скопировано!');
        });
    }

    function showToast(msg) {
        const toast = document.createElement('div');
        toast.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:8px;font-size:14px;z-index:999999;animation:beaconSlideUp .3s ease';
        toast.textContent = msg;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    }

    function createInlineWidget(el) {
        const url = el.dataset.url || window.location.href;
        const title = el.dataset.title || document.title;
        const theme = el.dataset.theme || CONFIG.theme;

        const widget = document.createElement('div');
        widget.className = 'beacon-share-widget';

        // Short link
        const shortLink = document.createElement('a');
        shortLink.className = 'beacon-share-short';
        shortLink.href = url;
        shortLink.target = '_blank';
        shortLink.textContent = 'Сократить...';
        widget.appendChild(shortLink);

        // Network buttons
        CONFIG.networks.forEach(net => {
            if (net === 'copy') {
                const btn = document.createElement('button');
                btn.className = 'beacon-share-btn';
                btn.innerHTML = ICONS.copy;
                btn.title = 'Копировать';
                btn.onclick = () => copyToClipboard(shortLink.href);
                widget.appendChild(btn);
            } else {
                const btn = document.createElement('button');
                btn.className = `beacon-share-btn ${net}`;
                btn.innerHTML = ICONS[net];
                btn.title = net.charAt(0).toUpperCase() + net.slice(1);
                btn.onclick = () => shareTo(net, shortLink.href, title);
                widget.appendChild(btn);
            }
        });

        el.appendChild(widget);

        // Auto-shorten
        shortenUrl(url).then(short => {
            if (short) shortLink.href = short;
            else shortLink.textContent = url;
        });
    }

    function createFloatingButton() {
        const btn = document.createElement('button');
        btn.style.cssText = 'position:fixed;bottom:20px;right:20px;width:50px;height:50px;border-radius:50%;background:#0078d4;color:#fff;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,120,212,.4);z-index:99998;display:flex;align-items:center;justify-content:center;transition:all .2s';
        btn.innerHTML = ICONS.link;
        btn.title = 'Поделиться';
        btn.onmouseenter = () => btn.style.transform = 'scale(1.1)';
        btn.onmouseleave = () => btn.style.transform = 'scale(1)';
        btn.onclick = () => showSharePopup(window.location.href, document.title);
        document.body.appendChild(btn);
    }

    function showSharePopup(url, title) {
        // Remove existing
        document.querySelector('.beacon-share-popup')?.remove();

        const popup = document.createElement('div');
        popup.className = `beacon-share-popup ${CONFIG.theme === 'dark' ? 'dark' : ''}`;

        popup.innerHTML = `
            <button class="beacon-close">${ICONS.close}</button>
            <h3>Поделиться</h3>
            <div class="beacon-short-url">
                <input type="text" value="Сокращение..." readonly id="beacon-popup-short">
                <button onclick="navigator.clipboard.writeText(document.getElementById('beacon-popup-short').value)">Копировать</button>
            </div>
            <div class="beacon-networks" id="beacon-popup-networks"></div>
        `;

        popup.querySelector('.beacon-close').onclick = () => popup.remove();
        document.body.appendChild(popup);

        // Add network buttons
        const netsDiv = popup.querySelector('#beacon-popup-networks');
        CONFIG.networks.forEach(net => {
            if (net === 'copy') return; // Already have copy button
            const btn = document.createElement('button');
            btn.className = `beacon-share-btn ${net}`;
            btn.innerHTML = ICONS[net];
            btn.onclick = () => shareTo(net, document.getElementById('beacon-popup-short').value, title);
            netsDiv.appendChild(btn);
        });

        // Shorten
        shortenUrl(url).then(short => {
            const input = popup.querySelector('#beacon-popup-short');
            input.value = short || url;
        });
    }

    // Public API
    window.BeaconShare = {
        init(opts = {}) {
            if (initialized) return;
            initialized = true;
            Object.assign(CONFIG, opts);
            injectStyles();

            // Find inline widgets
            document.querySelectorAll('.beacon-share').forEach(createInlineWidget);

            // Create floating button if no inline widgets
            if (!document.querySelector('.beacon-share') && CONFIG.position !== 'inline') {
                createFloatingButton();
            }
        },

        create(url, opts = {}) {
            return shortenUrl(url);
        },

        show(url, title) {
            showSharePopup(url || window.location.href, title || document.title);
        },
    };

    // Auto-init from script tag
    const script = document.currentScript;
    if (script) {
        const domain = script.dataset.domain;
        if (domain) CONFIG.domain = domain;
        CONFIG.apiBase = `https://${domain}/api`;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => window.BeaconShare.init());
    } else {
        window.BeaconShare.init();
    }
})();
