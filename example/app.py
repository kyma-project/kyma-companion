from flask import Flask, request


app = Flask(__name__)

# Kezdőoldal
@app.route("/", methods=["GET"])
def info():
    return "Docker alkalmazás"

# Helló Világ!
@app.route("/hello", methods=["GET"])
def hello():
    return "Helló Világ!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
