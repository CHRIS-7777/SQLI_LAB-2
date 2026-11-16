import importlib
import pkgutil

from flask import Flask, render_template_string

from . import apps as apps_pkg

HUB = """<!doctype html><html><head><meta charset="utf-8"><title>Meridian Web Services</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:#0f1419;color:#e6e9ef}
header{padding:40px 24px 10px;max-width:1000px;margin:auto}h1{margin:0;font-size:28px;letter-spacing:.3px}
p.sub{color:#8b95a7;margin:6px 0 0}
.grid{max-width:1000px;margin:24px auto;padding:0 24px 60px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
a.card{display:block;background:#1a212b;border:1px solid #273142;border-radius:10px;padding:18px;text-decoration:none;color:inherit;transition:.15s}
a.card:hover{border-color:#4f8cff;transform:translateY(-2px)}
.card h3{margin:0 0 6px;font-size:17px}.card p{margin:0;color:#8b95a7;font-size:14px;line-height:1.4}
.card span{display:block;margin-top:12px;font-size:12px;color:#4f8cff}
footer{text-align:center;color:#556070;font-size:12px;padding-bottom:30px}
</style></head><body>
<header><h1>Meridian Web Services</h1><p class="sub">Customer-facing portals &mdash; select a service</p></header>
<div class="grid">
{% for m in metas %}<a class="card" href="{{ m.prefix }}/"><h3>{{ m.title }}</h3><p>{{ m.tagline }}</p><span>{{ m.prefix }}/ &rarr;</span></a>{% endfor %}
</div><footer>&copy; Meridian Web Services</footer></body></html>"""


def discover():
    mods = []
    for m in pkgutil.iter_modules(apps_pkg.__path__):
        mod = importlib.import_module(f"{apps_pkg.__name__}.{m.name}")
        if hasattr(mod, "bp") and hasattr(mod, "META"):
            mods.append(mod)
    return sorted(mods, key=lambda x: x.META["title"].lower())


def create_app():
    app = Flask(__name__)
    app.secret_key = "meridian-internal-key"
    mods = discover()
    for mod in mods:
        app.register_blueprint(mod.bp, url_prefix=mod.META["prefix"])
    metas = [m.META for m in mods]

    @app.route("/")
    def hub():
        return render_template_string(HUB, metas=metas)

    @app.errorhandler(404)
    def nf(e):
        return ("<h1>404 Not Found</h1>", 404)

    @app.errorhandler(500)
    def err(e):
        return ("<h1>500 Internal Server Error</h1>", 500)

    return app
