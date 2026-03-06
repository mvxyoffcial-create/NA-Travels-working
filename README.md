# 🌍 Tourist App Backend

A production-ready Python/FastAPI backend for a tourist website with MongoDB, JWT auth, Google OAuth, email verification, and review/photo system.

---

## 🚀 Features

- **Email + Password Signup** with email verification
- **Google OAuth** login (verify ID token from frontend)
- **JWT Authentication** (access + refresh tokens)
- **Password Reset** via email with expiring tokens
- **User Profiles** with avatar upload
- **Tourist Destinations** CRUD (admin-managed)
- **Reviews System** — write, edit, delete, mark helpful
- **Photo Uploads** — up to 5 photos per review + destination gallery
- **CORS** configured for frontend domains
- **Rate limiting ready** (add slowapi if needed)
- **MongoDB** with indexed collections
- **Docker + Koyeb** ready

---

## 📁 Project Structure

```
tourist-backend/
├── app/
│   ├── main.py              # FastAPI app + CORS + middleware
│   ├── core/
│   │   ├── config.py        # Settings from environment
│   │   ├── database.py      # MongoDB connection + indexes
│   │   └── security.py      # JWT + password hashing
│   ├── routers/
│   │   ├── auth.py          # Signup, login, Google, verify, reset
│   │   ├── users.py         # Profile, avatar
│   │   ├── destinations.py  # Tourist spots CRUD
│   │   └── reviews.py       # Reviews + photo uploads
│   ├── schemas/
│   │   └── schemas.py       # Pydantic request/response models
│   └── utils/
│       ├── dependencies.py  # Auth dependencies
│       ├── email.py         # Email sending (SMTP)
│       └── files.py         # Image upload + resize
├── uploads/                 # Uploaded files (gitignored)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Procfile                 # Koyeb/Heroku
├── koyeb.yaml
└── .env.example
```

---

## ⚙️ Setup

### 1. Clone & install

```bash
git clone https://github.com/your-user/tourist-backend
cd tourist-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

Key variables:
| Variable | Description |
|---|---|
| `MONGODB_URL` | MongoDB Atlas connection string |
| `SECRET_KEY` | JWT secret (min 32 chars, random) |
| `SMTP_*` | Gmail SMTP credentials |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `FRONTEND_URL` | Your frontend URL for CORS + email links |

### 3. Run locally

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`  
Swagger docs at `http://localhost:8000/docs`

---

## 🐳 Docker

```bash
docker-compose up --build
```

---

## ☁️ Deploy to Koyeb

1. Push to GitHub
2. Create a Koyeb account at [koyeb.com](https://koyeb.com)
3. New Service → GitHub → select your repo
4. Build command: `pip install -r requirements.txt`
5. Run command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
6. Add all environment variables from `.env.example`
7. Set port to `8000`
8. Deploy!

For persistent uploads, mount a Koyeb volume at `/app/uploads` or use S3/Cloudflare R2.

---

## 📡 API Endpoints

### Auth (`/api/v1/auth`)
| Method | Path | Description |
|---|---|---|
| POST | `/signup` | Register with email + password |
| GET | `/verify-email?token=...` | Verify email |
| POST | `/resend-verification` | Resend verification email |
| POST | `/login` | Login → access + refresh tokens |
| POST | `/google` | Login with Google ID token |
| POST | `/refresh` | Refresh access token |
| POST | `/forgot-password` | Send password reset email |
| POST | `/reset-password` | Reset with token |
| POST | `/change-password` | Change password (authenticated) |
| GET | `/me` | Get current user |

### Users (`/api/v1/users`)
| Method | Path | Description |
|---|---|---|
| GET | `/{user_id}` | Public profile |
| PUT | `/me/profile` | Update profile |
| POST | `/me/avatar` | Upload avatar |
| GET | `/{user_id}/reviews` | User's reviews |

### Destinations (`/api/v1/destinations`)
| Method | Path | Description |
|---|---|---|
| GET | `/` | List (filter, search, paginate) |
| GET | `/featured` | Featured destinations |
| GET | `/slug/{slug}` | Get by slug |
| GET | `/{id}` | Get by ID |
| POST | `/` | Create (admin) |
| PUT | `/{id}` | Update (admin) |
| POST | `/{id}/photos` | Upload photo (admin) |
| DELETE | `/{id}` | Deactivate (admin) |
| GET | `/meta/countries` | All countries |
| GET | `/meta/categories` | All categories |

### Reviews (`/api/v1/reviews`)
| Method | Path | Description |
|---|---|---|
| GET | `/destination/{dest_id}` | List reviews for destination |
| POST | `/` | Create review (verified user) |
| POST | `/{id}/photos` | Upload photos (up to 5) |
| PUT | `/{id}` | Edit your review |
| DELETE | `/{id}` | Delete your review |
| DELETE | `/{id}/photos` | Remove a photo |
| POST | `/{id}/helpful` | Toggle helpful |
| GET | `/{id}` | Get single review |

---

## 🔑 Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

Get tokens from `/api/v1/auth/login` or `/api/v1/auth/google`.

---

## 📧 Email Setup (Gmail)

1. Enable 2FA on your Gmail account
2. Generate an "App Password" at myaccount.google.com/apppasswords
3. Use that as `SMTP_PASSWORD` in `.env`

---

## 🔐 Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable Google+ API
3. Create OAuth 2.0 credentials (Web application)
4. Add your frontend URL to authorized origins
5. Copy Client ID → `GOOGLE_CLIENT_ID` in `.env`

Frontend sends the Google `credential` (ID token) to `/api/v1/auth/google`.

---

## 📸 File Uploads

- Images are resized to max 1920px and converted to JPEG
- Served at `/uploads/<path>`
- Max size: 10MB per file (configurable)
- For production, replace local storage with S3/R2
