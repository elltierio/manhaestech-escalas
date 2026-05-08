from __future__ import annotations

from functools import wraps

from flask import abort
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import ActivityLog, User, log_activity


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.get("/login")
def login() -> str:
    return render_template("login.html")


@auth_bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = db.session.query(User).filter(User.username == username).first()
    if not user or not user.check_password(password):
        try:
            log_activity(
                actor_user_id=None,
                actor_username=username or None,
                action="login_failed",
                entity="auth",
                entity_id=None,
                ip=request.remote_addr,
                user_agent=request.headers.get("User-Agent"),
                detail="invalid_credentials",
            )
        except Exception:
            db.session.rollback()
        flash("Usuário ou senha inválidos.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    try:
        log_activity(
            actor_user_id=user.id,
            actor_username=user.username,
            action="login",
            entity="auth",
            entity_id=None,
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=None,
        )
    except Exception:
        db.session.rollback()
    return redirect(url_for("dashboard.dashboard"))


@auth_bp.post("/logout")
@login_required
def logout():
    try:
        log_activity(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="logout",
            entity="auth",
            entity_id=None,
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            detail=None,
        )
    except Exception:
        db.session.rollback()
    logout_user()
    return redirect(url_for("auth.login"))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_admin", False):
            abort(403)
        return view(*args, **kwargs)

    return wrapper


@auth_bp.get("/users")
@admin_required
def users():
    q = (request.args.get("q") or "").strip()
    query = db.session.query(User)
    if q:
        query = query.filter(User.username.ilike(f"%{q}%"))
    items = query.order_by(User.username.asc()).all()
    return render_template("users.html", users=items, q=q)


@auth_bp.get("/users/new")
@admin_required
def user_new():
    user = User(username="", is_admin=False)
    return render_template("user_edit.html", user=user)


@auth_bp.post("/users/new")
@admin_required
def user_new_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    is_admin = (request.form.get("is_admin") == "on")

    if not username:
        flash("Informe o usuário.", "danger")
        return redirect(url_for("auth.user_new"))
    if len(password) < 6:
        flash("A senha deve ter no mínimo 6 caracteres.", "danger")
        return redirect(url_for("auth.user_new"))

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um usuário com esse nome.", "danger")
        return redirect(url_for("auth.user_new"))

    log_activity(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="create",
        entity="user",
        entity_id=str(user.id),
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        detail=f"username={user.username};is_admin={user.is_admin}",
    )

    flash("Usuário criado.", "success")
    return redirect(url_for("auth.user_edit", user_id=user.id))


@auth_bp.get("/users/<int:user_id>")
@admin_required
def user_edit(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.users"))
    return render_template("user_edit.html", user=user)


@auth_bp.post("/users/<int:user_id>")
@admin_required
def user_edit_post(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.users"))

    username = (request.form.get("username") or "").strip()
    is_admin = (request.form.get("is_admin") == "on")
    password = request.form.get("password") or ""

    if not username:
        flash("Informe o usuário.", "danger")
        return redirect(url_for("auth.user_edit", user_id=user_id))

    user.username = username
    user.is_admin = is_admin
    if password:
        if len(password) < 6:
            flash("A senha deve ter no mínimo 6 caracteres.", "danger")
            return redirect(url_for("auth.user_edit", user_id=user_id))
        user.set_password(password)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Já existe um usuário com esse nome.", "danger")
        return redirect(url_for("auth.user_edit", user_id=user_id))

    log_activity(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="update",
        entity="user",
        entity_id=str(user.id),
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        detail=f"username={user.username};is_admin={user.is_admin};password_changed={'yes' if password else 'no'}",
    )

    flash("Usuário atualizado.", "success")
    return redirect(url_for("auth.user_edit", user_id=user.id))


@auth_bp.post("/users/<int:user_id>/delete")
@admin_required
def user_delete_post(user_id: int):
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("auth.users"))

    if user.id == current_user.id:
        flash("Você não pode excluir o próprio usuário.", "danger")
        return redirect(url_for("auth.user_edit", user_id=user_id))

    db.session.delete(user)
    db.session.commit()

    log_activity(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="delete",
        entity="user",
        entity_id=str(user_id),
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        detail=None,
    )

    flash("Usuário excluído.", "success")
    return redirect(url_for("auth.users"))


@auth_bp.get("/logs")
@admin_required
def logs():
    q = (request.args.get("q") or "").strip()
    query = db.session.query(ActivityLog)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (ActivityLog.actor_username.ilike(like))
            | (ActivityLog.action.ilike(like))
            | (ActivityLog.entity.ilike(like))
            | (ActivityLog.detail.ilike(like))
        )

    items = query.order_by(ActivityLog.created_at.desc()).limit(300).all()
    return render_template("logs.html", logs=items, q=q)
