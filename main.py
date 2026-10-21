from flask import Flask, request, jsonify

app = Flask(name)

@app.route("/", methods=["GET"])
def accueil():
return jsonify({
"ok": True,
"message": "ConductriceFashion Backend est prêt."
})

def main(context):
try:
response = accueil()
return context.res.json({
"ok": True,
"message": "ConductriceFashion Backend est actif."
})
except Exception as e:
return context.res.json({
"ok": False,
"message": "Erreur du backend."
}, 500)
