# Windows 11 setup guide (no programming knowledge needed)

You will do three things: **(A)** start the server on your laptop, **(B)** connect Firebase so phones get push alerts, **(C)** build the Android app and install it on your phone.
Allow about 1–2 hours the first time. Copy commands exactly. If something fails, read the "Problems" section at the end.

> **Important:** the server must be switched on to collect jobs. Your laptop is fine for testing, but for real "never miss a notification" use you need it running 24 hours (a cheap cloud server; see Part D).

---
## Part A – Start the server (backend + database + admin dashboard)

1. **Turn on virtualization** (usually already on). Press Ctrl+Shift+Esc → *Performance* → *CPU* → check "Virtualization: Enabled". If Disabled, enable it in your laptop's BIOS (search "<your laptop model> enable virtualization").
2. **Install Docker Desktop**: go to https://www.docker.com/products/docker-desktop → *Download for Windows* → install with default options (keep "Use WSL 2" ticked) → restart Windows → open Docker Desktop and wait until it says *Engine running*.
3. **Unzip** `GovJobsTracker.zip` to `C:\GovJobsTracker` (right-click → Extract All).
4. **Create your settings file**: open `C:\GovJobsTracker\backend`, copy `.env.example`, and rename the copy to `.env` (if you cannot see the extension, in File Explorer choose *View → Show → File name extensions*). Open `.env` with Notepad and set:
   * `ADMIN_API_KEY=` a long password you invent (this is your admin login)
   * `TOKEN_SECRET=` another long random text (e.g. 40 random letters/numbers)
   * `USER_AGENT=GovJobsTracker/1.0 (contact: your-real-email@example.com)`
   Save. **Never share this file.**
5. **Start everything**: open the Start menu → type `cmd` → Enter. Then:
   ```
   cd C:\GovJobsTracker
   docker compose up --build
   ```
   The first time it downloads things (5–15 minutes). Wait until you see lines like `Uvicorn running on http://0.0.0.0:8000` and `registry: 222 organizations`. Leave this window open. (To stop: Ctrl+C. To start later in the background: `docker compose up -d`.)
6. **Open the admin dashboard**: browser → http://localhost:8000/admin-ui → paste your `ADMIN_API_KEY` → *Sign in*.
   * **Health** tab: shows how many sources are monitored / pending / unavailable.
   * **Sources** tab: ~222 official organizations are pre-loaded as *pending*. The worker visits each home page automatically (every 60 min). Click **Check now** on a source to test it. A source becomes **monitored** only after it really finds notification links. If it says "no notification links recognised", open the real recruitment/notifications page of that website, copy its address, click **Edit**, paste the address (and, if you can, a CSS selector) → *Check now* again. The *Preview links* box under "Add a source" shows what would be collected before you commit.
   * Sources that block robots (CAPTCHA / 403) are put in **manual verification**; the app shows them honestly as not auto-monitored.
7. **Windows Firewall** (so your phone can reach the laptop): in `cmd` (run as Administrator):
   ```
   netsh advfirewall firewall add rule name="GovJobs API" dir=in action=allow protocol=TCP localport=8000
   ```
   Find your laptop's address: `ipconfig` → "IPv4 Address", e.g. `192.168.1.10`. Your phone must be on the same Wi-Fi. Test on the phone's browser: `http://192.168.1.10:8000/health` should show `{"ok":true}`.

## Part B – Firebase push notifications (free)
1. Go to https://console.firebase.google.com → *Add project* → name it (e.g. GovJobsTracker) → create.
2. *Project settings* (gear) → **Cloud Messaging** must be enabled (it is by default).
3. **For the phone app**: *Project settings → General → Your apps → Android icon*. Package name: `app.govjobs.tracker` → *Register app* → **Download `google-services.json`** → put it in `C:\GovJobsTracker\android\app\` (next to `build.gradle.kts`).
4. **For the server**: *Project settings → Service accounts → Generate new private key* → save the file as `C:\GovJobsTracker\secrets\firebase.json`.
5. Restart the server: in `cmd`: `docker compose down` then `docker compose up -d`. The dashboard Health tab should now say *Firebase configured: Yes*.

## Part C – Build the Android app and install it
1. **Install Android Studio**: https://developer.android.com/studio → install with defaults. On first start let it download the SDK ("Standard" setup).
2. **Set the server address**: open `C:\GovJobsTracker\android\gradle.properties` in Notepad and change the last line to your laptop address, e.g. `backendUrl=http://192.168.1.10:8000` (you can also change it later inside the app: *More → Settings*).
3. Android Studio → *Open* → choose the folder `C:\GovJobsTracker\android` → wait for "Gradle sync" to finish (first time 5–10 min, needs internet). If it asks to *trust the project* → Trust. If it suggests a Gradle/AGP upgrade, you may decline.
4. **Build the APK**: menu *Build → Build Bundle(s) / APK(s) → Build APK(s)*. When finished click *locate*. The file is `android\app\build\outputs\apk\debug\app-debug.apk`.
5. **Install on your phone**: copy the APK to the phone (USB cable or WhatsApp/Telegram "saved messages"/Google Drive) → tap it → allow "Install unknown apps" for that app → Install. Or: enable *Developer options → USB debugging*, plug in the phone, and press the green ▶ Run button in Android Studio.
6. Open the app → allow notifications → *More → Settings* → switch on **All Government Job Alerts** (or choose subscriptions) → *Save*.

> The debug APK talks to `http://` addresses (fine on your home Wi-Fi). For a **release** APK to share with others you need an `https://` server address and a signing key: *Build → Generate Signed App Bundle / APK*.

## Part D – Running 24 hours (recommended for real use)
Rent a small Linux VPS (2 GB RAM is enough), install Docker, copy the project folder, run `docker compose up -d --build`, and put a domain with HTTPS in front (e.g. Caddy or a provider's managed HTTPS). Then set `backendUrl=https://your-domain` and rebuild the app. Keep `.env` and `secrets/` private and back up the `pgdata` volume.

## Everyday use
* Check the dashboard **Health** and **Review** tabs daily at first: confirm good notifications, fix wrong types, handle **Vacancy drafts** (open → compare with the official PDF → correct numbers → *Approve*).
* Add organizations/sources over time (*Sources → Add a source*). Add many more organizations by adding lines to `backend\sql\registry.txt` and running `docker compose restart api`.

## Problems
| Symptom | Fix |
|---|---|
| Docker says WSL / virtualization error | Enable virtualization (step 1); run `wsl --install` in an Administrator cmd; restart |
| `port 8000 already in use` | Close the other program or change `8000:8000` to `8001:8000` in `docker-compose.yml` |
| App says "Cannot reach the server" | Phone and laptop on the same Wi-Fi? Firewall rule added? Address in *Settings* correct and starting with `http://`? |
| No push alerts | Dashboard Health: Firebase configured? `google-services.json` placed before building? Notifications allowed on phone? A notification only pushes after it is verified, and the first crawl of a source is deliberately silent (it only sets a baseline) |
| App shows "Nothing yet" everywhere | Server has not collected data yet. Dashboard → Sources → **Check ALL sources now**, wait 5–10 min, then Health/Review. Check Logs for errors. Pull the latest version (an earlier version had a scheduler bug that stopped all checks) and run `docker compose up -d --build` |
| Many sources "pending" or "unavailable" | Expected at first. Government sites differ; use *Preview links* / *Edit* to point each at its real notifications page |
| Gradle sync fails | Check internet; *File → Invalidate Caches → Restart*; make sure Android Studio's JDK is 17 (Settings → Build Tools → Gradle → Gradle JDK) |
