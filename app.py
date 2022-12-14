from flask import Flask, render_template, redirect, session, request, abort
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
    nuevo['product_id'] = product_id
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

    mensaje1 = request.args.get('mensaje1')
    mensaje2 = request.args.get('mensaje2')
    return render_template(
        "carro_detalle.html",
        productos=productos,
        cart=cart,
        mensaje1=mensaje1,
        mensaje2=mensaje2,
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
    total = request.args.get('total')
    propina = request.args.get('propina')

    if firstName == "" or lastName == "" or address == "" or phone == "" or nota == "" or email == "" or total == "" or propina == "":
        return redirect('/checkout?mensaje=tienes campos vacios')

    emailSplitted = email.split('@')
    if len(emailSplitted) != 2 or emailSplitted[1] != 'gmail.com':

        return redirect('/checkout?mensaje=la direccion de correo no es valida')

    user = session.get('id')
    cartproducts = list(db.cart.find({'user_id': user}))
    # coupon_id es una variable global creada en #no es magia.
    cupon_id = session.get('coupon_id')

    cuponDocument = db.coupons.find_one({'_id': ObjectId(cupon_id)})
    ###################################
    # cupon = None lo definimos por defecto para que no de error cuando no se encuentre la base de datos el cupon.
    # o cuando no haya nada en la variable de sesion.('coupon_id')
    cupon = None
    if cuponDocument:  # es True siempre que consiga el documento.
        # si trajo un documento el valor del code se le aplica a la variable cupon.
        cupon = cuponDocument['code']
    ###################################

    orderExist = db.orders.find_one(
        {'client.cupon': cupon, 'client.email': email})
    if orderExist:
        # Cuando sea diferente a none se aplica el redirect. ejemplo cupon 'code'= hola. Cuando sea none el va a crear la orden aunque otra orden none exista
        if cupon != None:
            session.pop('coupon_id', None)
            return redirect('/checkout?mensaje=Este cupon ya fue aplicado')

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

    # session.pop sirve para borrar la variable de sesion.
    if session.get('coupon_id'):
        session.pop('coupon_id', None)
    # pero nos est?? sirviendo para que no le siga aplicando el cupon despues de haber creado la orden.
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
        return redirect('/cart?mensaje1=El campo cup??n no puede estar vacio')

    coupon = db.coupons.find_one({'code': couponCode})

    if not coupon:
        return redirect('/cart?mensaje1=El cup??n no existe')

    # NO ES MAGIA
    session['coupon_id'] = str(coupon['_id'])

    # caso exitoso
    return redirect('/cart?mensaje2=El cup??n fue aplicado exitosamente')


@app.route("/order_list")
def order_detalle_view():

    # restringimos el acceso al order_list aunque tenga una sesion iniciada con la variable 'admin'
    if not session.get('admin'):
        return redirect('/')

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


@app.route("/comentario/order/<id>")
def comentario_view(id):

    pedido = db.orders.find_one({'_id': ObjectId(id)})

    if (not pedido):
        return abort(404)

    mensaje1 = request.args.get('mensaje1')

    return render_template("comentario_detalle.html",
                           pedido=pedido,
                           mensaje1=mensaje1
                           )


@app.route("/comment/create")
def comment_create():
    commentText = request.args.get('comment')
    productId = request.args.get('product_id')
    orderId = request.args.get('order_id')

    pedido = db.orders.find_one({'_id': ObjectId(orderId)})

    comment = {}
    comment['comment'] = commentText
    comment['order_id'] = orderId
    comment['product_id'] = productId

    firstName = pedido['client']['first_name']
    lastName = pedido['client']['last_name']

    comment['client_full_name'] = f'{firstName} {lastName}'

    existComment = db.comments.find_one(
        {'order_id': orderId, 'product_id': productId})

    if existComment:
        return redirect('/comentario/order/' + orderId + '?mensaje1=Ya se hizo un comentario de ese producto')

    # inserted_id te indica el id insertado del nuevo documento
    commentCreatedId = db.comments.insert_one(comment).inserted_id

    return redirect('/producto/' + productId + '#comment-' + str(commentCreatedId))


@ app.route("/producto/<id>")
def producto_view(id):
    product = db.frutas.find_one({'_id': ObjectId(id)})
    if (not product):
        return abort(404)
    comments = db.comments.find({'product_id': id})
    return render_template("producto_detalle.html", product=product, comments=comments)


@ app.route("/login")
def login_view():
    mensaje = request.args.get('mensaje')
    return render_template("login.html", mensaje=mensaje)


@ app.route("/login/admins")
def login_admins():
    adminUser = request.args.get('user')
    adminPassword = request.args.get('password')

    if adminUser == "":
        return redirect('/login?mensaje=Ingresa el usuario')

    if adminPassword == "":
        return redirect('/login?mensaje=Ingresa la contrase??a')

    adminDocument = db.admins.find_one({'user': adminUser})

    if not adminDocument:
        return redirect('/login?mensaje=El usuario no existe')
    # adminpassword en este caso compara el documento en base de datos 'password' que sea igual al del formulario, si no es igual dispara mensaje de error
    if adminDocument['password'] != adminPassword:

        return redirect('/login?mensaje=La contrase??a no es v??lida')

    # 'id' del admin en la base de datos admins, le damos el valor a sesion['admin']
    session['admin'] = str(adminDocument['_id'])
    # caso positivo del if entra en el detalle solicitado.
    return redirect('/order_list')
