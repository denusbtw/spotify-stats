# 🎵 Spotify Stats

Веб-додаток для аналізу персональних даних прослуховувань Spotify з красивою візуалізацією та детальною статистикою.
<img width="1884" height="1019" alt="image" src="https://github.com/user-attachments/assets/fc91d292-8bd6-45ab-ba56-d2155c2ca445" />


## ✨ Особливості

- 📊 **Детальна аналітика** - статистика треків, артистів, жанрів та активності
- 📈 **Візуалізація даних** - інтерактивні графіки та діаграми
- 🔄 **Асинхронна обробка** - швидка обробка великих обсягів даних
- 🎯 **Оптимізовані запити** - ефективна робота з базою даних
- 🔗 **Spotify API інтеграція** - автоматичне отримання метаданих треків
- 📱 **Адаптивний дизайн** - працює на всіх пристроях
- 🌙 **Темна тема** - стильний Spotify-подібний інтерфейс

## 📊 Аналітика

### Загальна статистика
<img width="1893" height="82" alt="image" src="https://github.com/user-attachments/assets/f1412387-9eef-4955-9891-420a919d4496" />

- Загальна кількість треків
- Загальний час прослуховування  
- Кількість унікальних артистів
- Кількість улюблених треків
- Кількість улюблених альбомів

### Детальна аналітика
- **Активність по роках** - графік динаміки прослуховувань
<img width="1898" height="1013" alt="image" src="https://github.com/user-attachments/assets/f2c6e0ec-9809-4693-b82e-80cba2049b1f" />


<img width="1885" height="1011" alt="image" src="https://github.com/user-attachments/assets/4b967ba0-862c-46d4-b7ae-b42230f818ee" />
- **Топ жанри** - розподіл по музичних стилях
- **Топ 5 треків** - найбільш прослуховувані композиції
- **Топ 5 артистів** - улюблені виконавці
- **Часова активність** - паттерни прослуховування

### Топ виконавців
<img width="1885" height="1016" alt="image" src="https://github.com/user-attachments/assets/058a4d3d-1def-4ef9-b0a5-4eb06f073ec0" />


### Топ пісень
<img width="1882" height="1015" alt="image" src="https://github.com/user-attachments/assets/864ae3f9-fdfc-42e9-b748-73403552ff2e" />


## 🛠️ Технології

### Backend
- **Django 5.2+** - веб-фреймворк
- **Django REST Framework** - API
- **PostgreSQL** - база даних
- **Celery** - асинхронна обробка задач
- **Celery Beat** - планувальник задач
- **Redis** - брокер повідомлень та кеш
- **Cloudflare R2** - хмарне сховище
- **Spotify Oauth** - вхід через Spotify

### Frontend
- **React** - інтерфейс користувача
- **Chart.js** - візуалізація даних
- **Responsive design** - адаптивність

### DevOps
- **Docker** - контейнеризація
- **Docker Compose** - оркестрація сервісів

## 🚀 Встановлення

### Передумови
- Python 3.11+
- Docker та Docker Compose
- Git

### Клонування репозиторію
```bash
git clone https://github.com/denusbtw/spotify-stats.git
cd spotify-stats
```

### Налаштування змінних середовища
```bash
cp .env.example .env
```

Відредагуйте `.env` файл:
```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True

DATABASE_URL=postgresql://username:password@db:5432/db_name
POSTGRES_DB=db_name
POSTGRES_USER=username
POSTGRES_PASSWORD=password

REDIS_URL=redis://redis:6379/0
ALLOWED_HOSTS=your-frontend-host

CLOUDFLARE_R2_BUCKET=your-bucket-name
CLOUDFLARE_R2_ACCESS_KEY=your-access-key
CLOUDFLARE_R2_SECRET_KEY=your-secret-key
CLOUDFLARE_R2_BUCKET_ENDPOINT=your-bucket-endpoint

SPOTIFY_CLIENT_ID=your-client-id
SPOTIFY_CLIENT_SECRET=your-client-secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5173/spotify/callback (change to your URL)

```

### Запуск через Docker
```bash
docker-compose up --build -d
```

### Або локальний запуск
```bash
# Встановлення залежностей
pip install -r requirements.txt

# Міграції
python3 manage.py migrate

# Створення суперкористувача
python3 manage.py createsuperuser

# Запуск сервера
python3 manage.py runserver

# В окремих терміналах:
celery -A spotify_stats worker --loglevel=info
celery -A spotify_stats beat --loglevel=info
```

## 📱 Використання

1. **Отримайте дані зі Spotify:**
   - Перейдіть на [Spotify Privacy Settings](https://www.spotify.com/account/privacy/)
   - Запросіть "Extended streaming history"
   - Дочекайтесь email з архівом (до 30 днів)

2. **Завантажте дані:**
   - Зареєструйтеся в додатку
   - Завантажте JSON файли через API або веб-інтерфейс
   - Дочекайтесь обробки даних

3. **Переглядайте аналітику:**
   - Відкрийте дашборд
   - Досліджуйте різні секції статистики
   - Фільтруйте дані за періодами

## 🔌 API Endpoints

### Аутентифікація
```
POST /api/token/                 # Отримання JWT токена
POST /api/token/refresh/         # Оновлення токена  
POST /api/token/verify/          # Верифікація токена
```

### Користувач
```
GET    /api/v1/me/               # Профіль користувача
PUT    /api/v1/me/               # Оновлення профілю
PATCH  /api/v1/me/               # Часткове оновлення
DELETE /api/v1/me/               # Видалення акаунту
```

### Аналітика
```
GET /api/v1/me/analytics/activity/     # Активність по періодах
GET /api/v1/me/analytics/stats/        # Загальна статистика
GET /api/v1/me/analytics/top-albums/   # Топ альбоми
GET /api/v1/me/analytics/top-artists/  # Топ артисти
GET /api/v1/me/analytics/top-tracks/   # Топ треки
```

### Завантаження
```
GET  /api/v1/me/uploads/         # Список завантажень
POST /api/v1/me/uploads/         # Завантаження файлу
```

### Spotify Integration
```
GET /api/v1/spotify/login/       # OAuth авторизація
GET /api/v1/spotify/callback/    # OAuth callback
```

## 🏗️ Архітектура

```
├── config/                # Django проект
│   ├── settings/          # Налаштування
│   ├── urls.py            # URL роутинг
│   └── wsgi.py            # WSGI конфігурація
├── spotify_stats/         # Django додатки
│   ├── users/             # Користувачі
│   ├── analytics/         # Аналітика
│   ├── catalog/           # Пісні, альбоми, виконавці
│   └── api/               # API
├── static/                # Статичні файли
├── templates/             # HTML шаблони
├── docker-compose.yml     # Docker конфігурація
├── Dockerfile            # Docker образ
└── requirements.txt      # Python залежності
```

## ⚡ Оптимізації

- **Database indexing** - індекси для швидких запитів
- **Query optimization** - select_related, prefetch_related
- **Caching** - Redis кешування для статистики
- **Async processing** - Celery для важких обчислень
- **Batch operations** - групова обробка даних
- **File upload to Cloudflare R2** - безпечне зберігання в хмарі
- **OAuth token management** - автоматичне оновлення токенів

## 🧪 Тестування

```bash
# Запуск всіх тестів
docker compose exec web python3 manage.py test

# З покриттям коду
coverage run --source='.' manage.py test
coverage report
coverage html
```

- [Spotify Web API](https://developer.spotify.com/documentation/web-api/) - за можливість отримання метаданих
- [Chart.js](https://www.chartjs.org/) - за красиві графіки
- [Django](https://www.djangoproject.com/) - за потужний фреймворк
