from flask import Flask, request, render_template_string
import subprocess

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Docksmith UI</title>
<style>
body {
    font-family: Arial;
    background: #0f172a;
    color: white;
    padding: 20px;
}

h1 {
    text-align: center;
}

.container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.card {
    background: #1e293b;
    padding: 15px;
    border-radius: 10px;
}

button {
    padding: 8px 12px;
    margin-top: 10px;
    background: #3b82f6;
    border: none;
    color: white;
    cursor: pointer;
}

button:hover {
    background: #2563eb;
}

input {
    width: 95%;
    padding: 6px;
    margin: 5px 0;
}

.output {
    background: black;
    padding: 10px;
    height: 250px;
    overflow-y: scroll;
    font-family: monospace;
    border-radius: 8px;
}

.image-item {
    background: #334155;
    padding: 8px;
    margin: 5px 0;
    border-radius: 5px;
}
</style>
</head>

<body>

<h1>Docksmith Dashboard</h1>

<div class="container">

<div class="card">
<h3>🏗️ Build Image</h3>
<form method="post" action="/build">
Name:<br><input name="name"><br>
Tag:<br><input name="tag"><br>
Path:<br><input name="path" value="sample_app/"><br>
<button type="submit">Build</button>
</form>
</div>

<div class="card">
<h3>▶️ Run Container</h3>
<form method="post" action="/run">
Image:<br><input name="image"><br>
<button type="submit">Run</button>
</form>
</div>

<div class="card">
<h3>📦 Images</h3>
<form method="post" action="/images">
<button type="submit">Refresh</button>
</form>

<div>
{% for img in images %}
<div class="image-item">
{{ img }}
<form method="post" action="/run" style="display:inline;">
<input type="hidden" name="image" value="{{ img.split()[0] + ':' + img.split()[1] }}">
<button>Run</button>
</form>
<form method="post" action="/delete" style="display:inline;">
<input type="hidden" name="image" value="{{ img.split()[0] + ':' + img.split()[1] }}">
<button style="background:red;">Delete</button>
</form>
</div>
{% endfor %}
</div>

</div>

</div>

<h3>📜 Output</h3>
<div class="output"><pre>{{ output }}</pre></div>

</body>
</html>
"""

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout + result.stderr

def get_images():
    result = subprocess.run(
        "python3 docksmith.py images",
        shell=True,
        capture_output=True,
        text=True
    )
    return [line for line in result.stdout.splitlines() if line.strip()]

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML, output="", images=get_images())

@app.route("/build", methods=["POST"])
def build():
    name = request.form["name"]
    tag = request.form["tag"]
    path = request.form["path"]
    output = run_cmd(f"python3 docksmith.py build -t {name}:{tag} {path}")
    return render_template_string(HTML, output=output, images=get_images())

@app.route("/run", methods=["POST"])
def run():
    image = request.form["image"]
    output = run_cmd(f"python3 docksmith.py run {image}")
    return render_template_string(HTML, output=output, images=get_images())

@app.route("/images", methods=["POST"])
def images():
    output = run_cmd("python3 docksmith.py images")
    return render_template_string(HTML, output=output, images=get_images())

@app.route("/delete", methods=["POST"])
def delete():
    image = request.form["image"]
    output = run_cmd(f"python3 docksmith.py rmi {image}")
    return render_template_string(HTML, output=output, images=get_images())

if __name__ == "__main__":
    app.run(debug=True)