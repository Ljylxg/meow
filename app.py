import os
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = "dev-key-2025"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

USERS = {
    "admin": {
        "username": "admin",
        "password": "admin123",
        "role": "admin",
        "email": "admin@example.com",
        "phone": "13800138000",
        "balance": 99999
    },
    "alice": {
        "username": "alice",
        "password": "alice2025",
        "role": "user",
        "email": "alice@example.com",
        "phone": "13900139001",
        "balance": 100
    }
}


@app.route("/")
def index():
    username = session.get("username")
    user_info = None
    if username and username in USERS:
        user_info = USERS[username]
    return render_template("index.html", user_info=user_info)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    user_info = None

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            user_info = USERS[username]
            return render_template("index.html", user_info=user_info)
        else:
            error = "用户名或密码错误"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


@app.route("/search")
def search():
    query = request.args.get("q", "")
    return render_template("search.html", query=query)


UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    error = None
    success_url = None
    filename = None

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename:
            filename = file.filename
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            success_url = url_for('static', filename=f'uploads/{filename}')
        else:
            error = "请选择要上传的文件"

    return render_template("upload.html", error=error, success_url=success_url, filename=filename)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
