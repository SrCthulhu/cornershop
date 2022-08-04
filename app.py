from flask import Flask, render_template, redirect, session, request
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
import random

#############################
# APP FLASK CONFIGURATION
app = Flask(__name__)
app.secret_key = ".."
# DATABASE CONFIGURATION
uri = os.environ.get('MONGO_DB_URI', "mongodb://127.0.0.1")
print(uri)
client = MongoClient(uri)
db = client.cornershop
#############################


@app.route("/")
def home_view():
    if not session.get('id'):
        session['id'] = random.randint(12345, 99999)
    return render_template("home.html", id=session.get('id'))


@app.route("/tiendas")
def tiendas_view():
    stores = list(db.stores.find())
    expresstiendas = list(db.expresstiendas.find())
    destacados = list(db.destacados.find())

    return render_template("tiendas_detalle.html",
                           stores=stores,
                           expresstiendas=expresstiendas,
                           destacados=destacados)


@app.route("/store/<id>")
def store_view(id):
    # .find trae una lista de elementos.
    frutas = list(db.frutas.find({'store_id': id}))
    ofertas = list(db.ofertas.find({'store_id': id}))

    # .find_one trae un solo elemento, no es necesario hacer un For.
    store = db.stores.find_one({'_id': ObjectId(id)})

    return render_template(
        "store_detalle.html",
        ofertas=ofertas,
        frutas=frutas,
        store=store,
    )


@app.route("/cart/add/<store_id>/<product_id>")
def add_product_to_cart(store_id, product_id):
    product = db.frutas.find_one({'_id': ObjectId(product_id)})

    if not session.get('id'):
        return redirect('/')

    user = session.get('id')
    cartproduct = db.cart.find_one(
        {'title': product['title'], 'user_id': user})
    if cartproduct:
        db.cart.update_one(
            {'title': product['title'], 'user_id': user},
            {'$set':
                {'cantidad': cartproduct['cantidad'] + 1}
             }
        )
        return redirect('/cart')
    nuevo = {}
    nuevo['title'] = product['title']
    nuevo['img'] = product['img']
    nuevo['price'] = product['price']
    nuevo['store_id'] = product['store_id']
    nuevo['cantidad'] = 1
    nuevo['user_id'] = user
    db.cart.insert_one(nuevo)
    return redirect('/cart')


@app.route("/cart")
def cart_view():
    if not session.get('id'):
        return redirect('/')
    user = session.get('id')
    productos = list(db.cart.find({'user_id': user}))

    cart = {}
    for p in productos:
        storeId = p['store_id']
        if not storeId in cart:
            cart[storeId] = {}
            cart[storeId]['store'] = db.stores.find_one(
                {'_id': ObjectId(storeId)})
            cart[storeId]['products'] = []
        cart[storeId]['products'].append(p)

    return render_template(
        "carro_detalle.html",
        productos=productos,
        cart=cart,
    )


@app.route("/remove/<id>")
def remove_to_cart(id):
    db.cart.delete_one({'_id': ObjectId(id)})
    return redirect('/cart')


@app.route("/checkout")
def check_view():
    user = session.get('id')
    cartproducts = list(db.cart.find({'user_id': user}))
    subtotal = 0
    for p in cartproducts:
        price = p['price']
        subtotal = subtotal + (int(price) * p['cantidad'])
    total = subtotal
    return render_template("checkout.html",
                           cartproducts=cartproducts,
                           subtotal=subtotal,
                           total=total,
                           )
