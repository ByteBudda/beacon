/**
 * Полноценный боевой JS-плагин Liftw для системы QuickJS.
 * Исправлено извлечение iframe_uri из /info/{id} и декодирование скрытых Base64 (#2) потоков.
 */
var plugin = globalThis.plugin = {
    meta: {
        name: "Liftw",
        baseUrl: "https://api.liftw.ws",
        aliases: ["Lift", "Liftw", "Лифт", "Фильмы и сериалы", "Кино"],
        domains: ["liftw.ws", "api.liftw.ws", "embed.liftw.ws", "interkh.com"],
        icon: "movie",
        requiresAuth: false
    },

    USER_AGENT: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",

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

            if (cat === "all" && (trimmed.length === 0 || trimmed.charAt(0) !== '[' || trimmed === "[]")) {
                var fallbackUrl = this.meta.baseUrl + "/list/categories?category=films&page=" + p + "&limit=20&sort=popular&last=true";
                body = bridge.request("GET", fallbackUrl, JSON.stringify(headers), "");
                trimmed = (body || "").trim();
            }

            if (!trimmed || trimmed.charAt(0) !== '[') return [];

            var arr = JSON.parse(trimmed);
            var results = [];

            for (var i = 0; i < arr.length; i++) {
                if (arr[i]) {
                    results.push(this._parseApiItem(arr[i], cat === "all" ? null : cat));
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
                "Origin": "https://liftw.ws",
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
                .map(function(k) { return parseInt(k, 10); })
                .filter(function(n) { return !isNaN(n); });
            seasonKeys.sort(function(a, b) { return a - b; });

            var episodesList = [];

            for (var si = 0; si < seasonKeys.length; si++) {
                var s = seasonKeys[si];
                var epRaw = episodesObj[String(s)];
                var numArr = [];

                if (Array.isArray(epRaw)) {
                    for (var ei = 0; ei < epRaw.length; ei++) {
                        var itemEp = epRaw[ei];
                        var n = typeof itemEp === "object" && itemEp !== null
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

                numArr.sort(function(a, b) { return a - b; });

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
            return null;
        }
    },

    resolveStream: function(url, audioOnly) {
        try {
            var embedCandidates = this._resolveEmbedCandidates(url);
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
                    if (!embedHtml || embedHtml.length < 20) continue;

                    var candidate = this._extractStreamFromHtml(embedHtml, cleanEmbedUrl);
                    if (candidate) {
                        foundStream = candidate;
                        usedHtml = embedHtml;
                        usedEmbedUrl = cleanEmbedUrl;
                        break;
                    }
                    if (!usedHtml) usedHtml = embedHtml;
                }
                if (foundStream) break;
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

            var originHost = "https://liftw.ws";
            var hostMatch = usedEmbedUrl.match(/^(https?:\/\/[^/]+)/);
            if (hostMatch) originHost = hostMatch[1];

            var playerHeaders = {
                "User-Agent": this.USER_AGENT,
                "Origin": originHost,
                "Referer": originHost + "/"
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

    _extractIframeFromObj: function(obj) {
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
        // На случай, если ссылка лежит в любом другом строковом поле JSON
        var rawJson = JSON.stringify(obj);
        var m = rawJson.match(/["']((?:https?:)?\/\/[^"']*(?:embed|interkh|play|iframe)[^"']*)["']/i);
        if (m && m[1]) {
            return this._normalizeIframe(m[1]);
        }
        return "";
    },

    _resolveEmbedCandidates: function(url) {
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

        // Если переданный url уже является прямым embed-адресом (а не /info/83478)
        if (url.indexOf("/info/") === -1 && !/^\d+$/.test(url)) {
            candidates.push(appendParams(url));
        }

        // Всегда дополнительно проверяем /info/{id}, чтобы достать свежий iframe_uri с токеном
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
                        if (candidates.indexOf(withParams) === -1) {
                            // Ставим свежий iframe из /info/{id} на первое место!
                            candidates.unshift(withParams);
                        }
                    }
                } catch (_) {}
            }

            // Резервные шаблоны на случай, если API не вернуло поле iframe_uri
            candidates.push(appendParams("https://embed.liftw.ws/embed/" + mediaId));
            candidates.push(appendParams("https://liftw.ws/embed/" + mediaId));
        }

        return candidates;
    },

    _extractStreamFromHtml: function(embedHtml, cleanEmbedUrl) {
        // 1. Ищем любые параметры плеера: file, hls, playlist, dash, src (даже если там Base64 #2... без http!)
        var configRegex = /(?:hls|file|playlist|dash|stream)\s*[:=]\s*["']([^"']{8,})["']/gi;
        var match;

        while ((match = configRegex.exec(embedHtml)) !== null) {
            var rawVal = match[1].trim();
            if (rawVal.indexOf(".js") !== -1 || rawVal.indexOf(".css") !== -1 || rawVal.indexOf(".svg") !== -1 || rawVal.indexOf(".png") !== -1) {
                continue;
            }

            var decoded = this._decodeIfBase64(rawVal);
            var bestUrl = this._pickBestStreamUrl(decoded);
            if (!bestUrl) continue;

            if (bestUrl.indexOf(".m3u8") !== -1 || bestUrl.indexOf(".mp4") !== -1 || bestUrl.indexOf("interkh") !== -1) {
                return bestUrl;
            }

            // Если это ссылка на текстовый/JSON плейлист (.txt / .json)
            if (bestUrl.indexOf("http") === 0) {
                var plHeaders = { "User-Agent": this.USER_AGENT, "Referer": cleanEmbedUrl };
                var plTextRaw = bridge.request("GET", bestUrl, JSON.stringify(plHeaders), "") || "";
                if (plTextRaw.indexOf("#EXTM3U") === 0) return bestUrl;

                var plDecoded = this._decodeIfBase64(plTextRaw);
                var subBest = this._pickBestStreamUrl(plDecoded);
                if (subBest) return subBest;
            }
        }

        // 2. Ищем зашифрованные строки PlayerJS вида "#2..." или "//_//..." в любом месте скрипта
        var b64Regex = /["']((?:#2|\/\/_\/\/)[A-Za-z0-9+/=_/-]{20,})["']/g;
        while ((match = b64Regex.exec(embedHtml)) !== null) {
            var dec = this._decodeIfBase64(match[1]);
            var bUrl = this._pickBestStreamUrl(dec);
            if (bUrl && (bUrl.indexOf(".m3u8") !== -1 || bUrl.indexOf(".mp4") !== -1)) {
                return bUrl;
            }
        }

        // 3. Прямой поиск m3u8 / mp4 в коде страницы
        var directBest = this._pickBestStreamUrl(embedHtml);
        if (directBest && (directBest.indexOf(".m3u8") !== -1 || directBest.indexOf(".mp4") !== -1)) {
            return directBest;
        }

        // 4. Переход во вложенный iframe балансера
        return this._resolveViaBalancer(embedHtml, cleanEmbedUrl);
    },

    /**
     * Извлекает лучшую ссылку на поток из строки PlayerJS (например "[1080p]https://...m3u8,[720p]https://...m3u8")
     */
    _pickBestStreamUrl: function(text) {
        if (!text) return null;
        var clean = String(text).replace(/\\\//g, "/").replace(/\\u0026/g, "&");

        // Ищем все URL с .m3u8 или .mp4
        var m3u8Regex = /(https?:\/\/[^,"'\s<>|\[\]{}]+\.(?:m3u8|mp4)[^,"'\s<>|\[\]{}]*)/gi;
        var allMatches = [];
        var m;
        while ((m = m3u8Regex.exec(clean)) !== null) {
            allMatches.push(m[1]);
        }

        if (allMatches.length > 0) {
            // Если несколько потоков (360p, 720p, 1080p), обычно последний или с 1080/720 — самый качественный
            for (var i = 0; i < allMatches.length; i++) {
                if (allMatches[i].indexOf("1080") !== -1) return allMatches[i];
            }
            for (var j = 0; j < allMatches.length; j++) {
                if (allMatches[j].indexOf("720") !== -1) return allMatches[j];
            }
            return allMatches[allMatches.length - 1];
        }

        // Иначе возвращаем первый валидный http-адрес
        var genericMatch = clean.match(/(https?:\/\/[^,"'|\[\]\s<>]+)/);
        return genericMatch ? genericMatch[1] : null;
    },

    _resolveViaBalancer: function(embedHtml, refererUrl) {
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

        var bHeaders = { "User-Agent": this.USER_AGENT, "Referer": refererUrl };
        var balancerHtml = bridge.request("GET", iframeUrl, JSON.stringify(bHeaders), "") || "";
        if (!balancerHtml) return null;

        // Если это сериал и внутри балансера есть дерево seasons: [...]
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

        // Пробуем стандартный парсер по HTML балансера (но без бесконечной рекурсии)
        var bStream = this._pickBestStreamUrl(balancerHtml);
        if (bStream && (bStream.indexOf(".m3u8") !== -1 || bStream.indexOf(".mp4") !== -1)) {
            return bStream;
        }

        var configRegex = /(?:hls|file|playlist|dash|url)\s*[:=]\s*["']([^"']{8,})["']/gi;
        var m;
        while ((m = configRegex.exec(balancerHtml)) !== null) {
            var dec = this._decodeIfBase64(m[1]);
            var u = this._pickBestStreamUrl(dec);
            if (u && (u.indexOf(".m3u8") !== -1 || u.indexOf(".mp4") !== -1)) return u;
        }

        return null;
    },

    _parseApiItem: function(item, forcedCategory) {
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

    _normalizeIframe: function(raw) {
        var s = String(raw || "").replace(/\\\//g, "/").replace(/\\u0026/g, "&").trim();
        if (s.indexOf("//") === 0) s = "https:" + s;
        if (s.indexOf("/") === 0) s = "https://liftw.ws" + s;
        return s;
    },

    _decodeIfBase64: function(s) {
        var trimmed = String(s || "").trim();
        if (trimmed.indexOf("#2") === 0) {
            try {
                // В PlayerJS внутри строки #2 иногда вставляются мусорные разделители //_//
                var cleanB64 = trimmed.substring(2).replace(/\/\/_\/\/[^\s"']*/g, "");
                return bridge.decodeBase64(cleanB64) || bridge.decodeBase64(trimmed.substring(2)) || trimmed;
            } catch (_) {
                return trimmed;
            }
        }
        if (trimmed.indexOf("//_//") === 0) {
            try {
                return bridge.decodeBase64(trimmed.substring(5)) || trimmed;
            } catch (_) {
                return trimmed;
            }
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
        m = str.match(/[?&]id=(\d+)/);
        if (m) return m[1];
        m = str.match(/\/(?:info|movie|embed|play|e|video|serial)\/(\d+)/);
        if (m) return m[1];
        m = str.match(/\/(\d+)(?:[/?#]|$)/);
        if (m) return m[1];
        return null;
    }
};
