from flask import Flask, render_template, request, send_from_directory
import os
import random
import string

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Temporary memory storage (code -> filename)
file_store = {}

def generate_code():
    return ''.join(random.choices(string.digits, k=6))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":

        file = request.files.get("file")

        # Safe validation
        if file and file.filename:

            code = generate_code()

            # Ensure filename is string
            original_name = str(file.filename)

            filename = f"{code}_{original_name}"
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

            file.save(filepath)

            file_store[code] = filename

            return render_template("index.html", code=code)

    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    code = request.form.get("code")

    if code and code in file_store:
        filename = file_store[code]
        return render_template("download.html", code=code)
    else:
        return "Invalid Code!"


@app.route("/get_file/<code>")
def get_file(code):
    if code in file_store:
        filename = file_store[code]
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
    else:
        return "File not found!"


# Render compatible run
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
