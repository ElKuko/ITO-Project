# Deployment Guide: Ito Merchandising App

This guide walks you through deploying the app to Railway (hosting) and Cloudflare R2 (image storage).

**Estimated setup time: 30 minutes**

---

## Prerequisites

- GitHub account (you already have this)
- Credit card for Railway ($5/month after free trial)
- Credit card for Cloudflare (free tier, card for verification only)

---

## Part 1: Set Up Cloudflare R2 (Image Storage)

### Step 1.1: Create Cloudflare Account
1. Go to [cloudflare.com](https://cloudflare.com) and sign up
2. Verify your email

### Step 1.2: Create R2 Bucket
1. In Cloudflare dashboard, click **R2** in the left sidebar
2. Click **Create bucket**
3. Name it: `ito-uploads`
4. Click **Create bucket**

### Step 1.3: Make Bucket Public (for image viewing)
1. Click on your `ito-uploads` bucket
2. Go to **Settings** tab
3. Under **Public access**, click **Allow Access**
4. Copy the **Public bucket URL** (looks like: `https://pub-xxxxx.r2.dev`)
5. Save this URL - you'll need it later as `R2_PUBLIC_URL`

### Step 1.4: Create API Token
1. Go to **R2** > **Overview**
2. Click **Manage R2 API Tokens**
3. Click **Create API token**
4. Settings:
   - Token name: `ito-app`
   - Permissions: **Object Read & Write**
   - Specify bucket: `ito-uploads`
5. Click **Create API Token**
6. **SAVE THESE VALUES** (shown only once):
   - Access Key ID → `R2_ACCESS_KEY_ID`
   - Secret Access Key → `R2_SECRET_ACCESS_KEY`

### Step 1.5: Get Account ID
1. Go to any page in Cloudflare dashboard
2. Look at the URL: `https://dash.cloudflare.com/XXXXXXX/...`
3. The `XXXXXXX` is your Account ID → `R2_ACCOUNT_ID`

---

## Part 2: Deploy to Railway

### Step 2.1: Create Railway Account
1. Go to [railway.app](https://railway.app)
2. Click **Login** → **Login with GitHub**
3. Authorize Railway

### Step 2.2: Create New Project
1. Click **New Project**
2. Select **Deploy from GitHub repo**
3. Find and select `ITO-Project`
4. Click **Deploy Now**

### Step 2.3: Add PostgreSQL Database
1. In your project, click **+ New**
2. Select **Database** → **Add PostgreSQL**
3. Railway automatically creates `DATABASE_URL` variable

### Step 2.4: Set Environment Variables
1. Click on your app service (not the database)
2. Go to **Variables** tab
3. Click **+ New Variable** and add each:

```
SECRET_KEY=<generate-a-random-string-here>
R2_ACCOUNT_ID=<from step 1.5>
R2_ACCESS_KEY_ID=<from step 1.4>
R2_SECRET_ACCESS_KEY=<from step 1.4>
R2_BUCKET_NAME=ito-uploads
R2_PUBLIC_URL=<from step 1.3>
```

**To generate SECRET_KEY**, run this in terminal:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Step 2.5: Deploy
1. Railway auto-deploys when you add variables
2. Wait for deployment to complete (watch the logs)
3. Click **Settings** → find your app URL (e.g., `ito-project-production.up.railway.app`)

### Step 2.6: (Optional) Custom Domain
1. Go to **Settings** → **Domains**
2. Click **+ Custom Domain**
3. Enter your domain (e.g., `app.ito-pr.com`)
4. Add the CNAME record to your DNS provider

---

## Part 3: Test Your Deployment

1. Open your Railway URL in a browser
2. Log in with: `admin` / `admin123`
3. Try uploading a photo in a visit
4. Verify the image loads (should come from R2)

---

## Part 4: Install as Mobile App (PWA)

### On iPhone:
1. Open your app URL in Safari
2. Tap the **Share** button (square with arrow)
3. Scroll down and tap **Add to Home Screen**
4. Tap **Add**

### On Android:
1. Open your app URL in Chrome
2. Tap the **three dots** menu
3. Tap **Add to Home Screen** or **Install App**
4. Tap **Add**

The app will now appear on the home screen and work like a native app!

---

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Auto-set by Railway |
| `SECRET_KEY` | JWT signing key (random string) | Yes |
| `R2_ACCOUNT_ID` | Cloudflare account ID | Yes |
| `R2_ACCESS_KEY_ID` | R2 API access key | Yes |
| `R2_SECRET_ACCESS_KEY` | R2 API secret key | Yes |
| `R2_BUCKET_NAME` | R2 bucket name | Yes |
| `R2_PUBLIC_URL` | Public URL for the R2 bucket | Yes |

---

## Estimated Monthly Costs

| Service | Cost |
|---------|------|
| Railway (compute + database) | $5-10/month |
| Cloudflare R2 (storage) | $0-3/month |
| **Total** | **$5-15/month** |

---

## Troubleshooting

### App won't start
- Check Railway logs for errors
- Verify all environment variables are set
- Make sure `DATABASE_URL` exists (from PostgreSQL service)

### Images not loading
- Verify R2 bucket is set to public access
- Check that `R2_PUBLIC_URL` is correct
- Verify API token has read/write permissions

### Database errors
- Railway provides `DATABASE_URL` automatically when you add PostgreSQL
- Make sure the app service can see the database variable

---

## Updating the App

Just push to GitHub:
```bash
git add .
git commit -m "Your changes"
git push origin main
```

Railway automatically deploys within 2 minutes.
