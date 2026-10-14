/**
 * Полноценный боевой JS-плагин Liftw для системы QuickJS.
 * - Глобальная привязка var plugin = globalThis.plugin
 * - Вызовы bridge.request строго со строками "" вместо null (защита от падений JNI)
 * - Единый парсер карточек (_parseApiItem) с поддержкой вложенного объекта info.*
 * - Формирование полного описания (жанр • страна, возраст • время • MPAA, сюжет)
 * - Разбор embed-плеера (Base64 #2 / //_//, токены lok, iframe-балансеры, дерево seasons)
 */
var plugin = globalThis.plugin = {
    meta: {
        name: "Lift",
        baseUrl: "https://api.liftw.ws",
        aliases: ["Lift", "Лифт", "Фильмы и сериалы", "Кино"],
        domains: ["liftw.ws", "api.liftw.ws", "embed.liftw.ws", "interkh.com"],
        icon: "movie",
        requiresAuth: false
    },

    USER_AGENT: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

    SERIES_CATEGORIES: {
        "series": true,
        "cartoon_series": true,
        "anime_series": true,
        "tvshows": true
    },

    checkAuth: function() {
        return true;
    },

    login: function(username, password) {
        return { success: true };
    },

    getCatalogCategories: function() {
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

    getCatalogItems: function(category, page) {
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
            if (!body) return [];

            var trimmed = body.trim();
            if (trimmed.charAt(0) !== '[') return [];

            var arr = JSON.parse(trimmed);
            var results = [];

            for (var i = 0; i < arr.length; i++) {
                if (arr[i]) {
                    results.push(this._parseApiItem(arr[i], cat));
                }
            }
            return results;
        } catch (e) {
            return [];
        }
    },

    search: function(query, limit) {
        try {
            var cleanQ = (query || "").trim();
            if (!cleanQ) return [];

            var maxLimit = limit || 30;
            var url = this.meta.baseUrl + "/search?q=" + encodeURIComponent(cleanQ);
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Accept": "application/json, text/html, */*"
            };

            var results = [];
            var seenIds = {};

            // 1. Основной поиск через API
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

            // 2. Фоллбек по популярному каталогу, если результатов мало
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
            return [];
        }
    },

    getVideoInfo: function(url) {
        try {
            var mediaId = this._extractMediaId(url);
            if (!mediaId) return null;

            var infoUrl = this.meta.baseUrl + "/info/" + mediaId;
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.trim().charAt(0) !== '{') return null;

            var root = JSON.parse(body.trim());
            return this._parseApiItem(root, null);
        } catch (e) {
            return null;
        }
    },

    getEpisodes: function(seriesUrl) {
        try {
            var mediaId = this._extractMediaId(seriesUrl);
            if (!mediaId) return null;

            var infoUrl = this.meta.baseUrl + "/info/" + mediaId;
            var headers = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/",
                "Accept": "application/json"
            };
            var body = bridge.request("GET", infoUrl, JSON.stringify(headers), "");
            if (!body || body.trim().charAt(0) !== '{') return null;

            var root = JSON.parse(body.trim());
            var episodesObj = root.episodes;
            if (!episodesObj) return null;

            var baseIframeUri = this._normalizeIframe(root.iframe_uri || root.iframe || root.embed || "");
            var currentMediaId = String(root.id || mediaId);

            var episodeTime = this._optStringSmart(root, ["time"]);
            var episodeDurationMs = this._parseDurationMs(episodeTime) || 0;

            var rawPoster = root.poster || "";
            var poster = rawPoster ? rawPoster + "#vertical" : "";

            var seasonKeys = Object.keys(episodesObj)
                .map(function(k) { return parseInt(k, 10); })
                .filter(function(n) { return !isNaN(n); });
            seasonKeys.sort(function(a, b) { return a - b; });

            var episodesList = [];

            for (var si = 0; si < seasonKeys.length; si++) {
                var s = seasonKeys[si];
                var epArr = episodesObj[String(s)] || [];
                var numArr = [];
                for (var ei = 0; ei < epArr.length; ei++) {
                    var n = parseInt(epArr[ei], 10);
                    if (!isNaN(n)) numArr.push(n);
                }
                numArr.sort(function(a, b) { return a - b; });

                for (var k = 0; k < numArr.length; k++) {
                    var e = numArr[k];
                    var episodeIframeUrl;
                    if (baseIframeUri.length > 0) {
                        var sep = baseIframeUri.indexOf("?") !== -1 ? "&" : "?";
                        episodeIframeUrl = baseIframeUri + sep + "season=" + s + "&episode=" + e;
                    } else {
                        episodeIframeUrl = this.meta.baseUrl + "/info/" + currentMediaId + "?season=" + s + "&episode=" + e;
                    }

                    episodesList.push({
                        id: currentMediaId + "_s" + s + "_e" + e,
                        title: "Сезон " + s + ", серия " + e,
                        author: episodeTime,
                        thumbnail: poster,
                        url: episodeIframeUrl,
                        duration: episodeDurationMs,
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
            return null;
        }
    },

    resolveStream: function(url, audioOnly) {
        try {
            var rawEmbedUrl = this._resolveEmbedUrl(url);
            if (!rawEmbedUrl) return null;

            var cleanEmbedUrl = this._normalizeIframe(rawEmbedUrl);
            var referers = [
                "https://liftw.ws/",
                "https://lift.com/",
                "https://liftw.ws/embed/"
            ];

            var foundStream = null;
            var usedHtml = "";

            for (var r = 0; r < referers.length; r++) {
                var embedHeaders = {
                    "User-Agent": this.USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": referers[r]
                };
                var embedHtml = bridge.request("GET", cleanEmbedUrl, JSON.stringify(embedHeaders), "");
                if (!embedHtml) continue;

                var candidate = this._extractStreamFromHtml(embedHtml, cleanEmbedUrl);
                if (candidate) {
                    foundStream = candidate;
                    usedHtml = embedHtml;
                    break;
                }
                if (!usedHtml) usedHtml = embedHtml;
            }

            if (!foundStream) return null;

            var stream = foundStream;
            if (stream.indexOf("//") === 0) stream = "https:" + stream;
            stream = stream.replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();

            // Токен авторизации lok
            var tokenMatch = usedHtml.match(/var\s+lok\s*=\s*1\s*,\s*[a-zA-Z0-9_]+\s*=\s*["']([^"']+)["']/);
            if (tokenMatch && tokenMatch[1] && stream.indexOf(tokenMatch[1]) === -1) {
                var sep = stream.indexOf("?") !== -1 ? "&" : "?";
                stream = stream + sep + tokenMatch[1];
            }

            var playerHeaders = {
                "User-Agent": this.USER_AGENT,
                "Referer": "https://liftw.ws/"
            };

            return {
                streamUrl: stream,
                mimeType: stream.indexOf(".mp4") !== -1 ? "video/mp4" : "application/x-mpegURL",
                width: 1920,
                height: 1080,
                headers: playerHeaders
            };
        } catch (e) {
            return null;
        }
    },

    // ====================== ВНУТРЕННИЕ ПАРСЕРЫ И УТИЛИТЫ ======================

    _parseApiItem: function(item, forcedCategory) {
        var info = item.info || {};
        var id = String(item.id || "");
        var type = item.type || 1;
        var serialStatus = String(item.serial_status || "").trim();
        var hasEpisodesObj = !!item.episodes;

        var isSeries = (type === 3 || type === 4 || type === 5) ||
            hasEpisodesObj ||
            serialStatus.length > 0 ||
            (forcedCategory != null && !!this.SERIES_CATEGORIES[forcedCategory]);

        var yearNum = parseInt(item.year || info.year || 0, 10);
        var year = (!isNaN(yearNum) && yearNum > 0) ? yearNum : null;

        var quality = String(item.quality || "").trim();
        var kpRating = parseFloat(item.kp_rating || 0);
        var imdbRating = parseFloat(item.imdb_rating || 0);
        var rating = (!isNaN(kpRating) && kpRating > 0) ? kpRating : ((!isNaN(imdbRating) && imdbRating > 0) ? imdbRating : null);

        var badges = [];
        if (serialStatus.length > 0) {
            badges.push(serialStatus);
        } else if (isSeries) {
            badges.push("Сериал");
        }
        if (quality.length > 0) badges.push(quality);
        if (rating !== null) {
            if (!isNaN(kpRating) && kpRating > 0) badges.push("КП " + kpRating.toFixed(1));
            else badges.push("IMDb " + imdbRating.toFixed(1));
        }
        if (year !== null) badges.push(String(year));

        var iframeUri = this._normalizeIframe(item.iframe_uri || item.iframe || item.embed || "");
        var targetUrl = iframeUri.length > 0 ? iframeUri : (this.meta.baseUrl + "/info/" + id);

        var rawPoster = String(item.poster || "").trim();
        var poster = rawPoster.length > 0 ? (rawPoster + "#vertical") : "";

        var description = this._optStringSmart(item, ["description"]);
        var genre = this._optStringArraySmart(item, "genre");
        var country = this._optStringArraySmart(item, "country");
        var age = this._optStringSmart(item, ["age"]);
        var time = this._optStringSmart(item, ["time"]);
        var mpaa = this._optStringSmart(item, ["rate_mpaa"]);

        var fullDescription = this._buildFullDescription(genre, country, age, time, mpaa, description);

        var originName = String(item.origin_name || info.name_eng || "").trim();
        var durationMs = isSeries ? 1 : (this._parseDurationMs(time) || 7200000);
        var title = String(info.name || item.name || "Без названия").trim() || "Без названия";

        return {
            id: id,
            title: title,
            author: originName || (year ? String(year) : "Liftw"),
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

    _extractStreamFromHtml: function(embedHtml, cleanEmbedUrl) {
        var urlRegex = /(https?:\/\/[^,"'|\[\]\s<>]+)/;
        var configRegex = /(?:hls|file|playlist|dash)\s*:\s*["'](https?:\/\/[^"']+\.(?:m3u8|mp4|txt|json)[^"']*)["']/g;
        var match;

        while ((match = configRegex.exec(embedHtml)) !== null) {
            var data = this._decodeIfBase64(match[1]);
            var urlMatch = data.match(urlRegex);
            if (!urlMatch) continue;

            var firstUrl = urlMatch[1];
            if (firstUrl.indexOf(".m3u8") !== -1 || firstUrl.indexOf(".mp4") !== -1 || firstUrl.indexOf("interkh") !== -1) {
                return firstUrl;
            }

            var plHeaders = { "User-Agent": this.USER_AGENT, "Referer": cleanEmbedUrl };
            var plTextRaw = bridge.request("GET", firstUrl, JSON.stringify(plHeaders), "") || "";
            if (plTextRaw.indexOf("#EXTM3U") === 0) return firstUrl;

            var plText = this._decodeIfBase64(plTextRaw);
            var subMatch = plText.match(urlRegex);
            return subMatch ? subMatch[1] : firstUrl;
        }

        var strictMatch = embedHtml.match(/(https?:\/\/[^"'\s<>|\[\]{},]+\.m3u8[^"'\s<>|\[\]{},]*)/);
        if (strictMatch) return strictMatch[1];

        return this._resolveViaBalancer(embedHtml, cleanEmbedUrl, urlRegex);
    },

    _resolveEmbedUrl: function(url) {
        var sMatch = url.match(/[?&]season=(\d+)/);
        var eMatch = url.match(/[?&]episode=(\d+)/);
        var sParam = sMatch ? sMatch[1] : null;
        var eParam = eMatch ? eMatch[1] : null;

        var mediaId = this._extractMediaId(url);
        var needsInfoFetch = url.indexOf("/info/") !== -1 ||
            /^\d+$/.test(url) ||
            (mediaId !== null && (
                url.indexOf("embed.liftw.ws") !== -1 ||
                url.indexOf("interkh") !== -1 ||
                url.indexOf("liftw.ws/embed") !== -1
            ));

        if (!needsInfoFetch || !mediaId) return url;

        var headers = {
            "User-Agent": this.USER_AGENT,
            "Referer": "https://liftw.ws/",
            "Accept": "application/json"
        };
        var infoBody = bridge.request("GET", this.meta.baseUrl + "/info/" + mediaId, JSON.stringify(headers), "");
        if (!infoBody || infoBody.trim().charAt(0) !== '{') return url;

        var json = JSON.parse(infoBody.trim());
        var extractedIframe = this._normalizeIframe(json.iframe_uri || json.iframe || json.embed || "");
        if (!extractedIframe) return url;

        if (sParam && eParam && extractedIframe.indexOf("season=") === -1) {
            var sep = extractedIframe.indexOf("?") !== -1 ? "&" : "?";
            return extractedIframe + sep + "season=" + sParam + "&episode=" + eParam;
        }
        return extractedIframe;
    },

    _resolveViaBalancer: function(embedHtml, refererUrl, urlRegex) {
        var iframeMatch = embedHtml.match(/<iframe[^>]+src=["']([^"']+)["']/);
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

        var bHeaders = { "User-Agent": this.USER_AGENT, "Referer": refererUrl };
        var balancerHtml = bridge.request("GET", iframeUrl, JSON.stringify(bHeaders), "") || "";

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
                            var hls = String(eObj.hls || eObj.url || "").replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
                            if (hls) return hls;
                        }
                    }
                } catch (_) {}
            }
        }

        var bMatch = balancerHtml.match(/(https?:\/\/[^"'\s<>|\[\]{},]+\.m3u8[^"'\s<>|\[\]{},]*)/);
        if (bMatch) return bMatch[1];

        var fileMatch = balancerHtml.match(/(?:file|url)\s*["':]+\s*["']([^"']+)["']/);
        if (fileMatch) {
            var uMatch = fileMatch[1].match(urlRegex);
            if (uMatch) return uMatch[1];
        }
        return null;
    },

    _normalizeIframe: function(raw) {
        var s = String(raw || "").replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
        if (s.indexOf("//") === 0) s = "https:" + s;
        if (s.indexOf("/") === 0) s = "https://liftw.ws" + s;
        return s;
    },

    _decodeIfBase64: function(s) {
        var trimmed = String(s || "").trim();
        if (trimmed.indexOf("#2") === 0) {
            try { return bridge.decodeBase64(trimmed.substring(2)) || trimmed; } catch (_) { return trimmed; }
        }
        if (trimmed.indexOf("//_//") === 0) {
            try { return bridge.decodeBase64(trimmed.substring(5)) || trimmed; } catch (_) { return trimmed; }
        }
        return trimmed;
    },

    _optStringSmart: function(obj, keys) {
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

    _optStringArraySmart: function(obj, key) {
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

    _buildFullDescription: function(genre, country, age, time, mpaa, description) {
        var lines = [];

        var head = [];
        if (genre && genre.length > 0) {
            var gStr = genre.join(", ");
            head.push(gStr.charAt(0).toUpperCase() + gStr.slice(1));
        }
        if (country && country.length > 0) {
            head.push(country.join(", "));
        }
        if (head.length > 0) {
            lines.push(head.join(" • "));
        }

        var sub = [];
        if (age) sub.push(age.slice(-1) === "+" ? age : (age + "+"));
        if (time) sub.push(time);
        if (mpaa) sub.push(mpaa);
        if (sub.length > 0) {
            lines.push(sub.join(" • "));
        }

        var metaBlock = lines.join("\n");
        var cleanDesc = (description || "").trim();

        if (metaBlock && cleanDesc) return metaBlock + "\n\n" + cleanDesc;
        return metaBlock || cleanDesc;
    },

    _parseDurationMs: function(timeStr) {
        if (!timeStr) return null;
        var hMatch = timeStr.match(/(\d+)\s*ч/);
        var mMatch = timeStr.match(/(\d+)\s*мин/);
        var hours = hMatch ? parseInt(hMatch[1], 10) : 0;
        var minutes = mMatch ? parseInt(mMatch[1], 10) : 0;
        if (hours > 0 || minutes > 0) {
            return (hours * 3600 + minutes * 60) * 1000;
        }

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

    _extractMediaId: function(url) {
        if (!url) return null;
        var str = String(url).trim();
        if (/^\d+$/.test(str)) return str;
        var m = str.match(/plugin_\w+_(\d+)(?:_s\d+_e\d+)?/);
        if (m) return m[1];
        m = str.match(/^(\d+)_s\d+_e\d+/);
        if (m) return m[1];
        m = str.match(/\/info\/(\d+)/);
        if (m) return m[1];
        m = str.match(/\/movie\/(\d+)/);
        if (m) return m[1];
        m = str.match(/[?&]id=(\d+)/);
        if (m) return m[1];
        return null;
    }
};
