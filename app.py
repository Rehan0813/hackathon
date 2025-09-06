from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Project, Task, ProjectMember, Message
from forms import LoginForm, RegisterForm
from datetime import datetime
from supabase_client import supabase
# For Flask-Login with Supabase
from flask_login import UserMixin

class SupabaseUser(UserMixin):
    def __init__(self, id, email, first_name="", last_name=""):
        self.id = id  # Supabase UUID string
        self.email = email
        self.first_name = first_name
        self.last_name = last_name


app = Flask(__name__)
app.config["SECRET_KEY"] = "hackathon_secret_change_me"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///synergysphere.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ✅ Initialize DB
db.init_app(app)

# ✅ Setup login manager
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # user_id is a string UUID from Supabase
    profile_response = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    if profile_response.data:
        p = profile_response.data
        return SupabaseUser(id=p["id"], email=p["email"], first_name=p.get("first_name", ""), last_name=p.get("last_name", ""))
    return None
 

# ✅ Create tables once at startup
with app.app_context():
    db.create_all()
@app.route("/main")
@login_required
def main_dashboard():
    # Fetch user's projects and tasks
    memberships = ProjectMember.query.filter_by(user_id=current_user.id).all()
    projects = [m.project for m in memberships]
    

    tasks = Task.query.filter_by(assignee_id=current_user.id).all()

    return render_template(
        "main_dashboard.html",
        user=current_user,
        projects=projects,
        tasks=tasks
    )
# -------- Auth --------
@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("register"))

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        password = form.password.data

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if response.user:
            user_id = response.user.id
            profile_resp = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
            profile = profile_resp.data if profile_resp.data else {}

            user = SupabaseUser(
                id=user_id,
                email=email,
                first_name=profile.get("first_name", ""),
                last_name=profile.get("last_name", "")
            )
            login_user(user)
            return redirect(url_for("dashboard"))
        else:
            flash(response.get("error", {}).get("message", "Invalid credentials"), "danger")

    return render_template("login.html", form=form)


@app.route("/register", methods=["GET", "POST"])
@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        password = form.password.data
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()

        # Sign up user with Supabase
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if response.user:
            # Store profile info in Supabase table
            supabase.table("profiles").insert({
                "id": response.user.id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name
            }).execute()

            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        else:
            flash(response.get("error", {}).get("message", "Signup failed"), "danger")
    else:
        # Print validation errors to debug
        if form.errors:
            print("Form errors:", form.errors)

    return render_template("register.html", form=form)
@app.route("/solutions")
def solutions():
    return render_template("solutions.html")

@app.route("/work")
def work():
    return render_template("work.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    # Fetch user's projects
    projects_resp = supabase.table("project").select("*").execute()
    projects = projects_resp.data if projects_resp.data else []

    tasks =[]

    return render_template("dashboard.html", projects=projects, tasks=tasks)



@app.route("/projects")
@login_required
def projects():
    # Show all projects
    projects_resp = supabase.table("project").select("*").execute()
    projects = projects_resp.data if projects_resp.data else []
    return render_template("projects.html", projects=projects)

@app.route("/tasks")
@login_required
def tasks():
    tasks = []  # Empty list placeholder
    return render_template("tasks.html", tasks=tasks)


@app.route("/project/create", methods=["POST"])
@login_required
def create_project():
    # Get form data
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    tags = request.form.get("tags", "").strip()
    manager = request.form.get("manager", "").strip()
    deadline = request.form.get("deadline", "").strip()
    priority = request.form.get("priority", "Medium")
    image_url = request.form.get("image_url", "").strip()  # Optional

    if not name:
        flash("Project name is required", "warning")
        return redirect(url_for("dashboard"))

    # Insert into Supabase
    response = supabase.table("project").insert({
        "name": name,
        "description": description,
        "tags": tags,
        "manager": manager,
        "deadline": deadline or None,
        "priority": priority,
        "image_url": image_url,
        "created_by": current_user.id,
        "created_at": datetime.utcnow().isoformat()
    }).execute()

    if not response.data:  # Check for failure
        flash("Failed to create project. Please check your table and columns.", "danger")
    else:
        flash("Project created successfully!", "success")

    return redirect(url_for("dashboard"))


def _require_membership(project_id):
    is_member = ProjectMember.query.filter_by(project_id=project_id, user_id=current_user.id).first()
    if not is_member:
        abort(403)

@app.route("/project/<project_id>")
@login_required
def project_detail(project_id):
    # project_id is now a string UUID
    project_resp = supabase.table("project").select("*").eq("id", project_id).single().execute()
    if not project_resp.data:
        abort(404)
    return render_template("project_detail.html", project=project_resp.data)

@app.route("/project/<project_id>/edit", methods=["GET", "POST"])
@login_required
def edit_project(project_id):
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        tags = request.form.get("tags", "").strip()
        manager = request.form.get("manager", "").strip()
        deadline = request.form.get("deadline", "").strip()
        priority = request.form.get("priority", "Medium")

        if not name:
            flash("Project name is required", "warning")
            return redirect(url_for("project_detail", project_id=project_id))

        # Update in Supabase
        response = supabase.table("project").update({
            "name": name,
            "description": description,
            "tags": tags,
            "manager": manager,
            "deadline": deadline or None,
            "priority": priority,
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", project_id).execute()

        if response.data:
            flash("Project updated successfully!", "success")
        else:
            flash("Failed to update project", "danger")

        return redirect(url_for("project_detail", project_id=project_id))
    
    # GET request - show edit form
    project_resp = supabase.table("project").select("*").eq("id", project_id).single().execute()
    if not project_resp.data:
        abort(404)
    return render_template("edit_project.html", project=project_resp.data)

@app.route("/project/<project_id>/delete", methods=["DELETE"])
@login_required
def delete_project(project_id):
    # Delete from Supabase
    response = supabase.table("project").delete().eq("id", project_id).execute()
    
    if response.data:
        flash("Project deleted successfully!", "success")
        return redirect(url_for("projects"))
    else:
        flash("Failed to delete project", "danger")
        return redirect(url_for("project_detail", project_id=project_id))


# -------- Members --------
@app.route("/project/<int:project_id>/member/add", methods=["POST"])
@login_required
def add_member(project_id):
    _require_membership(project_id)
    email = (request.form.get("email") or "").lower().strip()
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("No user with that email", "warning")
        return redirect(url_for("project_detail", project_id=project_id))
    exists = ProjectMember.query.filter_by(project_id=project_id, user_id=user.id).first()
    if exists:
        flash("User is already a member", "info")
    else:
        db.session.add(ProjectMember(project_id=project_id, user_id=user.id))
        db.session.commit()
        flash("Member added", "success")
    return redirect(url_for("project_detail", project_id=project_id))

# -------- Tasks --------
@app.route("/project/<project_id>/tasks")
@login_required
def task_board(project_id):
    _require_membership(project_id)
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()
    return render_template("task_board.html", project=project, tasks=tasks)

@app.route("/project/<int:project_id>/task/create", methods=["POST"])
@login_required
def create_task(project_id):
    _require_membership(project_id)
    title = (request.form.get("title") or "").strip()
    desc = (request.form.get("description") or "").strip()
    due_date = (request.form.get("due_date") or "").strip()
    assignee_id = request.form.get("assignee_id") or None
    if not title:
        flash("Task title is required", "warning")
        return redirect(url_for("project_detail", project_id=project_id))
    task = Task(
        title=title, description=desc, project_id=project_id,
        assignee_id=int(assignee_id) if assignee_id else None,
        due_date=due_date, status="To-Do"
    )
    db.session.add(task)
    db.session.commit()
    flash("Task created", "success")
    return redirect(url_for("project_detail", project_id=project_id))

@app.route("/task/<int:task_id>", methods=["GET", "POST"])
@login_required
def task_detail(task_id):
    task = Task.query.get_or_404(task_id)
    _require_membership(task.project_id)
    if request.method == "POST":
        status = request.form.get("status")
        if status in ("To-Do", "In Progress", "Done"):
            task.status = status
            db.session.commit()
            flash("Task updated", "success")
        else:
            flash("Invalid status", "danger")
        return redirect(url_for("project_detail", project_id=task.project_id))
    return render_template("task_detail.html", task=task)

# -------- Chat / Discussion --------
@app.route("/project/<int:project_id>/chat", methods=["POST"])
@login_required
def send_message(project_id):
    _require_membership(project_id)
    content = (request.form.get("content") or "").strip()
    if not content:
        return redirect(url_for("project_detail", project_id=project_id))
    db.session.add(Message(project_id=project_id, user_id=current_user.id, content=content, timestamp=datetime.utcnow()))
    db.session.commit()
    return redirect(url_for("project_detail", project_id=project_id))

# -------- Profile --------
@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)

if __name__ == "__main__":
    app.run(debug=True)
