/**
 * Полноценный боевой JS-плагин Liftw для системы QuickJS.
 * Правки:
 *  - _decodeIfBase64: корректное удаление разделителей //_//
 *  - _decodePlayerValue: разбор [1080p]//_//b64,[720p]//_//b64
 *  - configRegex: JSON-ключи ("file":"..."), src/source/url
 *  - НОВОЕ: извлечение потока из download (URL-encoded master.m3u8)
 *  - Приоритет качества 1080p → 720p → любой m3u8 → mp4
 */
var plugin = globalThis.plugin = {
    meta: {
        name: "Lift",
        baseUrl: "https://api.liftw.ws",
        aliases: ["Lift", "Liftw", "Лифт", "Фильмы и сериалы", "Кино"],
        domains: ["liftw.ws", "api.liftw.ws", "embed.liftw.ws", "interkh.com", "showvid.ws"],
        icon: "movie",
        requiresAuth: false
    },

    USER_AGENT: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    DEBUG: true,

    SERIES_CATEGORIES: {
        "series": true,
        "cartoon_series": true,
        "anime_series": true,
        "tvshows": true
    },

    _log: function (msg) {
        if (!this.DEBUG) return;
        try {
            if (typeof bridge !== "undefined" && bridge.log) {
                bridge.log("[Lift] " + msg);
            }
        } catch (_) {}
    },

    checkAuth: function () { return true; },

    login: function (username, password) { return { success: true }; },

    getCatalogCategories: function () {
        return [
            { id: "films", title: "Фильмы", description: "Художественные фильмы" },
            { id: "series", title: "Сериалы", description: "Зарубежные и российские сериалы" },
            { id: "cartoons", title: "Мультфильмы", description: "Анимационные фильмы" },
            { id: "cartoon_series", title: "Мультсериалы", description: "Анимационные сериалы" },
            { id: "anime_films", title: "Аниме", description: "Полнометражное аниме" },
            { id: "anime_series", title: "Аниме-сериалы", description: "Многосерийное аниме" },
            { id: "tvshows", title: "ТВ-шоу", description: "Телевизионные шоу" },
            { id: "all", title: "Все", description: "Популярное из всех категорий" }
        ];
    },

    getCatalogItems: function (category, page) {
        try {
            var cat = category || "films";
            var p = page || 1;
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Origin": "https://liftw.ws",
                "Referer": "https://liftw.ws/",
                "Accept": "application/json, text/html, */*"
            };

            var catQuery = cat === "all"
                ? "series,cartoons,cartoon_series,tvshows,anime_films,anime_series,films"
                : cat;
            var url = this.meta.baseUrl + "/list/categories?category=" + encodeURIComponent(catQuery) + "&page=" + p + "&limit=20&sort=popular&last=true";

            var body = bridge.request("GET", url, JSON.stringify(headers), "");
            var trimmed = (body || "").trim();

            if (cat === "all" && (!trimmed || trimmed.charAt(0) !== '[' || trimmed === "[]")) {
                var fallbackUrl = this.meta.baseUrl + "/list/categories?category=films&page=" + p + "&limit=20&sort=popular&last=true";
                body = bridge.request("GET", fallbackUrl, JSON.stringify(headers), "");
                trimmed = (body || "").trim();
            }

            if (!trimmed || trimmed.charAt(0) !== '[') return [];

            var arr = JSON.parse(trimmed);
            var results = [];
            for (var i = 0; i < arr.length; i++) {
                if (arr[i]) results.push(this._parseApiItem(arr[i], cat === "all" ? null : cat));
            }
            return results;
        } catch (e) {
            this._log("getCatalogItems error: " + e);
            return [];
        }
    },

    search: function (query, limit) {
        try {
            var cleanQ = (query || "").trim();
            if (!cleanQ) return [];

            var maxLimit = limit || 30;
            var url = this.meta.baseUrl + "/search?q=" + encodeURIComponent(cleanQ);
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Origin": "https://liftw.ws",
                "Referer": "https://liftw.ws/",
                "Accept": "application/json, text/html, */*"
            };

            var results = [];
            var seenIds = {};

            var body = bridge.request("GET", url, JSON.stringify(headers), "");
            if (body && body.trim().charAt(0) === '{') {
                var root = JSON.parse(body.trim());
                var itemsArray = root.items || [];
                var count = Math.min(itemsArray.length, maxLimit);
                for (var i = 0; i < count; i++) {
                    if (itemsArray[i]) {
                        var parsed = this._parseApiItem(itemsArray[i], null);
                        if (!seenIds[parsed.id]) {
                            seenIds[parsed.id] = true;
                            results.push(parsed);
                        }
                    }
                }
            }

            if (results.length < maxLimit) {
                var catItems = this.getCatalogItems("all", 1);
                var qLower = cleanQ.toLowerCase();
                for (var j = 0; j < catItems.length; j++) {
                    var cItem = catItems[j];
                    if (cItem.title.toLowerCase().indexOf(qLower) !== -1 && !seenIds[cItem.id]) {
                        seenIds[cItem.id] = true;
                        results.push(cItem);
                        if (results.length >= maxLimit) break;
                    }
                }
            }

            return results;
        } catch (e) {
            this._log("search error: " + e);
            return [];
        }
    },

    getVideoInfo: function (url) {
        try {
            var mediaId = this._extractMediaId(url);
            if (!mediaId) return null;

            var infoUrl = this.meta.baseUrl + "/info/" + mediaId;
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Origin": "https://liftw.ws",
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.trim().charAt(0) !== '{') return null;

            var root = JSON.parse(body.trim());
            return this._parseApiItem(root, null);
        } catch (e) {
            this._log("getVideoInfo error: " + e);
            return null;
        }
    },

    getEpisodes: function (seriesUrl) {
        try {
            var mediaId = this._extractMediaId(seriesUrl);
            if (!mediaId) return null;

            var infoUrl = this.meta.baseUrl + "/info/" + mediaId;
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Origin": "https://liftw.ws",
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.trim().charAt(0) !== '{') return null;

            var root = JSON.parse(body.trim());
            var episodesObj = root.episodes || (root.info && root.info.episodes);
            if (!episodesObj) return null;

            var baseIframeUri = this._extractIframeFromObj(root);
            var currentMediaId = String(root.id || mediaId);

            var episodeTime = this._optStringSmart(root, ["time"]);
            var episodeDurationMs = this._parseDurationMs(episodeTime) || 0;

            var rawPoster = root.poster || (root.info && root.info.poster) || "";
            var poster = rawPoster ? rawPoster + "#vertical" : "";

            var description = this._optStringSmart(root, ["description"]);
            var genre = this._optStringArraySmart(root, "genre");
            var country = this._optStringArraySmart(root, "country");
            var age = this._optStringSmart(root, ["age"]);
            var mpaa = this._optStringSmart(root, ["rate_mpaa"]);
            var fullDescription = this._buildFullDescription(genre, country, age, episodeTime, mpaa, description);

            var seasonKeys = Object.keys(episodesObj)
                .map(function (k) { return parseInt(k, 10); })
                .filter(function (n) { return !isNaN(n); });
            seasonKeys.sort(function (a, b) { return a - b; });

            var episodesList = [];

            for (var si = 0; si < seasonKeys.length; si++) {
                var s = seasonKeys[si];
                var epRaw = episodesObj[String(s)];
                var numArr = [];

                if (Array.isArray(epRaw)) {
                    for (var ei = 0; ei < epRaw.length; ei++) {
                        var itemEp = epRaw[ei];
                        var n = (typeof itemEp === "object" && itemEp !== null)
                            ? parseInt(itemEp.episode || itemEp.num || (ei + 1), 10)
                            : parseInt(itemEp, 10);
                        if (!isNaN(n)) numArr.push(n);
                    }
                } else if (typeof epRaw === "object" && epRaw !== null) {
                    var ek = Object.keys(epRaw);
                    for (var eki = 0; eki < ek.length; eki++) {
                        var n2 = parseInt(ek[eki], 10);
                        if (!isNaN(n2)) numArr.push(n2);
                    }
                }

                numArr.sort(function (a, b) { return a - b; });

                for (var k = 0; k < numArr.length; k++) {
                    var e = numArr[k];
                    var episodeIframeUrl;
                    if (baseIframeUri.length > 0) {
                        var sep = baseIframeUri.indexOf("?") !== -1 ? "&" : "?";
                        episodeIframeUrl = baseIframeUri + sep + "id=" + currentMediaId + "&season=" + s + "&episode=" + e;
                    } else {
                        episodeIframeUrl = this.meta.baseUrl + "/info/" + currentMediaId + "?season=" + s + "&episode=" + e;
                    }

                    episodesList.push({
                        id: currentMediaId + "_s" + s + "_e" + e,
                        title: "Сезон " + s + ", серия " + e,
                        author: episodeTime || ("Сезон " + s),
                        thumbnail: poster,
                        url: episodeIframeUrl,
                        duration: episodeDurationMs,
                        views: "S" + s + "E" + e,
                        source: this.meta.name,
                        isSeries: false,
                        season: s,
                        episode: e,
                        contentType: "EPISODE",
                        description: fullDescription
                    });
                }
            }

            return episodesList.length > 0 ? episodesList : null;
        } catch (e) {
            this._log("getEpisodes error: " + e);
            return null;
        }
    },

    resolveStream: function (url, audioOnly) {
        try {
            this._log("resolveStream IN: " + url);

            var embedCandidates = this._resolveEmbedCandidates(url);
            this._log("embed candidates: " + JSON.stringify(embedCandidates));
            if (!embedCandidates || embedCandidates.length === 0) return null;

            var referers = [
                "https://liftw.ws/",
                "https://lift.com/",
                "https://embed.liftw.ws/"
            ];

            var foundStream = null;
            var usedHtml = "";
            var usedEmbedUrl = embedCandidates[0];

            for (var c = 0; c < embedCandidates.length; c++) {
                var cleanEmbedUrl = this._normalizeIframe(embedCandidates[c]);
                if (!cleanEmbedUrl) continue;

                for (var r = 0; r < referers.length; r++) {
                    var embedHeaders = {
                        "User-Agent": this.USER_AGENT,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Origin": "https://liftw.ws",
                        "Referer": referers[r]
                    };
                    var embedHtml = bridge.request("GET", cleanEmbedUrl, JSON.stringify(embedHeaders), "");
                    if (!embedHtml || embedHtml.length < 20) {
                        this._log("embed " + cleanEmbedUrl + " ref=" + referers[r] + " -> len=" + (embedHtml ? embedHtml.length : 0));
                        continue;
                    }

                    var candidate = this._extractStreamFromHtml(embedHtml, cleanEmbedUrl);
                    if (candidate) {
                        foundStream = candidate;
                        usedHtml = embedHtml;
                        usedEmbedUrl = cleanEmbedUrl;
                        this._log("FOUND stream: " + candidate);
                        break;
                    }
                    if (!usedHtml) usedHtml = embedHtml;
                }
                if (foundStream) break;
            }

            if (!foundStream) {
                this._log("no stream found, last html head: " + (usedHtml || "").substring(0, 500));
                return null;
            }

            var stream = foundStream;
            if (stream.indexOf("//") === 0) stream = "https:" + stream;
            stream = stream.replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();

            var tokenMatch = usedHtml.match(/var\s+lok\s*=\s*1\s*,\s*[a-zA-Z0-9_]+\s*=\s*["']([^"']+)["']/);
            if (tokenMatch && tokenMatch[1] && stream.indexOf(tokenMatch[1]) === -1) {
                var sep = stream.indexOf("?") !== -1 ? "&" : "?";
                stream = stream + sep + tokenMatch[1];
            }

            var originHost = "https://liftw.ws";
            var hostMatch = usedEmbedUrl.match(/^(https?:\/\/[^/]+)/);
            if (hostMatch) originHost = hostMatch[1];

            // Для interkh.com плеер обычно требует Referer именно embed-страницы
            var streamHost = "";
            var streamHostMatch = stream.match(/^https?:\/\/([^/]+)/);
            if (streamHostMatch) streamHost = streamHostMatch[1];

            var playerHeaders = {
                "User-Agent": this.USER_AGENT,
                "Origin": originHost,
                "Referer": originHost + "/"
            };

            if (stream.indexOf("interkh.com") !== -1) {
                playerHeaders["Referer"] = usedEmbedUrl;
                playerHeaders["Origin"] = originHost;
            }

            return {
                streamUrl: stream,
                mimeType: stream.indexOf(".mp4") !== -1 && stream.indexOf(".m3u8") === -1 ? "video/mp4" : "application/x-mpegURL",
                width: 1920,
                height: 1080,
                headers: playerHeaders
            };
        } catch (e) {
            this._log("resolveStream error: " + e);
            return null;
        }
    },

    // ====================== ВНУТРЕННИЕ ПАРСЕРЫ И УТИЛИТЫ ======================

    _extractIframeFromObj: function (obj) {
        if (!obj || typeof obj !== "object") return "";
        var keys = ["iframe_uri", "iframe_url", "iframe", "embed_url", "embed", "player", "player_url"];
        for (var i = 0; i < keys.length; i++) {
            var val = obj[keys[i]];
            if (typeof val === "string" && val.trim().length > 0 && val.indexOf("/info/") === -1) {
                return this._normalizeIframe(val);
            }
        }
        if (obj.info && typeof obj.info === "object") {
            for (var j = 0; j < keys.length; j++) {
                var val2 = obj.info[keys[j]];
                if (typeof val2 === "string" && val2.trim().length > 0 && val2.indexOf("/info/") === -1) {
                    return this._normalizeIframe(val2);
                }
            }
        }
        var rawJson = JSON.stringify(obj);
        var m = rawJson.match(/["']((?:https?:)?\/\/[^"']*(?:embed|interkh|play|iframe)[^"']*)["']/i);
        if (m && m[1]) return this._normalizeIframe(m[1]);
        return "";
    },

    _resolveEmbedCandidates: function (url) {
        var sMatch = url.match(/[?&]season=(\d+)/);
        var eMatch = url.match(/[?&]episode=(\d+)/);
        var sParam = sMatch ? sMatch[1] : null;
        var eParam = eMatch ? eMatch[1] : null;

        var candidates = [];

        function appendParams(target) {
            if (!target) return "";
            if (sParam && eParam && target.indexOf("season=") === -1) {
                var sep = target.indexOf("?") !== -1 ? "&" : "?";
                return target + sep + "season=" + sParam + "&episode=" + eParam;
            }
            return target;
        }

        if (url.indexOf("/info/") === -1 && !/^\d+$/.test(url)) {
            candidates.push(appendParams(url));
        }

        var mediaId = this._extractMediaId(url);
        if (mediaId) {
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Origin": "https://liftw.ws",
                "Referer": "https://liftw.ws/",
                "Accept": "application/json, text/plain, */*"
            };
            var infoBody = bridge.request("GET", this.meta.baseUrl + "/info/" + mediaId, JSON.stringify(headers), "");
            if (infoBody && infoBody.trim().charAt(0) === '{') {
                try {
                    var json = JSON.parse(infoBody.trim());
                    var extracted = this._extractIframeFromObj(json);
                    if (extracted) {
                        var withParams = appendParams(extracted);
                        if (candidates.indexOf(withParams) === -1) candidates.unshift(withParams);
                    }
                } catch (_) {}
            }
            candidates.push(appendParams("https://embed.liftw.ws/embed/" + mediaId));
            candidates.push(appendParams("https://liftw.ws/embed/" + mediaId));
        }

        var unique = [];
        for (var i = 0; i < candidates.length; i++) {
            var c = candidates[i];
            if (c && unique.indexOf(c) === -1) unique.push(c);
        }
        return unique;
    },

    /**
     * Разбор значения PlayerJS-поля.
     * Поддерживает:
     *   "[1080p]//_//b64,[720p]//_//b64"
     *   "#2b64"
     *   "//_//b64"
     *   "https://...m3u8"
     *   URL-encoded "%3A%2F%2F...master.m3u8..."
     */
    _decodePlayerValue: function (raw) {
        if (!raw) return null;
        var out = String(raw).trim();
        if (!out) return null;

        // Сначала раскодируем URL-encoding (может прийти download=...)
        var decoded = out;
        try {
            if (out.indexOf("%3A") !== -1 || out.indexOf("%2F") !== -1) {
                decoded = decodeURIComponent(out.replace(/\\u0026/g, "&"));
            }
        } catch (_) {}

        var direct = this._decodeIfBase64(decoded);
        var directUrl = this._pickBestStreamUrl(direct);
        if (directUrl && (directUrl.indexOf(".m3u8") !== -1 || directUrl.indexOf(".mp4") !== -1)) {
            return directUrl;
        }

        var parts = decoded.split(",");
        if (parts.length > 1) {
            var urls = [];
            for (var i = 0; i < parts.length; i++) {
                var p = parts[i].trim();
                p = p.replace(/^\[\s*[^\]]+\s*\]\s*/, "");
                p = this._decodeIfBase64(p);
                var u = this._pickBestStreamUrl(p);
                if (u) urls.push(u);
            }
            if (urls.length > 0) {
                for (var k = 0; k < urls.length; k++) if (urls[k].indexOf("1080") !== -1) return urls[k];
                for (var k2 = 0; k2 < urls.length; k2++) if (urls[k2].indexOf("720") !== -1) return urls[k2];
                return urls[urls.length - 1];
            }
        }

        return directUrl;
    },

    _extractStreamFromHtml: function (embedHtml, cleanEmbedUrl) {
        var html = String(embedHtml || "");
        var self = this;
        var match;

        // 0. download: "https://dl.showvid.ws/x-px?m=ENCODED_master.m3u8..."
        var dlMatch = html.match(/["']?download["']?\s*:\s*["']([^"']+)["']/i);
        if (dlMatch) {
            var dlVal = dlMatch[1];
            try {
                dlVal = decodeURIComponent(dlVal.replace(/\\u0026/g, "&"));
            } catch (_) {}
            var m3u8InDl = dlVal.match(/(https?:\/\/[^\s"']+\.m3u8[^\s"']*)/i);
            if (m3u8InDl) {
                this._log("FOUND in download: " + m3u8InDl[1]);
                return m3u8InDl[1];
            }
            // Иногда master.m3u8 зашит в ?m=
            var mParam = dlVal.match(/[?&]m=([^&"'\s]+)/i);
            if (mParam) {
                var innerM3u8;
                try { innerM3u8 = decodeURIComponent(mParam[1]); } catch (_) { innerM3u8 = mParam[1]; }
                var innerMatch = innerM3u8.match(/(https?:\/\/[^\s"']+\.m3u8[^\s"']*)/i);
                if (innerMatch) {
                    this._log("FOUND in download?m=: " + innerMatch[1]);
                    return innerMatch[1];
                }
            }
        }

        // 1. URL-encoded master.m3u8 в любом месте HTML
        var encMatches = html.match(/https?%3A%2F%2F[^"'\s)]+master\.m3u8[^"'\s)]*/gi);
        if (encMatches && encMatches.length > 0) {
            for (var em = 0; em < encMatches.length; em++) {
                try {
                    var dec = decodeURIComponent(encMatches[em]);
                    var realM = dec.match(/(https?:\/\/[^\s"']+\.m3u8[^\s"']*)/i);
                    if (realM) {
                        this._log("FOUND encoded master.m3u8: " + realM[1]);
                        return realM[1];
                    }
                } catch (_) {}
            }
        }

        // 2. JSON-encoded URL (часто "https:\/\/...m3u8")
        var slashEsc = html.match(/"https?:\\\/\\\/[^"]+\.m3u8[^"]*"/i);
        if (slashEsc) {
            var cleanS = slashEsc[0].slice(1, -1).replace(/\\\//g, "/");
            this._log("FOUND slash-escaped m3u8: " + cleanS);
            return cleanS;
        }

        // 3. Поля плеера: file/hls/playlist/dash/stream/src/source/url
        var configRegex = /["']?(?:hls|file|playlist|dash|stream|src|source|url)["']?\s*[:=]\s*["']([^"']{8,})["']/gi;
        while ((match = configRegex.exec(html)) !== null) {
            var rawVal = match[1].trim();
            if (rawVal.indexOf(".js") !== -1 || rawVal.indexOf(".css") !== -1 ||
                rawVal.indexOf(".svg") !== -1 || rawVal.indexOf(".png") !== -1 ||
                rawVal.indexOf(".jpg") !== -1 || rawVal.indexOf(".jpeg") !== -1) {
                continue;
            }

            var bestUrl = self._decodePlayerValue(rawVal);
            if (!bestUrl) continue;

            if (bestUrl.indexOf(".m3u8") !== -1 || bestUrl.indexOf(".mp4") !== -1 ||
                bestUrl.indexOf("interkh") !== -1) {
                return bestUrl;
            }

            if (bestUrl.indexOf("http") === 0) {
                var plHeaders = { "User-Agent": self.USER_AGENT, "Referer": cleanEmbedUrl };
                var plTextRaw = bridge.request("GET", bestUrl, JSON.stringify(plHeaders), "") || "";
                if (plTextRaw.indexOf("#EXTM3U") === 0) return bestUrl;

                var plDecoded = self._decodeIfBase64(plTextRaw);
                var subBest = self._pickBestStreamUrl(plDecoded);
                if (subBest) return subBest;
            }
        }

        // 4. Зашифрованные строки PlayerJS (#2 / //_//)
        var b64Regex = /["']((?:#2|\/\/_\/\/)[A-Za-z0-9+/=_\/-]{20,})["']/g;
        while ((match = b64Regex.exec(html)) !== null) {
            var decB64 = self._decodeIfBase64(match[1]);
            var bUrl = self._pickBestStreamUrl(decB64);
            if (bUrl && (bUrl.indexOf(".m3u8") !== -1 || bUrl.indexOf(".mp4") !== -1)) {
                return bUrl;
            }
        }

        // 5. Прямой поиск m3u8 / mp4 в HTML
        var directBest = self._pickBestStreamUrl(html);
        if (directBest && (directBest.indexOf(".m3u8") !== -1 || directBest.indexOf(".mp4") !== -1)) {
            return directBest;
        }

        // 6. Вложенный iframe-балансер
        return this._resolveViaBalancer(html, cleanEmbedUrl);
    },

    _pickBestStreamUrl: function (text) {
        if (!text) return null;
        var clean = String(text).replace(/\\\//g, "/").replace(/\\u0026/g, "&");

        var m3u8All = [];
        var m3u8Re = /(https?:\/\/[^,"'\s<>|\[\]{}]+\.m3u8[^,"'\s<>|\[\]{}]*)/gi;
        var m;
        while ((m = m3u8Re.exec(clean)) !== null) m3u8All.push(m[1]);
        if (m3u8All.length > 0) {
            for (var i = 0; i < m3u8All.length; i++) if (m3u8All[i].indexOf("1080") !== -1) return m3u8All[i];
            for (var j = 0; j < m3u8All.length; j++) if (m3u8All[j].indexOf("720") !== -1) return m3u8All[j];
            return m3u8All[m3u8All.length - 1];
        }

        var mp4All = [];
        var mp4Re = /(https?:\/\/[^,"'\s<>|\[\]{}]+\.mp4[^,"'\s<>|\[\]{}]*)/gi;
        while ((m = mp4Re.exec(clean)) !== null) mp4All.push(m[1]);
        if (mp4All.length > 0) return mp4All[mp4All.length - 1];

        var genericMatch = clean.match(/(https?:\/\/[^,"'|\[\]\s<>]+)/);
        return genericMatch ? genericMatch[1] : null;
    },

    _resolveViaBalancer: function (embedHtml, refererUrl) {
        var iframeMatch = embedHtml.match(/<iframe[^>]+src=["']([^"']+)["']/i);
        if (!iframeMatch) return null;

        var iframeUrl = this._normalizeIframe(iframeMatch[1]);
        var sMatch = refererUrl.match(/[?&]season=(\d+)/);
        var eMatch = refererUrl.match(/[?&]episode=(\d+)/);
        var sParam = sMatch ? parseInt(sMatch[1], 10) : null;
        var eParam = eMatch ? parseInt(eMatch[1], 10) : null;

        if (sParam && eParam && iframeUrl.indexOf("season=") === -1) {
            var sep = iframeUrl.indexOf("?") !== -1 ? "&" : "?";
            iframeUrl = iframeUrl + sep + "season=" + sParam + "&episode=" + eParam;
        }

        this._log("balancer iframe: " + iframeUrl);

        var bHeaders = { "User-Agent": this.USER_AGENT, "Referer": refererUrl };
        var balancerHtml = bridge.request("GET", iframeUrl, JSON.stringify(bHeaders), "") || "";
        if (!balancerHtml) return null;

        if (sParam && eParam) {
            var seasonsMatch = balancerHtml.match(/seasons\s*:\s*(\[\{[\s\S]*?\}\])\s*[,;]/);
            if (seasonsMatch) {
                try {
                    var sArr = JSON.parse(seasonsMatch[1]);
                    for (var si = 0; si < sArr.length; si++) {
                        var sObj = sArr[si];
                        if (Number(sObj.season || (si + 1)) !== sParam) continue;
                        var eps = sObj.episodes || [];
                        for (var ei = 0; ei < eps.length; ei++) {
                            var eObj = eps[ei];
                            if (Number(eObj.episode || (ei + 1)) !== eParam) continue;
                            var rawHls = String(eObj.hls || eObj.file || eObj.url || "");
                            var decHls = this._decodeIfBase64(rawHls);
                            var best = this._pickBestStreamUrl(decHls) || decHls.replace(/\\\//g, "/").trim();
                            if (best && best.indexOf("http") === 0) return best;
                        }
                    }
                } catch (_) {}
            }
        }

        var configRegex = /["']?(?:hls|file|playlist|dash|stream|src|source|url)["']?\s*[:=]\s*["']([^"']{8,})["']/gi;
        var m;
        while ((m = configRegex.exec(balancerHtml)) !== null) {
            var val = m[1].trim();
            if (val.indexOf(".js") !== -1 || val.indexOf(".css") !== -1) continue;
            var bestUrl = this._decodePlayerValue(val);
            if (bestUrl && (bestUrl.indexOf(".m3u8") !== -1 || bestUrl.indexOf(".mp4") !== -1)) return bestUrl;
        }

        var bStream = this._pickBestStreamUrl(balancerHtml);
        if (bStream && (bStream.indexOf(".m3u8") !== -1 || bStream.indexOf(".mp4") !== -1)) {
            return bStream;
        }

        var nestedIframe = balancerHtml.match(/<iframe[^>]+src=["']([^"']+)["']/i);
        if (nestedIframe) {
            var nestedUrl = this._normalizeIframe(nestedIframe[1]);
            if (nestedUrl !== iframeUrl) {
                var nHeaders = { "User-Agent": this.USER_AGENT, "Referer": iframeUrl };
                var nHtml = bridge.request("GET", nestedUrl, JSON.stringify(nHeaders), "") || "";
                if (nHtml) {
                    var nRegex = /["']?(?:hls|file|playlist|dash|stream|src|source|url)["']?\s*[:=]\s*["']([^"']{8,})["']/gi;
                    while ((m = nRegex.exec(nHtml)) !== null) {
                        var v2 = m[1].trim();
                        if (v2.indexOf(".js") !== -1 || v2.indexOf(".css") !== -1) continue;
                        var u2 = this._decodePlayerValue(v2);
                        if (u2 && (u2.indexOf(".m3u8") !== -1 || u2.indexOf(".mp4") !== -1)) return u2;
                    }
                }
            }
        }

        return null;
    },

    _parseApiItem: function (item, forcedCategory) {
        var info = item.info || {};
        var id = String(item.id || info.id || "");
        var type = item.type || info.type || 1;
        var serialStatus = String(item.serial_status || info.serial_status || "").trim();
        var hasEpisodesObj = !!(item.episodes || info.episodes);

        var isSeries = (type === 3 || type === 4 || type === 5) ||
            hasEpisodesObj ||
            serialStatus.length > 0 ||
            (forcedCategory != null && !!this.SERIES_CATEGORIES[forcedCategory]);

        var yearNum = parseInt(item.year || info.year || 0, 10);
        var year = (!isNaN(yearNum) && yearNum > 0) ? yearNum : null;

        var quality = String(item.quality || info.quality || "").trim();
        var kpRating = parseFloat(item.kp_rating || info.kp_rating || 0);
        var imdbRating = parseFloat(item.imdb_rating || info.imdb_rating || 0);
        var rating = (!isNaN(kpRating) && kpRating > 0) ? kpRating : ((!isNaN(imdbRating) && imdbRating > 0) ? imdbRating : null);

        var badges = [];
        if (serialStatus.length > 0) badges.push(serialStatus);
        else if (isSeries) badges.push("Сериал");
        if (quality.length > 0) badges.push(quality);
        if (rating !== null) {
            if (!isNaN(kpRating) && kpRating > 0) badges.push("КП " + kpRating.toFixed(1));
            else badges.push("IMDb " + imdbRating.toFixed(1));
        }
        if (year !== null) badges.push(String(year));

        var iframeUri = this._extractIframeFromObj(item);
        var targetUrl;
        if (iframeUri.length > 0) {
            if (id && !this._extractMediaId(iframeUri)) {
                var sep = iframeUri.indexOf("?") !== -1 ? "&" : "?";
                targetUrl = iframeUri + sep + "id=" + id;
            } else {
                targetUrl = iframeUri;
            }
        } else {
            targetUrl = this.meta.baseUrl + "/info/" + id;
        }

        var rawPoster = String(item.poster || info.poster || "").trim();
        var poster = rawPoster.length > 0 ? (rawPoster + "#vertical") : "";

        var description = this._optStringSmart(item, ["description"]);
        var genre = this._optStringArraySmart(item, "genre");
        var country = this._optStringArraySmart(item, "country");
        var age = this._optStringSmart(item, ["age"]);
        var time = this._optStringSmart(item, ["time"]);
        var mpaa = this._optStringSmart(item, ["rate_mpaa"]);

        var fullDescription = this._buildFullDescription(genre, country, age, time, mpaa, description);

        var originName = String(item.origin_name || info.origin_name || info.name_eng || "").trim();
        var durationMs = isSeries ? 1 : (this._parseDurationMs(time) || 7200000);
        var title = String(info.name || item.name || "Без названия").trim() || "Без названия";

        return {
            id: id,
            title: title,
            author: originName || (year ? String(year) : this.meta.name),
            thumbnail: poster,
            url: targetUrl,
            duration: durationMs,
            views: badges.join(" • ") || "HD",
            source: this.meta.name,
            isSeries: isSeries,
            contentType: isSeries ? "SERIES" : "FILM",
            description: fullDescription
        };
    },

    _normalizeIframe: function (raw) {
        var s = String(raw || "").replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
        if (s.indexOf("//") === 0) s = "https:" + s;
        if (s.indexOf("/") === 0) s = "https://liftw.ws" + s;
        return s;
    },

    /**
     * PlayerJS: "#2<b64>" или "//_//<b64>".
     * Внутри base64 могут встречаться разделители "//_//" — вырезаем их по всей строке.
     */
    _decodeIfBase64: function (s) {
        var trimmed = String(s || "").trim();
        if (!trimmed) return trimmed;

        var b64 = null;
        if (trimmed.indexOf("#2") === 0) b64 = trimmed.substring(2);
        else if (trimmed.indexOf("//_//") === 0) b64 = trimmed.substring(5);
        if (b64 === null) return trimmed;

        b64 = b64.split("//_//").join("");

        try {
            var decoded = bridge.decodeBase64(b64);
            if (decoded && decoded.length > 0) return decoded;
        } catch (_) {}

        return trimmed;
    },

    _optStringSmart: function (obj, keys) {
        if (!obj) return "";
        for (var i = 0; i < keys.length; i++) {
            var k = keys[i];
            if (obj[k] !== undefined && obj[k] !== null) {
                var v = String(obj[k]).trim();
                if (v.length > 0 && v !== "null") return v;
            }
        }
        var info = obj.info;
        if (info && typeof info === "object") {
            for (var j = 0; j < keys.length; j++) {
                var ik = keys[j];
                if (info[ik] !== undefined && info[ik] !== null) {
                    var iv = String(info[ik]).trim();
                    if (iv.length > 0 && iv !== "null") return iv;
                }
            }
        }
        return "";
    },

    _optStringArraySmart: function (obj, key) {
        function readArr(target) {
            if (!target || !Array.isArray(target[key])) return [];
            var out = [];
            for (var i = 0; i < target[key].length; i++) {
                var s = String(target[key][i] || "").trim();
                if (s.length > 0) out.push(s);
            }
            return out;
        }
        var top = readArr(obj);
        if (top.length > 0) return top;
        return readArr(obj ? obj.info : null);
    },

    _buildFullDescription: function (genre, country, age, time, mpaa, description) {
        var lines = [];

        var head = [];
        if (genre && genre.length > 0) {
            var gStr = genre.join(", ");
            head.push(gStr.charAt(0).toUpperCase() + gStr.slice(1));
        }
        if (country && country.length > 0) head.push(country.join(", "));
        if (head.length > 0) lines.push(head.join(" • "));

        var sub = [];
        if (age) sub.push(age.slice(-1) === "+" ? age : (age + "+"));
        if (time) sub.push(time);
        if (mpaa) sub.push(mpaa);
        if (sub.length > 0) lines.push(sub.join(" • "));

        var metaBlock = lines.join("\n");
        var cleanDesc = (description || "").trim();

        if (metaBlock && cleanDesc) return metaBlock + "\n\n" + cleanDesc;
        return metaBlock || cleanDesc;
    },

    _parseDurationMs: function (timeStr) {
        if (!timeStr) return null;
        var hMatch = timeStr.match(/(\d+)\s*ч/);
        var mMatch = timeStr.match(/(\d+)\s*мин/);
        var hours = hMatch ? parseInt(hMatch[1], 10) : 0;
        var minutes = mMatch ? parseInt(mMatch[1], 10) : 0;
        if (hours > 0 || minutes > 0) return (hours * 3600 + minutes * 60) * 1000;

        var parts = timeStr.split(":");
        if (parts.length === 2) {
            var m = parseInt(parts[0].trim(), 10);
            var s = parseInt(parts[1].trim(), 10);
            if (!isNaN(m) && !isNaN(s)) return (m * 60 + s) * 1000;
        } else if (parts.length === 3) {
            var h = parseInt(parts[0].trim(), 10);
            var m2 = parseInt(parts[1].trim(), 10);
            var s2 = parseInt(parts[2].trim(), 10);
            if (!isNaN(h) && !isNaN(m2) && !isNaN(s2)) return (h * 3600 + m2 * 60 + s2) * 1000;
        }
        return null;
    },

    _extractMediaId: function (url) {
        if (!url) return null;
        var str = String(url).trim();
        if (/^\d+$/.test(str)) return str;
        var m = str.match(/plugin_\w+_(\d+)(?:_s\d+_e\d+)?/);
        if (m) return m[1];
        m = str.match(/^(\d+)_s\d+_e\d+/);
        if (m) return m[1];
        m = str.match(/[?&]id=(\d+)/);
        if (m) return m[1];
        m = str.match(/\/(?:info|movie|embed|play|e|video|serial)\/(\d+)/);
        if (m) return m[1];
        m = str.match(/\/(\d+)(?:[/?#]|$)/);
        if (m) return m[1];
        return null;
    }
};