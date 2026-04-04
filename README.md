# QNTX.Beacon

> Сервис сокращения ссылок с аналитикой, QR-кодами, тарифами, оплатой, Telegram-ботом, виджетом и расширением для браузера.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/Proprietary-red.svg)](#)

---

## Содержание

- [Возможности](#возможности)
- [Демо](#демо)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)
- [API](#api)
- [Тарифы](#тарифы)
- [Telegram бот](#telegram-бот)
- [Виджет для сайтов](#виджет-для-сайтов)
- [Расширение для браузера](#расширение-для-браузера)
- [Админ-панель](#админ-панель)
- [Модерация ссылок](#модерация-ссылок)
- [Реклама при переходе](#реклама-при-переходе)
- [Деплой](#деплой)
- [Структура проекта](#структура-проекта)

---

## Возможности

### Основные
- Сокращение ссылок с кастомными алиасами
- QR-коды для каждой ссылки
- Защита ссылок паролем
- OG мета-теги для превью в соцсетях
- Срок действия ссылок
- Теги и поиск по ссылкам
- Автосокращение URL через Telegram бота

### Аналитика
- Общая статистика кликов
- Устройства (desktop, mobile, tablet)
- Операционные системы
- Браузеры
- Источники трафика (рефереры)
- IP-адреса

### Безопасность
- Регистрация с подтверждением email
- JWT + API ключи для авторизации
- SSRF-защита (блокировка внутренних адресов)
- Rate limiting (Redis или in-memory)
- Автоматическая модерация ссылок (чёрный список, Google Safe Browsing, VirusTotal)
- TrustedHost middleware
- CORS настройка

### Монетизация
- 3 тарифных плана: Free / Pro / Business
- Оплата через ЮKassa и Yandex Pay
- Промокоды
- Рекламные вставки при переходе (для бесплатного тарифа)
- Автопродление подписок

### Интеграции
- Telegram бот для создания и управления ссылками
- JavaScript виджет для встраивания на сайты
- Расширение для Chrome / Yandex Браузер
- Импорт / экспорт ссылок (CSV, JSON)
- Webhook'и от платёжных систем

### Инфраструктура
- Docker + docker-compose (App + PostgreSQL + Redis)
- Health check endpoint для мониторинга
- Structured JSON logging
- Sentry интеграция
- Background tasks (очистка expired links, подписок)
- DB миграции при старте

---

## Демо

Главная страница:
```
https://qntx.ru
```

API документация (только в DEBUG режиме):
```
https://qntx.ru/docs
```

Health check:
```
https://qntx.ru/api/v1/health
```

---

## Установка

### Локальная разработка

```bash
# 1. Клонировать репозиторий
git clone <repo-url> beaconqntx
cd beaconqntx

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение
cp .env.example .env
# Отредактировать .env (см. раздел Конфигурация)

# 5. Запустить
python main.py
```

Открыть: http://localhost:3333

### Docker (рекомендуется для продакшена)

```bash
# Сборка и запуск (App + PostgreSQL + Redis)
docker-compose up -d

# Просмотр логов
docker-compose logs -f app

# Остановка
docker-compose down

# Полная очистка (включая данные)
docker-compose down -v
```

---

## Конфигурация

Все настройки хранятся в файле `.env`.

### Сервер

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `SERVER_HOST` | Хост для прослушивания | `0.0.0.0` |
| `SERVER_PORT` | Порт | `3333` |
| `DEBUG` | Режим отладки (документация, reload) | `false` |
| `LOG_LEVEL` | Уровень логирования | `info` |
| `LOG_FORMAT` | Формат логов: `json` или `text` | `json` |

### База данных

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DATABASE_URL` | URL БД | `sqlite:///./data/beacon.db` |
| `DB_POOL_SIZE` | Размер пула (PostgreSQL) | `10` |
| `DB_MAX_OVERFLOW` | Макс. переполнение пула | `20` |

```bash
# SQLite (разработка)
DATABASE_URL=sqlite:///./data/beacon.db

# PostgreSQL (продакшен)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/beacon
```

### Redis

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `REDIS_URL` | URL Redis (пусто = in-memory) | — |

```bash
# In-memory (разработка, сброс при рестарте)
REDIS_URL=

# Redis (продакшен)
REDIS_URL=redis://localhost:6379/0
```

### JWT и безопасность

| Переменная | Описание |
|------------|----------|
| `JWT_SECRET` | Секретный ключ JWT (ОБЯЗАТЕЛЬНО сменить!) |
| `JWT_ALGORITHM` | Алгоритм | `HS256` |
| `JWT_EXPIRATION_HOURS` | Время жизни токена (часы) | `24` |
| `BCRYPT_ROUNDS` | Сложность bcrypt | `12` |
| `ALLOWED_ORIGINS` | CORS origins через запятую | — |
| `TRUSTED_HOSTS` | Разрешённые Host header (пусто = все) | — |

```bash
# Генерация секрета
python -c "import secrets; print(secrets.token_hex(32))"
```

### Email (SMTP)

| Переменная | Описание |
|------------|----------|
| `SMTP_HOST` | SMTP сервер |
| `SMTP_PORT` | Порт | `587` |
| `SMTP_USER` | Логин |
| `SMTP_PASSWORD` | Пароль |
| `FROM_EMAIL` | От кого |
| `FROM_NAME` | Имя отправителя | `Beacon` |
| `SMTP_USE_SSL` | Использовать SSL | `false` |

### Приложение

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_NAME` | Название | `Beacon` |
| `APP_URL` | URL приложения | `http://localhost:3333` |
| `DEFAULT_DOMAIN` | Основной домен | `qntx.ru` |
| `ADMIN_EMAIL` | Email администратора | — |
| `ADMIN_PASSWORD` | Пароль администратора | — |

### Rate Limiting

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `RATE_LIMIT_REGISTER` | Лимит регистраций в окно | `3` |
| `RATE_LIMIT_LOGIN` | Лимит логинов в окно | `5` |
| `RATE_LIMIT_CREATE_LINK` | Лимит созданий ссылок | `50` |
| `RATE_LIMIT_REDIRECT` | Лимит редиректов с IP | `200` |
| `RATE_LIMIT_WINDOW_HOURS` | Окно лимитирования (часы) | `1` |

### Тарифы

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `FREE_PLAN_LIMIT` | Лимит ссылок Free | `50` |
| `PRO_PLAN_LIMIT` | Лимит ссылок Pro | `1000` |
| `PRO_PLAN_PRICE` | Цена Pro (руб/мес) | `299` |
| `BUSINESS_PLAN_LIMIT` | Лимит ссылок Business | `999999` |
| `BUSINESS_PLAN_PRICE` | Цена Business (руб/мес) | `999` |

### Платежи

| Переменная | Описание |
|------------|----------|
| `YOOKASSA_SHOP_ID` | ID магазина ЮKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ ЮKassa |
| `YANDEX_PAY_MERCHANT_ID` | ID мерчанта Yandex Pay |
| `YANDEX_PAY_SECRET_KEY` | Секретный ключ Yandex Pay |

Получить ключи ЮKassa: https://yookassa.ru/my

### Модерация

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MODERATION_ENABLED` | Автопроверка ссылок | `true` |
| `GOOGLE_SAFE_BROWSING_KEY` | Ключ Google Safe Browsing API | — |
| `VIRUSTOTAL_API_KEY` | Ключ VirusTotal API | — |
| `AUTO_BAN_ON_DETECTION` | Автобан при обнаружении угрозы | `true` |

Получить ключи:
- Google Safe Browsing: https://developers.google.com/safe-browsing/v4/get-api-key
- VirusTotal: https://www.virustotal.com/gui/my-apikey

### Telegram бот

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен бота от @BotFather |
| `TELEGRAM_BOT_USERNAME` | Username бота |

### Мониторинг

| Переменная | Описание |
|------------|----------|
| `SENTRY_DSN` | Sentry DSN для трекинга ошибок |

---

## Запуск

### Режим разработки

```bash
# С автоперезагрузкой
DEBUG=true python main.py

# Или через uvicorn напрямую
uvicorn app.main:app --reload --port 3333
```

### Режим продакшена

```bash
# Через Docker
docker-compose up -d

# Или напрямую
python main.py

# Или через gunicorn/uvicorn с несколькими воркерами
uvicorn app.main:app --host 0.0.0.0 --port 3333 --workers 4
```

### Проверка здоровья

```bash
curl http://localhost:3333/api/v1/health
```

Ответ:
```json
{
  "status": "healthy",
  "version": "3.1.0",
  "uptime_seconds": 3600,
  "checks": {
    "database": "ok",
    "redis": "disabled"
  }
}
```

---

## API

### Аутентификация

API поддерживает два способа:

**JWT Bearer token:**
```bash
curl -H "Authorization: Bearer <jwt_token>" https://qntx.ru/api/links
```

**API ключ (Pro/Business):**
```bash
curl -H "Authorization: Bearer bcon_<key>" https://qntx.ru/api/links
```

Получить API ключ: `POST /api/v1/account/api-key`

### Auth

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| POST | `/api/auth/register` | Регистрация | — |
| POST | `/api/auth/login` | Логин, получение JWT | — |
| GET | `/api/auth/verify-email?token=` | Подтверждение email | — |
| POST | `/api/auth/resend-verification` | Повторная отправка письма | — |
| POST | `/api/auth/password-reset` | Запрос сброса пароля | — |
| POST | `/api/auth/password-reset-confirm` | Подтверждение сброса | — |
| POST | `/api/auth/change-password` | Смена пароля | JWT |
| GET | `/api/auth/profile` | Профиль пользователя | JWT |

### Links

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| POST | `/api/links` | Создать ссылку | JWT/API |
| GET | `/api/links` | Список ссылок (с поиском `?q=`) | JWT/API |
| GET | `/api/links/{id}` | Детали ссылки | JWT/API |
| GET | `/api/links/{id}/stats?days=7` | Статистика кликов | JWT/API |
| PUT | `/api/links/{id}` | Обновить ссылку | JWT/API |
| DELETE | `/api/links/{id}` | Удалить ссылку | JWT/API |

Создание ссылки:
```bash
curl -X POST https://qntx.ru/api/links \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very-long-url", "slug": "my-link", "title": "Моя ссылка"}'
```

Ответ:
```json
{
  "id": 1,
  "slug": "my-link",
  "url": "https://example.com/very-long-url",
  "title": "Моя ссылка",
  "clicks": 0,
  "qr_code": "data:image/png;base64,...",
  "moderation_status": "ok"
}
```

### Payments

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| GET | `/api/payments/plans` | Список тарифов с ценами | — |
| POST | `/api/payments` | Создать платёж | JWT |
| GET | `/api/payments/{id}` | Статус платежа | JWT |
| GET | `/api/payments` | История платежей | JWT |
| GET | `/api/payments/subscription/current` | Текущая подписка | JWT |
| POST | `/api/payments/webhook/yookassa` | Webhook ЮKassa | — |
| POST | `/api/payments/webhook/yandex-pay` | Webhook Yandex Pay | — |

### Account (v1)

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| GET | `/api/v1/account` | Детали аккаунта | JWT |
| PUT | `/api/v1/account/email` | Сменить email | JWT |
| POST | `/api/v1/account/api-key` | Сгенерировать API ключ | JWT |
| DELETE | `/api/v1/account/api-key` | Отозвать API ключ | JWT |
| DELETE | `/api/v1/account` | Удалить аккаунт (GDPR) | JWT |

### Import / Export (v1)

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| POST | `/api/v1/import-export/import/csv` | Импорт из CSV файла | JWT |
| POST | `/api/v1/import-export/import/json` | Импорт из JSON файла | JWT |
| GET | `/api/v1/import-export/export/csv` | Экспорт всех ссылок в CSV | JWT |
| GET | `/api/v1/import-export/export/json` | Экспорт всех ссылок в JSON | JWT |

Формат CSV:
```csv
slug,url,title,description,tags
my-link,https://example.com,Пример,,example
```

Формат JSON:
```json
[
  {"url": "https://example.com", "slug": "my-link", "title": "Пример"}
]
```

### Promocodes (v1)

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| POST | `/api/v1/promocodes/redeem` | Активировать промокод | JWT |
| GET | `/api/v1/promocodes` | Список промокодов | Admin |
| POST | `/api/v1/promocodes` | Создать промокод | Admin |
| DELETE | `/api/v1/promocodes/{id}` | Удалить промокод | Admin |

### Admin

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| GET | `/api/admin/stats` | Статистика дашборда | Admin |
| GET | `/api/admin/users?page=&search=&plan=` | Список пользователей | Admin |
| GET | `/api/admin/users/{id}` | Детали пользователя | Admin |
| PUT | `/api/admin/users/{id}` | Обновить пользователя | Admin |
| DELETE | `/api/admin/users/{id}` | Удалить пользователя | Admin |
| GET | `/api/admin/payments?page=&status=` | Все платежи | Admin |
| GET | `/api/admin/links/moderation?mod_status=` | Ссылки для модерации | Admin |
| PUT | `/api/admin/links/{id}/ban` | Забанить ссылку | Admin |
| PUT | `/api/admin/links/{id}/unban` | Разбанить ссылку | Admin |
| POST | `/api/admin/links/{id}/recheck` | Перепроверить ссылку | Admin |
| GET | `/api/admin/settings/ads` | Настройки рекламы | Admin |
| PUT | `/api/admin/settings/ads` | Обновить настройки рекламы | Admin |

### System (v1)

| Method | Endpoint | Описание | Auth |
|--------|----------|----------|------|
| GET | `/api/v1/health` | Health check | — |
| GET | `/api/v1/info` | Информация о приложении | — |

---

## Тарифы

| | Free | Pro | Business |
|---|---|---|---|
| **Ссылок** | 50 | 1 000 | Безлимит |
| **Аналитика** | 7 дней | 30 дней | 365 дней |
| **QR-коды** | + | + | + |
| **Кастомные алиасы** | + | + | + |
| **Защита паролем** | — | + | + |
| **API доступ** | — | + | + |
| **Импорт/Экспорт** | — | + | + |
| **OG теги** | — | + | + |
| **Кастомные домены** | — | — | + |
| **Приоритетная поддержка** | — | — | + |
| **Без рекламы** | — | + | + |
| **Цена** | **0 руб** | **299 руб/мес** | **999 руб/мес** |

---

## Telegram бот

### Создание бота

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить `/newbot`
3. Ввести имя бота: `QNTX.Beacon`
4. Ввести username: `QNTXBeaconBot` (или доступный)
5. Скопировать токен
6. Добавить в `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   TELEGRAM_BOT_USERNAME=QNTXBeaconBot
   ```

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и инструкция |
| `/help` | Справка по командам |
| `/short URL [alias]` | Создать короткую ссылку |
| `/my` | Последние 10 ссылок |
| `/stats slug` | Статистика по ссылке |
| `/qr slug` | QR-код для ссылки |
| `/delete slug` | Удалить ссылку |
| `URL` (просто текст) | Автоматическое сокращение |

### Пример использования

```
Пользователь: https://github.com/fastapi/fastapi
Бот: ✅ Готово!
     🔗 https://qntx.ru/s/a3Bx9k
     📎 https://github.com/fastapi/fastapi
```

```
Пользователь: /short https://docs.python.org/3/ python-docs
Бот: ✅ Готово!
     🔗 https://qntx.ru/s/python-docs
     📎 https://docs.python.org/3/
```

### Особенности

- Бот автоматически создаёт пользователя при первом использовании
- Ссылки модерируются (фишинг, мальварь)
- Лимиты по тарифу применяются
- Поддержка Markdown форматирования

---

## Виджет для сайтов

### Подключение

Добавить одну строку на страницу:

```html
<script src="https://qntx.ru/static/widget/share.js" data-domain="qntx.ru"></script>
```

### Режимы отображения

#### 1. Плавающая кнопка (по умолчанию)

```html
<script src="https://qntx.ru/static/widget/share.js" data-domain="qntx.ru"></script>
```

Появится кнопка в правом нижнем углу. При клике открывается popup с короткой ссылкой и кнопками шаринга.

#### 2. Инлайн-виджет

```html
<div class="beacon-share" data-url="https://example.com/page" data-title="Заголовок"></div>
```

Встроенный блок с кнопками Telegram, VK, WhatsApp и копирования.

#### 3. Программный вызов

```javascript
// Показать popup для текущей страницы
BeaconShare.show();

// Показать popup для конкретного URL
BeaconShare.show('https://example.com', 'Мой заголовок');

// Получить короткую ссылку
BeaconShare.create('https://example.com').then(shortUrl => {
    console.log(shortUrl); // https://qntx.ru/s/abc123
});
```

### Опции

| Атрибут | Описание | По умолчанию |
|---------|----------|--------------|
| `data-domain` | Домен API | `qntx.ru` |
| `data-url` | URL для сокращения | текущий URL |
| `data-title` | Заголовок для шаринга | `document.title` |
| `data-theme` | Тема: `light`, `dark`, `auto` | `auto` |

### Сети

Виджет поддерживает шаринг в:
- Telegram
- VKontakte
- WhatsApp
- Копирование в буфер обмена

---

## Расширение для браузера

### Установка

1. Скачать папку `extension/` из репозитория
2. Открыть `chrome://extensions/` (или `edge://extensions/`)
3. Включить «Режим разработчика» (переключатель вверху справа)
4. Нажать «Загрузить распакованное расширение»
5. Выбрать папку `extension/`
6. Расширение появится в панели

### Использование

1. Нажать на иконку расширения на любой странице
2. Текущий URL автоматически подставится
3. (Опционально) Ввести кастомный алиас
4. Нажать «Сократить»
5. Короткая ссылка скопируется в буфер обмена

### Горячие клавиши

| Сочетание | Действие |
|-----------|----------|
| `Alt + S` | Сократить текущую страницу и скопировать |

### Настройки

В popup расширения есть секция «Настройки»:

| Поле | Описание |
|------|----------|
| API URL | URL вашего сервера (по умолчанию `https://qntx.ru`) |
| Токен | API ключ из личного кабинета |

### Файлы расширения

```
extension/
├── manifest.json     # Манифест расширения (Manifest V3)
├── popup.html        # Popup окно
├── popup.js          # Логика popup
├── background.js     # Service worker (горячие клавиши)
├── icon16.png        # Иконка 16x16
├── icon48.png        # Иконка 48x48
└── icon128.png       # Иконка 128x128
```

---

## Админ-панель

### Доступ

Администратор определяется по `ADMIN_EMAIL` в `.env`. При первом запуске создаётся аккаунт с ролью `admin`.

### Функции

#### Дашборд
- Общее количество пользователей
- Активные пользователи (верифицированные)
- Общее количество ссылок
- Общее количество кликов
- Ссылки и клики за сегодня
- Подозрительные / заблокированные ссылки

#### Управление пользователями
- Список всех пользователей с фильтрами (по тарифу, роли, поиску)
- Изменение тарифа, роли, статуса активности
- Удаление пользователя
- Просмотр деталей: ссылки, платежи, подписка

#### Модерация ссылок
- Список ссылок с фильтрами по статусу модерации
- Ручной бан / разбан ссылок
- Повторная проверка через Safe Browsing / VirusTotal
- Причина блокировки

#### Платежи
- Список всех платежей
- Фильтр по статусу (completed, pending, canceled)

#### Промокоды
- Создание промокодов с параметрами:
  - Код (4+ символов)
  - Тариф (pro / business)
  - Длительность (дней)
  - Лимит использований
  - Срок действия
- Список и удаление

#### Настройки рекламы
- Включение / выключение рекламы
- Задержка (1-30 секунд)
- Заголовок и текст кнопки
- Освобождённые тарифы
- HTML рекламного блока (iframe, AdSense, и т.д.)

---

## Модерация ссылок

При создании ссылки автоматически проверяется:

### 1. Встроенный чёрный список (~40 доменов)
- Фишинговые домены (login-microsoft, apple-id-verify, и т.д.)
- Мошеннические крипто-сайты
- Фейковые магазины
- Мальварь-хостинги

### 2. Regex-паттерны
- Phishing patterns (login.*google, wallet.*connect)
- Вложенные сокращалки (bit.ly, tinyurl.com)
- Скачивания мальвари

### 3. Google Safe Browsing API v4
- MALWARE
- SOCIAL_ENGINEERING
- UNWANTED_SOFTWARE
- POTENTIALLY_HARMFUL_APPLICATION

### 4. VirusTotal API (опционально)
- Проверка URL через 70+ антивирусных движков

### Статусы модерации

| Статус | Описание |
|--------|----------|
| `ok` | Ссылка безопасна |
| `pending` | На проверке |
| `blacklisted` | В чёрном списке |
| `phishing` | Фишинг |
| `malware` | Мальварь |
| `suspicious` | Подозрительная |
| `banned` | Заблокирована администратором |

При обнаружении угрозы ссылка автоматически деактивируется (если `AUTO_BAN_ON_DETECTION=true`).

---

## Реклама при переходе

При переходе по ссылке пользователей бесплатного тарифа может показываться рекламная страница с обратным отсчётом.

### Как работает

1. Пользователь переходит по ссылке `/s/{slug}`
2. Проверяется тариф владельца ссылки
3. Если тариф `free` — показывается рекламная страница
4. Обратный отсчёт (5-30 секунд)
5. Кнопка «Перейти» активируется
6. Через delay+3 сек — автоматический редирект

### Настройка в админке

- **Включена** — переключатель вкл/выкл
- **Задержка** — время ожидания (1-30 секунд)
- **Заголовок** — текст заголовка
- **Кнопка** — текст кнопки перехода
- **Освобождённые тарифы** — `pro,business` — без рекламы
- **HTML** — код рекламного блока (iframe, скрипт AdSense, и т.д.)

### Пример HTML рекламы

```html
<iframe src="https://ad.example.com/banner" width="300" height="250" frameborder="0"></iframe>
```

---

## Деплой

### Вариант 1: Docker (рекомендуется)

```bash
# Клонировать
git clone <repo> /opt/beacon
cd /opt/beacon

# Настроить
cp .env.example .env
nano .env  # Отредактировать настройки

# Запустить
docker-compose up -d

# Проверить
curl http://localhost:3333/api/v1/health
```

### Вариант 2: VPS (systemd)

```bash
# Установка
apt update && apt install python3-pip python3-venv nginx certbot python3-certbot-nginx
git clone <repo> /opt/beacon
cd /opt/beacon
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Systemd service
cat > /etc/systemd/system/beacon.service << 'EOF'
[Unit]
Description=QNTX.Beacon URL Shortener
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/beacon
ExecStart=/opt/beacon/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 3333 --workers 4
Restart=always
RestartSec=5
EnvironmentFile=/opt/beacon/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now beacon
```

### Nginx конфигурация

```nginx
server {
    listen 80;
    server_name qntx.ru www.qntx.ru;

    # HTTPS redirect
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name qntx.ru www.qntx.ru;

    ssl_certificate /etc/letsencrypt/live/qntx.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/qntx.ru/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Proxy to app
    location / {
        proxy_pass http://127.0.0.1:3333;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Static files (cache)
    location /static/ {
        alias /opt/beacon/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Widget (CORS)
    location /static/widget/ {
        alias /opt/beacon/static/widget/;
        add_header Access-Control-Allow-Origin *;
        expires 7d;
    }
}
```

### SSL сертификат

```bash
certbot --nginx -d qntx.ru -d www.qntx.ru
```

### Обновление

```bash
cd /opt/beacon
git pull
source venv/bin/activate
pip install -r requirements.txt
systemctl restart beacon
```

---

## Структура проекта

```
beaconqntx/
├── main.py                          # Точка входа
├── .env                             # Конфигурация
├── requirements.txt                 # Зависимости Python
├── Dockerfile                       # Docker образ
├── docker-compose.yml               # App + PostgreSQL + Redis
├── .dockerignore                    # Исключения для Docker
├── README.md                        # Документация
│
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI приложение, lifespan, middleware
│   ├── dependencies.py              # DI: get_db, get_current_user, require_admin
│   ├── tasks.py                     # Background tasks (cleanup, subscriptions)
│   │
│   ├── core/
│   │   ├── config.py                # Все настройки из .env
│   │   ├── database.py              # DDL, подключение, миграции
│   │   ├── security.py              # JWT, bcrypt, SSRF, API ключи
│   │   ├── logging.py               # Structured JSON logging
│   │   └── rate_limiter.py          # Redis / in-memory rate limiter
│   │
│   ├── models/
│   │   └── schemas.py               # Pydantic модели запросов/ответов
│   │
│   ├── routers/
│   │   ├── auth.py                  # POST /api/auth/* — регистрация, логин
│   │   ├── links.py                 # CRUD /api/links/*
│   │   ├── payments.py              # POST /api/payments/* — ЮKassa, Yandex Pay
│   │   ├── admin.py                 # GET/PUT/DELETE /api/admin/*
│   │   ├── health.py                # GET /api/v1/health
│   │   ├── account.py               # /api/v1/account/* — email, api-key, удаление
│   │   ├── import_export.py         # /api/v1/import-export/* — CSV, JSON
│   │   ├── promocodes.py            # /api/v1/promocodes/*
│   │   └── settings.py              # /api/admin/settings/ads
│   │
│   ├── services/
│   │   ├── auth_service.py          # Логика авторизации
│   │   ├── link_service.py          # CRUD ссылок, QR
│   │   ├── link_checker.py          # Модерация: blacklist, Safe Browsing
│   │   ├── payment_service.py       # ЮKassa, Yandex Pay, webhooks
│   │   ├── admin_service.py         # Статистика, управление
│   │   └── ad_service.py            # Настройки рекламы
│   │
│   └── bot/
│       └── telegram_bot.py          # Telegram бот
│
├── utils/
│   ├── email_service.py             # SMTP email (подтверждение, сброс)
│   ├── qr_generator.py              # Генерация QR-кодов
│   └── analytics.py                 # Обработка кликов, user-agent
│
├── static/
│   ├── index.html                   # SPA фронтенд
│   ├── app.js                       # JavaScript
│   ├── style.css                    # Стили
│   ├── manifest.json                # PWA manifest
│   └── widget/
│       └── share.js                 # Виджет для встраивания
│
└── extension/
    ├── manifest.json                # Chrome Extension Manifest V3
    ├── popup.html                   # Popup окно
    ├── popup.js                     # Логика popup
    ├── background.js                # Service worker
    ├── icon16.png                   # Иконки
    ├── icon48.png
    └── icon128.png
```

---

## Требования

### Минимальные
- Python 3.10+
- 512 MB RAM
- 1 GB диска

### Рекомендуемые (продакшен)
- Python 3.12
- 2 GB RAM
- 10 GB диска
- PostgreSQL 16
- Redis 7

### Зависимости Python

**Обязательные:**
- `fastapi` — веб-фреймворк
- `uvicorn` — ASGI сервер
- `aiosqlite` — асинхронный SQLite
- `pydantic` — валидация данных
- `python-jose` — JWT токены
- `bcrypt` — хеширование паролей
- `qrcode` — генерация QR-кодов
- `user-agents` — парсинг User-Agent
- `yookassa` — интеграция ЮKassa

**Опциональные:**
- `redis` — Redis rate limiter
- `asyncpg` + `sqlalchemy` — PostgreSQL
- `sentry-sdk` — мониторинг ошибок
- `python-telegram-bot` — Telegram бот
- `geoip2` — геолокация по IP
