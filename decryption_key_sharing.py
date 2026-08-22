from flask import Flask, request

app = Flask(__name__)

@app.route("/upload_key", methods=["POST"])
def receive_key():
    file = request.files['key']
    file.save("received_key.key")
    return "Key received", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
