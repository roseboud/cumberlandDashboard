# Cumberland Flood Dashboard — Hosting Guide

How to deploy this dashboard live on the web so anyone can access it.

---

## Quick Comparison

| Method | Cost | Difficulty | Best For |
|--------|------|------------|----------|
| **GitHub Pages** | Free | Easy | Student projects, demos |
| **Netlify** | Free | Easy | Professional deploys with custom domain |
| **Vercel** | Free | Easy | Similar to Netlify |
| **Azure Static Web Apps** | Free tier | Medium | Microsoft ecosystem, NSCC Azure credits |
| **AWS S3 + CloudFront** | ~$1/month | Medium | Enterprise-grade, scalable |
| **Traditional Web Host** | $5-15/month | Easy | Full control, cPanel |

---

## Option 1: GitHub Pages (Recommended — Free & Easiest)

GitHub Pages serves static HTML directly from your repository. Since our dashboard is pure HTML/CSS/JS with no build step, this is the simplest option.

### Steps

1. **Push your code to GitHub** (if not already):
   ```bash
   cd cumberlandDashboard
   git add .
   git commit -m "Upgrade: professional UI, real flood data, OSM integration"
   git push origin main
   ```

2. **Enable GitHub Pages:**
   - Go to your repo on GitHub: `https://github.com/roseboud/cumberlandDashboard`
   - Click **Settings** (tab at the top)
   - Scroll to **Pages** in the left sidebar
   - Under **Source**, select **Deploy from a branch**
   - Select **main** branch and **/ (root)** folder
   - Click **Save**

3. **Wait 1-2 minutes**, then visit:
   ```
   https://roseboud.github.io/cumberlandDashboard/
   ```

### Important: File Structure Fix for GitHub Pages

GitHub Pages serves from the repo root. Since our `index.html` is inside the `cumberlandDashboard/` subfolder, you have two options:

**Option A — Set the subfolder as the source:**
- In Settings → Pages → Source, change the folder from `/ (root)` to `/cumberlandDashboard` (if GitHub allows it)

**Option B — Move files to repo root (recommended):**
```bash
# From the repo root
cp -r cumberlandDashboard/* .
git add .
git commit -m "Move files to root for GitHub Pages"
git push
```

**Option C — Use a GitHub Actions workflow:**
Create `.github/workflows/deploy.yml`:
```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: cumberlandDashboard
      - uses: actions/deploy-pages@v4
```

### Pros & Cons
- Free forever, automatic HTTPS
- Custom domain supported (free)
- Auto-deploys when you push to main
- No server to manage
- Limited to static files (which is all we need)

---

## Option 2: Netlify (Free — Best for Custom Domains)

Netlify is a popular static hosting service with a generous free tier.

### Steps

1. Go to [netlify.com](https://www.netlify.com/) and sign up with your GitHub account.

2. Click **"Add new site"** → **"Import an existing project"**

3. Connect your GitHub repo (`roseboud/cumberlandDashboard`)

4. Configure the build:
   - **Base directory:** `cumberlandDashboard`
   - **Build command:** *(leave empty — no build step needed)*
   - **Publish directory:** `cumberlandDashboard`

5. Click **Deploy site**

6. Your site will be live at something like: `https://random-name-12345.netlify.app`

7. (Optional) Click **Domain settings** to set a custom domain or rename the subdomain

### Custom Domain Setup
- Go to **Domain management** → **Add custom domain**
- Point your DNS with a CNAME record to Netlify
- Netlify provides free HTTPS via Let's Encrypt

### Pros & Cons
- Free tier: 100GB bandwidth/month (more than enough)
- Automatic deploys from GitHub
- Easy custom domain + free HTTPS
- Deploy previews for pull requests
- Form handling, serverless functions available

---

## Option 3: Vercel (Free — Similar to Netlify)

### Steps

1. Go to [vercel.com](https://vercel.com/) and sign up with GitHub.
2. Import your repository.
3. Set **Root Directory** to `cumberlandDashboard`.
4. Deploy — no build command needed.
5. Live at `https://your-project.vercel.app`

---

## Option 4: Azure Static Web Apps (Free Tier)

Good option if you have NSCC Azure student credits or want Microsoft ecosystem.

### Steps

1. Install Azure CLI: [docs.microsoft.com/cli/azure/install](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)

2. Login:
   ```bash
   az login
   ```

3. Create a Static Web App:
   ```bash
   az staticwebapp create \
     --name cumberland-flood-dashboard \
     --resource-group myResourceGroup \
     --source https://github.com/roseboud/cumberlandDashboard \
     --branch main \
     --app-location "/cumberlandDashboard" \
     --output-location "" \
     --login-with-github
   ```

4. Your site deploys automatically. Find the URL in the Azure Portal.

### Pros & Cons
- Free tier: 100GB bandwidth/month
- Custom domains + free HTTPS
- Staging environments
- Authentication built-in (if needed later)
- Good for Azure-integrated projects

---

## Option 5: AWS S3 + CloudFront

Enterprise-grade hosting for when the municipality wants a production deployment.

### Steps

1. **Create an S3 bucket:**
   ```bash
   aws s3 mb s3://cumberland-flood-dashboard --region ca-central-1
   ```

2. **Enable static website hosting:**
   ```bash
   aws s3 website s3://cumberland-flood-dashboard \
     --index-document index.html
   ```

3. **Upload files:**
   ```bash
   cd cumberlandDashboard
   aws s3 sync . s3://cumberland-flood-dashboard --delete
   ```

4. **Set bucket policy for public access** (create `policy.json`):
   ```json
   {
     "Statement": [{
       "Effect": "Allow",
       "Principal": "*",
       "Action": "s3:GetObject",
       "Resource": "arn:aws:s3:::cumberland-flood-dashboard/*"
     }]
   }
   ```
   ```bash
   aws s3api put-bucket-policy --bucket cumberland-flood-dashboard --policy file://policy.json
   ```

5. **(Optional) Add CloudFront CDN** for HTTPS and caching:
   ```bash
   aws cloudfront create-distribution \
     --origin-domain-name cumberland-flood-dashboard.s3-website.ca-central-1.amazonaws.com
   ```

### Pros & Cons
- Extremely reliable and scalable
- ~$0.50-1.00/month for low traffic
- CloudFront CDN for fast global delivery
- Custom domain + HTTPS
- More setup required

---

## Performance Considerations

The GeoJSON flood files range from 162 KB (0m) to 6.8 MB (10m, 11m). For production:

### 1. Enable Gzip/Brotli Compression
All hosting platforms above support automatic compression. GeoJSON compresses extremely well:
- 6.8 MB file → ~800 KB compressed (88% reduction)
- GitHub Pages, Netlify, and Vercel do this automatically

### 2. Consider Splitting Large Files
If the 10m and 11m files cause slow loading, you can:
- Increase the simplification tolerance in `convert_shapefiles.py` (change `0.00005` to `0.0001`)
- Re-run: `python convert_shapefiles.py`

### 3. Add a Service Worker (Advanced)
For offline capability, you could add a service worker to cache the GeoJSON files after first load.

---

## CORS Note

The tide data comes from `api-iwls.dfo-mpo.gc.ca`. This API works from any hosted domain (it has permissive CORS headers). However:
- It does **NOT** work from `file:///` (opening HTML directly)
- It **DOES** work from `http://localhost:*`, GitHub Pages, Netlify, etc.

---

## Recommended Approach for This Project

**For the Capstone presentation:** Use **GitHub Pages** — it's free, takes 5 minutes, and auto-deploys from your existing repo.

**For handing off to the municipality:** Use **Netlify** or **Azure Static Web Apps** — they offer custom domains (e.g., `floods.cumberlandcounty.ns.ca`), HTTPS, and professional-grade reliability.

### Quick Deploy Checklist

1. Ensure all files are committed and pushed to GitHub
2. Enable GitHub Pages (Settings → Pages → main branch)
3. Wait 2 minutes
4. Share the URL: `https://roseboud.github.io/cumberlandDashboard/`
5. Done!

---

*Last updated: February 15, 2026*
