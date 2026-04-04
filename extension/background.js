// Background service worker for keyboard shortcut
chrome.commands.onCommand.addListener(async (command) => {
    if (command === 'shorten-current') {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab?.url) return;

        const { apiUrl, apiToken } = await chrome.storage.sync.get(['apiUrl', 'apiToken']);
        const base = (apiUrl || 'https://qntx.ru').replace(/\/$/, '') + '/api';

        try {
            const headers = { 'Content-Type': 'application/json' };
            if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

            const resp = await fetch(base + '/links', {
                method: 'POST',
                headers,
                body: JSON.stringify({ url: tab.url }),
            });

            const data = await resp.json();
            if (resp.ok && data.slug) {
                const shortUrl = `${apiUrl || 'https://qntx.ru'}/s/${data.slug}`;
                await navigator.clipboard.writeText(shortUrl);

                // Show notification
                chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icon48.png',
                    title: 'QNTX.Beacon',
                    message: `Ссылка скопирована: ${shortUrl}`,
                });
            }
        } catch (e) {
            console.error('Shorten error:', e);
        }
    }
});
