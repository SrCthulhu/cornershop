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

    mensaje = request.args.get('mensaje')
    return render_template(
        "carro_detalle.html",
        productos=productos,
        cart=cart,
        mensaje=mensaje
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

    couponId = session.get('coupon_id')
    coupon = db.coupons.find_one({'_id': ObjectId(couponId)})

    for p in cartproducts:
        price = p['price']
        subtotal = subtotal + (int(price) * p['cantidad'])

    descuento = 0

    if coupon:
        descuento = subtotal * float(coupon['discount'])

    total = subtotal - descuento

    mensaje = request.args.get('mensaje')
    return render_template("checkout.html",
                           cartproducts=cartproducts,
                           subtotal=subtotal,
                           total=total,
                           mensaje=mensaje,
                           descuento=descuento,
                           coupon=coupon)


@app.route("/order/create")
def order_created_view():
    # nombre del input documento del checkout.html
    firstName = request.args.get('first_name')
    lastName = request.args.get('last_name')
    address = request.args.get('address')
    nota = request.args.get('nota')
    email = request.args.get('email')
    phone = request.args.get('phone')
    cupon = request.args.get('cupon')
    total = request.args.get('total')
    propina = request.args.get('propina')

    if firstName == "" or lastName == "" or address == "" or phone == "" or nota == "" or email == "" or cupon == "" or total == "" or propina == "":
        return redirect('/checkout?mensaje=tienes campos vacios')

    emailSplitted = email.split('@')
    if len(emailSplitted) != 2 or emailSplitted[1] != 'gmail.com':

        return redirect('/checkout?mensaje=la direccion de correo no es valida')

    user = session.get('id')
    cartproducts = list(db.cart.find({'user_id': user}))

    pedido = {}
    pedido['client'] = {
        'first_name': firstName,
        'last_name': lastName,
        'address': address,
        'nota': nota,
        'email': email,
        'phone': phone,
        'cupon': cupon
    }

    pedido['user_id'] = user
    pedido['cart'] = cartproducts
    pedido['total'] = total
    pedido['propina'] = propina
    pedido['status'] = 'paid'
    orderCreated = db.orders.insert_one(pedido)
    orderId = orderCreated.inserted_id

    db.cart.delete_many({'user_id': user})
    db.session.delete_many({'coupon_id': user})
    return redirect('/order/' + str(orderId))


@app.route("/order/<id>")
def order_view(id):
    pedido = db.orders.find_one({'_id': ObjectId(id)})

    return render_template("order_created.html", pedido=pedido)


@app.route("/coupon/apply")
def apply_coupon():
    # nombre del input documento del checkout.html
    couponCode = request.args.get('cupon')

    if couponCode == "":
        return redirect('/cart?mensaje=El campo cupon no puede estar vacio')

    coupon = db.coupons.find_one({'code': couponCode})

    if not coupon:
        return redirect('/cart?mensaje=El cupon no existe')

    # MAGIA
    session['coupon_id'] = str(coupon['_id'])

    return redirect('/cart')


@app.route("/order_list")
def order_detalle_view():

    # .sort() sirve para ordenar elementos con el criterio, en este caso con el id de forma descendente (del ultimo creado al primero)
    ordenes = list(db.orders.find().sort('_id', -1))

    return render_template("order_detalle.html", ordenes=ordenes)

# Actualizar Estado de una orden!!!


@app.route("/order/next/status/<id>")
def order_next_status(id):

    pedido = db.orders.find_one({'_id': ObjectId(id)})
    # status= se refiere al valor que tenga el pedido en la actualidad.
    status = pedido['status']

    if pedido['status'] == 'paid':
        # se cumple la condicion y se reemplaza el valor del status. de 'paid' a 'delivered'
        status = 'delivered'
    elif pedido['status'] == 'delivered':
        status = 'finished'

    db.orders.update_one(
        {'_id': ObjectId(id)},
        {'$set': {'status': status}}
    )
    # recargamos order list con darle continuar.
    return redirect('/order_list')
