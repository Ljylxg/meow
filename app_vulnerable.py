from flask import Flask, render_template, render_template_string, request, redirect, session

app = Flask(__name__)
app.secret_key = "dev-key-2025"

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
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username in USERS and USERS[username]["password"] == password:
            session["username"] = username
            return render_template("index.html", user_info=USERS[username])
        else:
            error = "用户名或密码错误"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


# ============================================================
# 🚨 漏洞代码：SSTI（服务器端模板注入）
# 将用户输入直接拼接到模板字符串中，使用 render_template_string 渲染
# ============================================================
@app.route("/search")
def search():
    query = request.args.get("q", "")
    template = f"""
    {{% extends "base.html" %}}
    {{% block content %}}
    <div class="card">
        <h2>搜索结果</h2>
        <p>您搜索的是: {query}</p>
    </div>
    {{% endblock %}}
    """
    return render_template_string(template)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
