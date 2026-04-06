from flask import Flask, render_template, session, request, flash, redirect, url_for
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from .config import Config # Ensure this matches your filename
import os

# 1. Extensions defined globally
db = SQLAlchemy()
bcrypt = Bcrypt()
oauth = OAuth()

def create_app():
    app = Flask(__name__)
    
    # 2. LOAD CONFIG FIRST
    app.config.from_object(Config)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # --- DEBUGGING SAFETY CHECK ---
    # This will print in your terminal when you run 'flask run'
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    print(f"\n--- DATABASE URI CHECK ---")
    print(f"URI found: {db_uri}")
    print(f"--------------------------\n")

    if not db_uri:
        # Emergency fallback if Config failed to load URI
        from urllib.parse import quote_plus
        user = os.environ.get('DB_USER')
        pw = quote_plus(os.environ.get('DB_PASSWORD'))
        host = os.environ.get('DB_HOSTING')
        port = os.environ.get('DB_PORT')
        db_name = os.environ.get('DB_NAME')
        app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db_name}"

    # 3. INITIALIZE AFTER URI IS GUARANTEED
    db.init_app(app)
    bcrypt.init_app(app)
    oauth.init_app(app)
    
    @app.route('/google5448905c392d0cc5.html')
    def google_verify():
        return '<html><body>google-site-verification: google5448905c392d0cc5.html</body></html>'
    
    @app.before_request
    def sync_session_role():
        from flask import session
        if session.get('member_id'):
            from .models import Member
            member = Member.query.get(session['member_id'])
            if member and session.get('role') != member.role:
                session['role'] = member.role

    @app.context_processor
    def inject_global_counts():
        """Inject unread message & notification counts into every template."""
        from flask import session
        unread_count = 0
        notif_count  = 0
        if session.get('member_id'):
            from .models import Chat, Notification
            me = session['member_id']
            unread_count = Chat.query.filter_by(
                receiver_id=me, is_read=False
            ).count()
            notif_count = Notification.query.filter_by(
                member_id=me, is_read=False
            ).count()
        return dict(unread_count=unread_count, notif_count=notif_count)
    # ────────────────────────────────────────────────────────

    # 4. DEFERRED IMPORTS (Inside function to prevent Circular Imports)
    from .routes.auth import auth_bp
    from .routes.main import main_bp
    from .routes.products import products_bp
    from .routes.chat import chat_bp
    from .routes.admin import admin_bp
    from .routes.demands import demands_bp
    from .routes.notifications import notifs_bp
    from .routes.transactions import transactions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(demands_bp)
    app.register_blueprint(notifs_bp)    
    app.register_blueprint(transactions_bp)

    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created/verified successfully.")
        except Exception as e:
            print(f"❌ Database connection failed during create_all: {e}")
            raise  # Don't hide this — let it crash loudly so you know

    return app
