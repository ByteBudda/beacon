/**
 * JS-порт рабочего Kotlin-плагина LiftwPlugin.
 * Логика извлечения потока 1:1 повторяет проверенный Kotlin-код.
 */
var plugin = globalThis.plugin = {
    meta: {
        name: "Liftw",
        baseUrl: "https://api.liftw.ws",
        aliases: ["Lift", "Лифт", "Фильмы и сериалы", "Кино"],
        domains: ["liftw.ws", "api.liftw.ws", "embed.liftw.ws", "interkh.com"],
        icon: "movie",
        requiresAuth: false
    },

    USER_AGENT: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
            if (typeof bridge !== "undefined" && bridge.log) bridge.log("[Liftw] " + msg);
        } catch (_) {}
    },

    _unescapeJs: function (s) {
        return String(s || "").replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
    },

    checkAuth: function () { return true; },
    login: function (u, p) { return { success: true }; },

    isSupported: function (url) {
        if (!url) return false;
        return url.indexOf("liftw.ws") !== -1 ||
               url.indexOf("api.liftw.ws") !== -1 ||
               url.indexOf("embed.liftw.ws") !== -1 ||
               url.indexOf("interkh.com") !== -1;
    },

    // ============================== КАТАЛОГ ==============================

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
            var catQuery = cat === "all"
                ? "series,cartoons,cartoon_series,tvshows,anime_films,anime_series,films"
                : cat;

            var url = this.meta.baseUrl + "/list/categories?category=" + encodeURIComponent(catQuery) + "&page=" + p + "&limit=20&sort=popular&last=true";
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Accept": "application/json, text/html, */*"
            };

            var body = bridge.request("GET", url, JSON.stringify(headers), "");
            var trimmed = (body || "").replace(/^\s+/, "");
            if (trimmed.charAt(0) !== '[') return [];

            var arr = JSON.parse(trimmed);
            var results = [];
            for (var i = 0; i < arr.length; i++) {
                var item = arr[i];
                var id = String(item.id || "");
                var type = parseInt(item.type || 1, 10);
                var serialStatus = String(item.serial_status || "").trim();
                var isSeries = (type === 3 || type === 4 || type === 5) ||
                    serialStatus.length > 0 ||
                    !!this.SERIES_CATEGORIES[cat];

                var year = parseInt(item.year || 0, 10);
                var yearStr = year > 0 ? String(year) : "";
                var quality = String(item.quality || "").trim();
                var kpRating = parseFloat(item.kp_rating || 0);
                var imdbRating = parseFloat(item.imdb_rating || 0);

                var badges = [];
                if (serialStatus.length > 0) badges.push(serialStatus);
                else if (isSeries) badges.push("Сериал");
                if (quality.length > 0) badges.push(quality);
                if (!isNaN(kpRating) && kpRating > 0) badges.push("КП " + kpRating.toFixed(1));
                else if (!isNaN(imdbRating) && imdbRating > 0) badges.push("IMDb " + imdbRating.toFixed(1));
                if (yearStr) badges.push(yearStr);

                var rawIframeUri = this._unescapeJs(
                    item.iframe_uri || item.iframe || item.embed || ""
                );
                if (rawIframeUri.indexOf("//") === 0) rawIframeUri = "https:" + rawIframeUri;
                if (rawIframeUri.charAt(0) === "/") rawIframeUri = "https://liftw.ws" + rawIframeUri;

                var targetUrl = rawIframeUri.length > 0 ? rawIframeUri : (this.meta.baseUrl + "/info/" + id);
                var rawPoster = String(item.poster || "");
                var finalPoster = rawPoster.length > 0 ? rawPoster + "#vertical" : "";

                results.push({
                    id: id,
                    title: String(item.name || "Без названия"),
                    author: String(item.origin_name || yearStr || "Liftw"),
                    thumbnail: finalPoster,
                    url: targetUrl,
                    duration: isSeries ? 1 : 7200000,
                    views: badges.length > 0 ? badges.join(" • ") : "HD",
                    source: this.meta.name,
                    isSeries: isSeries,
                    contentType: isSeries ? "SERIES" : "FILM"
                });
            }
            return results;
        } catch (e) {
            this._log("getCatalogItems error: " + e);
            return [];
        }
    },

    // ============================== ПОИСК ==============================

    search: function (query, limit) {
        try {
            var q = (query || "").trim();
            if (!q) return [];

            var url = this.meta.baseUrl + "/search?q=" + encodeURIComponent(q);
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Accept": "application/json"
            };

            var body = bridge.request("GET", url, JSON.stringify(headers), "");
            if (!body || body.replace(/^\s+/, "").charAt(0) !== '{') return [];

            var root = JSON.parse(body);
            var itemsArray = root.items || [];
            var max = Math.min(itemsArray.length, limit || 30);
            var results = [];

            for (var i = 0; i < max; i++) {
                var item = itemsArray[i];
                var id = String(item.id || "");
                var type = parseInt(item.type || 1, 10);
                var serialStatus = String(item.serial_status || "").trim();
                var hasEpisodes = !!item.episodes;
                var isSeries = (type === 3 || type === 4 || type === 5) || hasEpisodes || serialStatus.length > 0;

                var year = parseInt(item.year || 0, 10);
                var yearStr = year > 0 ? String(year) : "";
                var quality = String(item.quality || "").trim();
                var kpRating = parseFloat(item.kp_rating || 0);
                var imdbRating = parseFloat(item.imdb_rating || 0);

                var badges = [];
                if (serialStatus.length > 0) badges.push(serialStatus);
                else if (isSeries) badges.push("Сериал");
                if (quality.length > 0) badges.push(quality);
                if (!isNaN(kpRating) && kpRating > 0) badges.push("КП " + kpRating.toFixed(1));
                else if (!isNaN(imdbRating) && imdbRating > 0) badges.push("IMDb " + imdbRating.toFixed(1));
                if (yearStr) badges.push(yearStr);

                var rawIframeUri = this._unescapeJs(
                    item.iframe_uri || item.iframe || item.embed || ""
                );
                if (rawIframeUri.indexOf("//") === 0) rawIframeUri = "https:" + rawIframeUri;
                if (rawIframeUri.charAt(0) === "/") rawIframeUri = "https://liftw.ws" + rawIframeUri;

                var targetUrl = rawIframeUri.length > 0 ? rawIframeUri : (this.meta.baseUrl + "/info/" + id);
                var rawPoster = String(item.poster || "");
                var finalPoster = rawPoster.length > 0 ? rawPoster + "#vertical" : "";

                results.push({
                    id: id,
                    title: String(item.name || "Без названия"),
                    author: String(item.origin_name || yearStr || "Liftw"),
                    thumbnail: finalPoster,
                    url: targetUrl,
                    duration: isSeries ? 1 : 7200000,
                    views: badges.length > 0 ? badges.join(" • ") : "HD",
                    source: this.meta.name,
                    isSeries: isSeries,
                    contentType: isSeries ? "SERIES" : "FILM"
                });
            }
            return results;
        } catch (e) {
            this._log("search error: " + e);
            return [];
        }
    },

    // ============================== ИНФО ==============================

    getVideoInfo: function (url) {
        try {
            var mediaId = this._extractMediaId(url);
            var infoUrl = mediaId ? (this.meta.baseUrl + "/info/" + mediaId) : url;

            var headers = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.replace(/^\s+/, "").charAt(0) !== '{') return null;

            var root = JSON.parse(body);
            var info = root.info || {};

            var id = String(root.id || (mediaId || "0"));
            var title = String(info.name || root.name || "Без названия");
            var desc = String(info.description || "");

            var rawPoster = String(root.poster || "");
            var finalPoster = rawPoster.length > 0 ? rawPoster + "#vertical" : "";

            var timeStr = String(info.time || "");
            var durationMs = 7200000;
            var minMatch = timeStr.match(/(\d+)\s*мин/);
            if (minMatch) durationMs = (parseInt(minMatch[1], 10) || 120) * 60 * 1000;

            var iframeUri = this._unescapeJs(root.iframe_uri || root.iframe || root.embed || "");
            if (iframeUri.indexOf("//") === 0) iframeUri = "https:" + iframeUri;
            if (iframeUri.charAt(0) === "/") iframeUri = "https://liftw.ws" + iframeUri;

            return {
                id: id,
                title: title,
                author: "Liftw",
                thumbnail: finalPoster,
                url: iframeUri.length > 0 ? iframeUri : infoUrl,
                duration: durationMs,
                views: desc,   // как в рабочем Kotlin: описание идёт в views
                description: desc,
                source: this.meta.name
            };
        } catch (e) {
            this._log("getVideoInfo error: " + e);
            return null;
        }
    },

    // ============================== СЕРИИ ==============================

    getEpisodes: function (seriesUrl) {
        try {
            var mediaId = this._extractMediaId(seriesUrl);
            var infoUrl = mediaId ? (this.meta.baseUrl + "/info/" + mediaId) : seriesUrl;

            var headers = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.replace(/^\s+/, "").charAt(0) !== '{') return null;

            var root = JSON.parse(body);
            var episodesObj = root.episodes;
            if (!episodesObj) return null;

            var baseIframeUri = this._unescapeJs(root.iframe_uri || root.iframe || root.embed || "");
            if (baseIframeUri.indexOf("//") === 0) baseIframeUri = "https:" + baseIframeUri;
            if (baseIframeUri.charAt(0) === "/") baseIframeUri = "https://liftw.ws" + baseIframeUri;

            var info = root.info || {};
            var episodeTime = String(info.time || "");
            var rawPoster = String(root.poster || "");
            var poster = rawPoster.length > 0 ? rawPoster + "#vertical" : "";
            var currentMediaId = String(root.id || mediaId || "0");

            // Числовая сортировка сезонов
            var sortedSeasons = Object.keys(episodesObj)
                .map(function (k) { return parseInt(k, 10); })
                .filter(function (n) { return !isNaN(n); })
                .sort(function (a, b) { return a - b; });

            var episodesList = [];

            for (var si = 0; si < sortedSeasons.length; si++) {
                var s = sortedSeasons[si];
                var epRaw = episodesObj[String(s)];
                if (!epRaw) continue;

                // В Kotlin: epArray.optString(i).toIntOrNull() — серии в виде массива строк
                var epArr = Array.isArray(epRaw) ? epRaw : Object.keys(epRaw);
                var sortedEps = epArr
                    .map(function (v) { return parseInt(v, 10); })
                    .filter(function (n) { return !isNaN(n); })
                    .sort(function (a, b) { return a - b; });

                for (var ei = 0; ei < sortedEps.length; ei++) {
                    var e = sortedEps[ei];
                    var sep = baseIframeUri.indexOf("?") !== -1 ? "&" : "?";
                    var episodeIframeUrl = baseIframeUri.length > 0
                        ? (baseIframeUri + sep + "season=" + s + "&episode=" + e)
                        : (this.meta.baseUrl + "/info/" + currentMediaId + "?season=" + s + "&episode=" + e);

                    var cleanDuration = "";
                    if (episodeTime) {
                        var m = episodeTime.match(/(\d+\s*мин)/);
                        cleanDuration = m ? m[1] : episodeTime.split("(")[0].trim();
                    }

                    episodesList.push({
                        id: currentMediaId + "_s" + s + "_e" + e,
                        title: "Серия " + e,
                        author: cleanDuration,
                        thumbnail: poster,
                        url: episodeIframeUrl,
                        duration: 0,
                        views: "S" + s + "E" + e,
                        source: this.meta.name,
                        isSeries: false,
                        season: s,
                        episode: e,
                        contentType: "EPISODE"
                    });
                }
            }

            return episodesList.length > 0 ? episodesList : null;
        } catch (e) {
            this._log("getEpisodes error: " + e);
            return null;
        }
    },

    // ============================== ПОТОК ==============================

    resolveStream: function (url, audioOnly) {
        try {
            this._log("1. resolveStream: " + url);

            // --- Шаг 1: получить embed URL ---
            var rawEmbedUrl;
            if (url.indexOf("/info/") !== -1 || /^\d+$/.test(url)) {
                var mediaId = this._extractMediaId(url);
                var infoUrl = mediaId ? (this.meta.baseUrl + "/info/" + mediaId) : url;

                var infoHeaders = {
                    "User-Agent": this.USER_AGENT,
                    "Origin": "https://liftw.ws",
                    "Referer": "https://liftw.ws/",
                    "Accept": "application/json"
                };
                var infoBody = bridge.request("GET", infoUrl, JSON.stringify(infoHeaders), "");
                if (!infoBody || infoBody.replace(/^\s+/, "").charAt(0) !== '{') return null;

                var json = JSON.parse(infoBody);
                var extractedIframe = String(json.iframe_uri || json.iframe || json.embed || "");
                if (extractedIframe.charAt(0) === "/") extractedIframe = "https://liftw.ws" + extractedIframe;

                var sM = url.match(/[?&]season=(\d+)/);
                var eM = url.match(/[?&]episode=(\d+)/);
                if (sM && eM && extractedIframe) {
                    var sep = extractedIframe.indexOf("?") !== -1 ? "&" : "?";
                    extractedIframe = extractedIframe + sep + "season=" + sM[1] + "&episode=" + eM[1];
                }
                rawEmbedUrl = extractedIframe;
            } else {
                rawEmbedUrl = url;
            }

            if (!rawEmbedUrl) return null;

            var cleanEmbedUrl = this._unescapeJs(rawEmbedUrl);
            if (cleanEmbedUrl.indexOf("//") === 0) cleanEmbedUrl = "https:" + cleanEmbedUrl;
            if (cleanEmbedUrl.charAt(0) === "/") cleanEmbedUrl = "https://liftw.ws" + cleanEmbedUrl;
            this._log("2. embed URL: " + cleanEmbedUrl);

            // --- Шаг 2: скачать embed-страницу ---
            var embedHeaders = {
                "User-Agent": this.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Referer": "https://liftw.ws/"
            };
            var embedHtml = bridge.request("GET", cleanEmbedUrl, JSON.stringify(embedHeaders), "") || "";
            if (!embedHtml) { this._log("empty embed html"); return null; }

            var finalStreamUrl = null;
            var urlRegex = /(https?:\/\/[^,"'|\[\]\s<>]+)/;

            // --- Шаг 3: конфиг плеера (hls|file|playlist|dash) : "https://...\.(m3u8|mp4|txt|json)..." ---
            var configRegex = /(?:hls|file|playlist|dash)\s*:\s*["'](https?:\/\/[^"']+\.(?:m3u8|mp4|txt|json)[^"']*)["']/g;
            var match;
            while ((match = configRegex.exec(embedHtml)) !== null) {
                var extractedData = this._unescapeJs(match[1]);

                if (extractedData.indexOf("#2") === 0) {
                    try { extractedData = bridge.decodeBase64(extractedData.substring(2)); } catch (_) {}
                } else if (extractedData.indexOf("//_//") === 0) {
                    try { extractedData = bridge.decodeBase64(extractedData.replace(/\/\/_\/\//g, "")); } catch (_) {}
                }

                var firstUrlMatch = extractedData.match(urlRegex);
                var firstUrl = firstUrlMatch ? firstUrlMatch[1] : null;
                if (!firstUrl) continue;

                if (firstUrl.indexOf(".m3u8") !== -1 || firstUrl.indexOf(".mp4") !== -1 ||
                    firstUrl.indexOf("interkh") !== -1 || firstUrl.slice(-2) === "==") {
                    finalStreamUrl = firstUrl;
                    break;
                } else {
                    var plHeaders = { "Referer": cleanEmbedUrl, "User-Agent": this.USER_AGENT };
                    var plTextRaw = bridge.request("GET", firstUrl, JSON.stringify(plHeaders), "") || "";
                    if (plTextRaw.indexOf("#EXTM3U") === 0) {
                        finalStreamUrl = firstUrl;
                        break;
                    } else {
                        var plText = plTextRaw;
                        if (plText.indexOf("#2") === 0) {
                            try { plText = bridge.decodeBase64(plText.substring(2)); } catch (_) {}
                        }
                        var sub = plText.match(urlRegex);
                        finalStreamUrl = sub ? sub[1] : firstUrl;
                        break;
                    }
                }
            }

            // --- Шаг 4: strict m3u8 в raw HTML ---
            if (!finalStreamUrl) {
                var strict = embedHtml.match(/(https?:\/\/[^"'\s<>|\[\]{},]+\.m3u8[^"'\s<>|\[\]{},]*)/);
                if (strict) {
                    finalStreamUrl = strict[1];
                    this._log("strict m3u8: " + finalStreamUrl);
                }
            }

            // --- Шаг 5: балансер через iframe ---
            if (!finalStreamUrl) {
                var iframeMatch = embedHtml.match(/<iframe[^>]+src=["']([^"']+)["']/);
                var iframeUrl = iframeMatch ? iframeMatch[1] : null;

                if (iframeUrl) {
                    if (iframeUrl.indexOf("//") === 0) iframeUrl = "https:" + iframeUrl;
                    if (iframeUrl.charAt(0) === "/") iframeUrl = "https://liftw.ws" + iframeUrl;
                    iframeUrl = this._unescapeJs(iframeUrl);

                    var sM2 = cleanEmbedUrl.match(/[?&]season=(\d+)/);
                    var eM2 = cleanEmbedUrl.match(/[?&]episode=(\d+)/);
                    var sP = sM2 ? parseInt(sM2[1], 10) : null;
                    var eP = eM2 ? parseInt(eM2[1], 10) : null;
                    if (sP !== null && eP !== null && iframeUrl.indexOf("season=") === -1) {
                        var sep2 = iframeUrl.indexOf("?") !== -1 ? "&" : "?";
                        iframeUrl = iframeUrl + sep2 + "season=" + sP + "&episode=" + eP;
                    }

                    this._log("balancer iframe: " + iframeUrl);

                    var balHeaders = { "User-Agent": this.USER_AGENT, "Referer": cleanEmbedUrl };
                    var balancerHtml = bridge.request("GET", iframeUrl, JSON.stringify(balHeaders), "") || "";

                    if (sP !== null && eP !== null) {
                        var seasonsMatch = balancerHtml.match(/seasons\s*:\s*(\[\{[\s\S]*?\}\])\s*[,;]/);
                        if (seasonsMatch) {
                            try {
                                var sArr = JSON.parse(seasonsMatch[1]);
                                for (var sidx = 0; sidx < sArr.length; sidx++) {
                                    var sObj = sArr[sidx];
                                    if (Number(sObj.season || (sidx + 1)) !== sP) continue;
                                    var epArr = sObj.episodes || [];
                                    for (var eidx = 0; eidx < epArr.length; eidx++) {
                                        var epObj = epArr[eidx];
                                        if (Number(epObj.episode || (eidx + 1)) !== eP) continue;
                                        var hls = String(epObj.hls || epObj.url || "")
                                            .replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
                                        if (hls) { finalStreamUrl = hls; break; }
                                    }
                                    if (finalStreamUrl) break;
                                }
                            } catch (_) {}
                        }
                    }

                    if (!finalStreamUrl) {
                        var balStrict = balancerHtml.match(/(https?:\/\/[^"'\s<>|\[\]{},]+\.m3u8[^"'\s<>|\[\]{},]*)/);
                        if (balStrict) finalStreamUrl = balStrict[1];
                    }

                    if (!finalStreamUrl) {
                        var fileMatch = balancerHtml.match(/(?:file|url)\s*["':]+\s*["']([^"']+)["']/);
                        if (fileMatch) {
                            var fmUrl = fileMatch[1].match(urlRegex);
                            if (fmUrl) finalStreamUrl = fmUrl[1];
                        }
                    }
                }
            }

            if (!finalStreamUrl) {
                this._log("Поток не найден для " + cleanEmbedUrl);
                return null;
            }

            if (finalStreamUrl.indexOf("//") === 0) finalStreamUrl = "https:" + finalStreamUrl;
            finalStreamUrl = this._unescapeJs(finalStreamUrl);

            // --- Шаг 6: токен авторизации var lok = 1, xxx = "token" ---
            var tokenMatch = embedHtml.match(/var\s+lok\s*=\s*1\s*,\s*[a-zA-Z0-9_]+\s*=\s*["']([^"']+)["']/);
            if (tokenMatch && tokenMatch[1] && finalStreamUrl.indexOf(tokenMatch[1]) === -1) {
                var sep3 = finalStreamUrl.indexOf("?") !== -1 ? "&" : "?";
                finalStreamUrl = finalStreamUrl + sep3 + tokenMatch[1];
                this._log("токен прикреплён: " + tokenMatch[1]);
            }

            this._log("5. ФИНАЛЬНЫЙ ПОТОК: " + finalStreamUrl);

            var playerHeaders = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/"
            };

            return {
                streamUrl: finalStreamUrl,
                mimeType: finalStreamUrl.indexOf(".mp4") !== -1 ? "video/mp4" : "application/x-mpegURL",
                headers: playerHeaders
            };
        } catch (e) {
            this._log("resolveStream error: " + e);
            return null;
        }
    },

    // ============================== УТИЛИТЫ ==============================

    _extractMediaId: function (url) {
        if (!url) return null;
        var s = String(url).trim();
        if (/^\d+$/.test(s)) return s;

        var m = s.match(/plugin_\w+_(\d+)(?:_s\d+_e\d+)?/);
        if (m) return m[1];
        m = s.match(/^(\d+)_s\d+_e\d+/);
        if (m) return m[1];
        m = s.match(/\/info\/(\d+)/);
        if (m) return m[1];
        m = s.match(/\/movie\/(\d+)/);
        if (m) return m[1];
        m = s.match(/[?&]id=(\d+)/);
        if (m) return m[1];
        return null;
    }
};