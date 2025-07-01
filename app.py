from flask import Flask, render_template, request, send_file
import os
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from werkzeug.utils import secure_filename
from datetime import datetime
import json

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB file size limit

# Error handler for large files
@app.errorhandler(413)
def file_too_large(e):
    return "❌ File too large! Max allowed is 10MB.", 413

# Folder paths
UPLOAD_FOLDER = 'uploads'
MERGED_FOLDER = 'merged'
PROTECTED_FOLDER = 'protected'

# Create folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MERGED_FOLDER, exist_ok=True)
os.makedirs(PROTECTED_FOLDER, exist_ok=True)

# 🔒 Usage tracking setup (shared limit: max 5 uses/day for merge + protect)
USAGE_FILE = 'usage.json'
USAGE_LIMIT = 5

def get_today():
    return datetime.now().strftime('%Y-%m-%d')

def load_usage():
    if not os.path.exists(USAGE_FILE):
        return {}
    with open(USAGE_FILE, 'r') as f:
        return json.load(f)

def get_usage_count():
    data = load_usage()
    today = get_today()
    return data.get(today, 0)

def update_usage_count():
    data = load_usage()
    today = get_today()
    data[today] = data.get(today, 0) + 1
    with open(USAGE_FILE, 'w') as f:
        json.dump(data, f)

# 🏠 Home route
@app.route('/')
def home():
    return render_template('index.html')

# 📎 Merge PDF route
@app.route('/merge', methods=['GET', 'POST'])
def merge():
    if request.method == 'POST':
        if get_usage_count() >= USAGE_LIMIT:
            return "❌ Daily usage limit reached (5 actions/day). Upgrade to continue.", 403

        files = request.files.getlist('pdfs')
        merger = PdfMerger()

        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            merger.append(filepath)

        output_path = os.path.join(MERGED_FOLDER, 'merged.pdf')
        merger.write(output_path)
        merger.close()

        update_usage_count()
        return send_file(output_path, as_attachment=True)

    return render_template('merge.html', remaining=USAGE_LIMIT - get_usage_count())

# 🔐 Protect PDF route
@app.route('/protect', methods=['GET', 'POST'])
def protect():
    if request.method == 'POST':
        if get_usage_count() >= USAGE_LIMIT:
            return "❌ Daily usage limit reached (5 actions/day). Upgrade to continue.", 403

        pdf_file = request.files['pdf']
        password = request.form['password']

        if not pdf_file or not password:
            return "Please upload a PDF and enter a password."

        filename = secure_filename(pdf_file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        output_path = os.path.join(PROTECTED_FOLDER, f'protected_{filename}')
        pdf_file.save(input_path)

        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        with open(output_path, 'wb') as f:
            writer.write(f)

        update_usage_count()
        return send_file(output_path, as_attachment=True)

    return render_template('protect.html', remaining=USAGE_LIMIT - get_usage_count())

# 🔄 Admin Reset Usage Route
@app.route('/reset-usage', methods=['POST'])
def reset_usage():
    secret_key = request.form.get('key')
    if secret_key != "admin123":
        return "Unauthorized", 403

    today = get_today()
    data = load_usage()
    if today in data:
        data[today] = 0
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f)
    return "✅ Usage reset successfully for today."

# 🚀 Run the app
if __name__ == '__main__':
    app.run(debug=True)
