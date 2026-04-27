import os
import secrets
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, session
import requests as http
from src import config, state

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

DISCORD_API = "https://discord.com/api/v10"
OAUTH_AUTHORIZE = "https://discord.com/oauth2/authorize"
OAUTH_TOKEN = "https://discord.com/api/oauth2/token"
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://127.0.0.1:5000/callback")
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
ADMINISTRATOR = 0x8


def _is_admin_in_bot_guilds(user_guilds: list) -> bool:
    bot_guild_ids = {str(g["id"]) for g in state.guilds}
    for g in user_guilds:
        if str(g["id"]) in bot_guild_ids:
            if int(g.get("permissions", 0)) & ADMINISTRATOR:
                return True
    return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


LOGIN_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lucy Admin — Login</title>
  <style>
    body { font-family: sans-serif; background: #1a1a2e; color: #eee; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
    .card { background: #1e1e3a; border: 1px solid #444; border-radius: 12px; padding: 48px 40px; text-align: center; max-width: 360px; width: 100%; }
    h1 { color: #a78bfa; margin: 0 0 8px; font-size: 1.6rem; }
    p { color: #888; margin: 0 0 32px; font-size: 0.95rem; }
    a.discord-btn {
      display: inline-flex; align-items: center; gap: 10px;
      background: #5865f2; color: white; text-decoration: none;
      padding: 12px 28px; border-radius: 8px; font-size: 1rem; font-weight: 600;
      transition: background 0.15s;
    }
    a.discord-btn:hover { background: #4752c4; }
    .error { background: #7f1d1d; color: #fca5a5; padding: 10px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 0.9rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Lucy Admin</h1>
    <p>Sign in with Discord to continue.<br>You must have admin permissions in a server Lucy is in.</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <a class="discord-btn" href="{{ auth_url }}">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057.101 18.08.114 18.1.132 18.11a19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03z"/></svg>
      Login with Discord
    </a>
  </div>
</body>
</html>
"""

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lucy Admin</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; background: #1a1a2e; color: #eee; }
    .topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    h1 { color: #a78bfa; margin: 0; }
    .user-info { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; color: #aaa; }
    .user-info img { width: 32px; height: 32px; border-radius: 50%; }
    .logout { color: #888; text-decoration: none; font-size: 0.85rem; border: 1px solid #444; padding: 4px 12px; border-radius: 6px; }
    .logout:hover { background: #2d2d44; color: #eee; }
    label { display: block; margin: 12px 0 4px; font-size: 0.9rem; color: #aaa; }
    input[type=text], input[type=number], textarea, select {
      width: 100%; padding: 8px; border-radius: 6px;
      border: 1px solid #444; background: #2d2d44; color: #eee; font-size: 0.95rem;
    }
    textarea { height: 80px; resize: vertical; }
    .row { display: flex; gap: 16px; }
    .row > div { flex: 1; }
    .ch-row { display: flex; align-items: center; gap: 8px; margin: 6px 0; }
    .ch-row input[type=checkbox] { width: 16px; height: 16px; margin: 0; flex-shrink: 0; }
    .ch-row label { display: inline; color: #eee; margin: 0; font-size: 0.95rem; }
    .save-btn { margin-top: 28px; padding: 10px 28px; background: #7c3aed; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }
    .save-btn:hover { background: #6d28d9; }
    .flash { background: #166534; color: #bbf7d0; padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; }
    .muted { color: #888; font-size: 0.85rem; margin: 2px 0 0; }
    .guild-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }
    .guild-bar select { width: auto; flex: 1; }

    /* Tabs */
    .tabs { display: flex; gap: 4px; margin-bottom: 0; flex-wrap: wrap; }
    .tab-btn {
      padding: 8px 18px; border: 1px solid #444; border-bottom: none;
      background: #2d2d44; color: #aaa; border-radius: 6px 6px 0 0;
      cursor: pointer; font-size: 0.9rem; transition: background 0.15s;
    }
    .tab-btn:hover { background: #3a3a5c; color: #eee; }
    .tab-btn.active { background: #1e1e3a; color: #a78bfa; border-color: #555; }
    .tab-panel {
      display: none; padding: 24px; border: 1px solid #555;
      border-radius: 0 6px 6px 6px; background: #1e1e3a;
    }
    .tab-panel.active { display: block; }
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Lucy Admin</h1>
    <div class="user-info">
      {% if user.avatar %}
        <img src="https://cdn.discordapp.com/avatars/{{ user.id }}/{{ user.avatar }}.png" alt="">
      {% endif %}
      <span>{{ user.global_name or user.username }}</span>
      <a class="logout" href="/logout">Logout</a>
    </div>
  </div>

  <form method="get" class="guild-bar">
    <label style="margin:0;white-space:nowrap">Server:</label>
    {% if guilds %}
      <select name="guild" onchange="this.form.submit()">
        {% for g in guilds %}
          <option value="{{ g.id }}" {% if g.id == selected_guild_id %}selected{% endif %}>{{ g.name }}</option>
        {% endfor %}
      </select>
    {% else %}
      <span class="muted">Bot not connected yet — guilds will appear once it's online.</span>
    {% endif %}
  </form>

  {% if selected_guild_id %}
    {% if saved %}<div class="flash">Settings saved for {{ selected_guild_name }}.</div>{% endif %}
    <form method="post">
      <input type="hidden" name="guild_id" value="{{ selected_guild_id }}">

      <div class="tabs">
        <button type="button" class="tab-btn active" onclick="showTab('bot', this)">Bot</button>
        <button type="button" class="tab-btn" onclick="showTab('llm', this)">Language Model</button>
        <button type="button" class="tab-btn" onclick="showTab('imggen', this)">Image Generation</button>
        <button type="button" class="tab-btn" onclick="showTab('flux2i2i', this)">Flux2 Restyle</button>
        <button type="button" class="tab-btn" onclick="showTab('inpaint', this)">Inpainting</button>
        <button type="button" class="tab-btn" onclick="showTab('upscale', this)">Upscaling</button>
        <button type="button" class="tab-btn" onclick="showTab('channels', this)">Channels</button>
      </div>

      <div id="tab-bot" class="tab-panel active">
        <label>Trigger prefix</label>
        <input type="text" name="prefix" value="{{ cfg.prefix }}">
      </div>

      <div id="tab-llm" class="tab-panel">
        <label>Ollama model</label>
        <input type="text" name="ollama_model" value="{{ cfg.ollama_model }}">
        <label>Inpaint model</label>
        <input type="text" name="inpaint_model" value="{{ cfg.inpaint_model }}">
        <p class="muted">Used to extract mask subject and edit prompt — should be a local uncensored model</p>
        <label>Vision model</label>
        <input type="text" name="vision_model" value="{{ cfg.vision_model }}">
        <p class="muted">Used for image description/analysis — must support vision (e.g. gemma3:12b, llava)</p>
        <label>NSFW image prompt model</label>
        <input type="text" name="nsfw_image_model" value="{{ cfg.nsfw_image_model }}">
        <p class="muted">Used when "nsfw" is included in the message — must be an uncensored model</p>
        <label>Chat system prompt</label>
        <textarea name="chat_system_prompt">{{ cfg.chat_system_prompt }}</textarea>
      </div>

      <div id="tab-imggen" class="tab-panel">
        <label>Model</label>
        <select name="txt2img_model" id="model-select" onchange="updateModelFields()">
          {% for val, label in [("flux2_klein", "FLUX.2 Klein"), ("juggernaut", "Juggernaut XL"), ("flux_schnell", "FLUX.1 Schnell"), ("flux_dev", "FLUX.1 Dev")] %}
            <option value="{{ val }}" {% if cfg.txt2img_model == val %}selected{% endif %}>{{ label }}</option>
          {% endfor %}
        </select>

        <div class="row" style="margin-top:12px">
          <div><label>Width</label><input type="number" name="image_width" value="{{ cfg.image_width }}"></div>
          <div><label>Height</label><input type="number" name="image_height" value="{{ cfg.image_height }}"></div>
        </div>

        <div id="juggernaut-fields">
          <div class="row">
            <div><label>Steps</label><input type="number" name="image_steps" value="{{ cfg.image_steps }}"></div>
            <div><label>CFG</label><input type="number" step="0.1" name="image_cfg" value="{{ cfg.image_cfg }}"></div>
          </div>
        </div>

        <div id="flux2-klein-fields">
          <div class="row">
            <div><label>Steps</label><input type="number" name="flux2_t2i_steps" value="{{ cfg.flux2_t2i_steps }}"><p class="muted">4 recommended</p></div>
            <div><label>CFG</label><input type="number" step="0.1" name="flux2_t2i_cfg" value="{{ cfg.flux2_t2i_cfg }}"><p class="muted">1 recommended</p></div>
          </div>
        </div>

        <div id="flux-dev-fields">
          <div class="row">
            <div><label>Steps</label><input type="number" name="flux_steps" value="{{ cfg.flux_steps }}"></div>
            <div><label>Guidance</label><input type="number" step="0.1" name="flux_guidance" value="{{ cfg.flux_guidance }}"><p class="muted">3.5 recommended</p></div>
          </div>
        </div>
      </div>

      <div id="tab-flux2i2i" class="tab-panel">
        <div class="row">
          <div><label>Steps</label><input type="number" name="flux2_i2i_steps" value="{{ cfg.flux2_i2i_steps }}"><p class="muted">4 recommended</p></div>
          <div><label>CFG</label><input type="number" step="0.1" name="flux2_i2i_cfg" value="{{ cfg.flux2_i2i_cfg }}"><p class="muted">1 recommended</p></div>
        </div>
      </div>

      <div id="tab-inpaint" class="tab-panel">
        <div class="row">
          <div>
            <label>Detection threshold</label>
            <input type="number" step="0.01" min="0.01" max="1" name="inpaint_threshold" value="{{ cfg.inpaint_threshold }}">
            <p class="muted">Lower = catch more strands (0.05 recommended)</p>
          </div>
          <div>
            <label>Mask expand (px)</label>
            <input type="number" name="inpaint_expand" value="{{ cfg.inpaint_expand }}">
            <p class="muted">Grows mask outward to catch edges</p>
          </div>
          <div>
            <label>Mask blur radius</label>
            <input type="number" name="inpaint_blur_radius" value="{{ cfg.inpaint_blur_radius }}">
            <p class="muted">Feathers mask edges</p>
          </div>
        </div>
      </div>

      <div id="tab-upscale" class="tab-panel">
        <div class="row">
          <div>
            <label>Target resolution (px)</label>
            <input type="number" name="upscale_resolution" value="{{ cfg.upscale_resolution }}">
            <p class="muted">Long-edge target — 2048 recommended</p>
          </div>
          <div>
            <label>Color correction</label>
            <select name="upscale_color_correction">
              {% for opt in ["lab", "none"] %}
                <option value="{{ opt }}" {% if cfg.upscale_color_correction == opt %}selected{% endif %}>{{ opt }}</option>
              {% endfor %}
            </select>
            <p class="muted">lab preserves original colours better</p>
          </div>
        </div>
      </div>

      <div id="tab-channels" class="tab-panel">
        <p class="muted" style="margin:0 0 12px">None selected = respond in all channels.</p>
        {% if guild_channels %}
          {% for ch in guild_channels %}
            <div class="ch-row">
              <input type="checkbox" name="allowed_channels" value="{{ ch.id }}" id="ch_{{ ch.id }}"
                {% if ch.id in cfg.allowed_channels %}checked{% endif %}>
              <label for="ch_{{ ch.id }}">#{{ ch.name }}</label>
            </div>
          {% endfor %}
        {% else %}
          <p class="muted">No channels found for this server.</p>
        {% endif %}
      </div>

      <button type="submit" class="save-btn">Save</button>
    </form>
  {% elif guilds %}
    <p class="muted">Select a server above to configure it.</p>
  {% endif %}

  <script>
    function updateModelFields() {
      const m = document.getElementById('model-select').value;
      document.getElementById('juggernaut-fields').style.display = m === 'juggernaut' ? '' : 'none';
      document.getElementById('flux2-klein-fields').style.display = m === 'flux2_klein' ? '' : 'none';
      document.getElementById('flux-dev-fields').style.display = m === 'flux_dev' ? '' : 'none';
    }
    updateModelFields();

    function showTab(name, btn) {
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      btn.classList.add('active');
    }
    {% if saved %}
      const saved_tab = sessionStorage.getItem('lucy_active_tab');
      if (saved_tab) {
        const btn = [...document.querySelectorAll('.tab-btn')].find(b => b.getAttribute('onclick').includes("'" + saved_tab + "'"));
        if (btn) showTab(saved_tab, btn);
      }
      sessionStorage.removeItem('lucy_active_tab');
    {% endif %}
    document.querySelector('form[method=post]').addEventListener('submit', () => {
      const active = document.querySelector('.tab-btn.active');
      if (active) {
        const match = active.getAttribute('onclick').match(/'(\w+)'/);
        if (match) sessionStorage.setItem('lucy_active_tab', match[1]);
      }
    });
  </script>
</body>
</html>
"""


@app.route("/login")
def login():
    if session.get("user"):
        return redirect(url_for("index"))
    error = request.args.get("error")
    state_token = secrets.token_urlsafe(16)
    session["oauth_state"] = state_token
    auth_url = (
        f"{OAUTH_AUTHORIZE}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify+guilds"
        f"&state={state_token}"
    )
    return render_template_string(LOGIN_TEMPLATE, auth_url=auth_url, error=error)


@app.route("/callback")
def callback():
    if request.args.get("state") != session.pop("oauth_state", None):
        return redirect(url_for("login", error="Invalid state — please try again."))

    code = request.args.get("code")
    if not code:
        return redirect(url_for("login", error="No code returned from Discord."))

    token_resp = http.post(OAUTH_TOKEN, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=10)

    if not token_resp.ok:
        return redirect(url_for("login", error="Failed to get token from Discord."))

    access_token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    user_resp = http.get(f"{DISCORD_API}/users/@me", headers=headers, timeout=10)
    guilds_resp = http.get(f"{DISCORD_API}/users/@me/guilds", headers=headers, timeout=10)

    if not user_resp.ok or not guilds_resp.ok:
        return redirect(url_for("login", error="Failed to fetch your Discord profile."))

    if not _is_admin_in_bot_guilds(guilds_resp.json()):
        return redirect(url_for("login", error="You don't have admin permissions in any server Lucy is in."))

    session["user"] = user_resp.json()
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    guilds = state.guilds
    saved = False
    selected_guild_id = None
    selected_guild_name = ""
    cfg = {}
    guild_channels = []

    if request.method == "POST":
        guild_id = int(request.form["guild_id"])
        cfg = config.load(guild_id)
        cfg["prefix"] = request.form["prefix"].strip()
        cfg["ollama_model"] = request.form["ollama_model"].strip()
        cfg["inpaint_model"] = request.form["inpaint_model"].strip()
        cfg["vision_model"] = request.form["vision_model"].strip()
        cfg["nsfw_image_model"] = request.form["nsfw_image_model"].strip()
        cfg["chat_system_prompt"] = request.form["chat_system_prompt"].strip()
        cfg["txt2img_model"] = request.form["txt2img_model"].strip()
        cfg["image_width"] = int(request.form["image_width"])
        cfg["image_height"] = int(request.form["image_height"])
        cfg["image_steps"] = int(request.form.get("image_steps", 20))
        cfg["image_cfg"] = float(request.form.get("image_cfg", 6.0))
        cfg["flux_steps"] = int(request.form.get("flux_steps", 20))
        cfg["flux_guidance"] = float(request.form.get("flux_guidance", 3.5))
        cfg["flux2_t2i_steps"] = int(request.form.get("flux2_t2i_steps", 4))
        cfg["flux2_t2i_cfg"] = float(request.form.get("flux2_t2i_cfg", 1))
        cfg["flux2_i2i_steps"] = int(request.form.get("flux2_i2i_steps", 4))
        cfg["flux2_i2i_cfg"] = float(request.form.get("flux2_i2i_cfg", 1))
        cfg["inpaint_threshold"] = float(request.form["inpaint_threshold"])
        cfg["inpaint_expand"] = int(request.form["inpaint_expand"])
        cfg["inpaint_blur_radius"] = int(request.form["inpaint_blur_radius"])
        cfg["upscale_resolution"] = int(request.form["upscale_resolution"])
        cfg["upscale_color_correction"] = request.form["upscale_color_correction"].strip()
        cfg["allowed_channels"] = [int(v) for v in request.form.getlist("allowed_channels")]
        config.save(guild_id, cfg)
        saved = True
        selected_guild_id = guild_id
    elif request.args.get("guild"):
        selected_guild_id = int(request.args["guild"])
    elif guilds:
        selected_guild_id = guilds[0]["id"]

    if selected_guild_id:
        cfg = config.load(selected_guild_id)
        guild_channels = [ch for ch in state.channels if ch["guild_id"] == selected_guild_id]
        match = next((g for g in guilds if g["id"] == selected_guild_id), None)
        selected_guild_name = match["name"] if match else ""

    return render_template_string(
        TEMPLATE,
        guilds=guilds,
        selected_guild_id=selected_guild_id,
        selected_guild_name=selected_guild_name,
        cfg=cfg,
        guild_channels=guild_channels,
        saved=saved,
        user=session["user"],
    )


def run():
    app.run(host="127.0.0.1", port=5001, use_reloader=False)
