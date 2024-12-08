import datetime
from flask import Flask, render_template, request, redirect, url_for, g, flash, session
import sqlite3
import requests
import json
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from forms import LoginForm, RegisterForm, ShopRegisterForm, BookForm, ShopUpdateForm
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.from_object(Config)

app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def format_currency(value):
    if value is None:
        return "Rp0"  # Atau format default lainnya
    return f'Rp{value:,.0f}'.replace(',', '.')

@app.route('/shop/dashboard')
def shop_dashboard():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))
    
    db = get_db()
    shop_id = session.get('shop_id')

    query_total_books = '''
    SELECT 
        SUM(orderitems.quantity) AS total_books_sold
    FROM 
        orders
    JOIN orderitems
    ON 
        orders.order_id = orderitems.order_id
    WHERE 
        orders.status = 'paid' AND
        orderitems.shop_id = ?
    '''
    cur = db.execute(query_total_books, (shop_id,))
    total_books_sold = cur.fetchone()['total_books_sold']

    query_total_sales = '''
    SELECT 
        SUM(orderitems.total_price) AS total_sales
    FROM 
        orders
    JOIN orderitems
    ON 
        orders.order_id = orderitems.order_id
    WHERE 
        orders.status = 'paid' AND
        orderitems.shop_id = ?
    '''
    cur = db.execute(query_total_sales, (shop_id,))
    total_sales = cur.fetchone()['total_sales']

    query_orders = '''
    SELECT 
    orders.order_id, orders.buyer_id, 
    orders.order_date, orders.subtotal, orders.total, 
    orders.status, orders.delivery_address, shipment.status

    FROM 
        orders
    JOIN orderitems
    ON 
        orders.order_id = orderitems.order_id
    LEFT JOIN shipment
    ON
        orders.order_id = shipment.order_id
    WHERE 
        orders.status = 'paid' AND
        orderitems.shop_id = ?
    
    '''

    cur = db.execute(query_orders, (shop_id,))
    orders = cur.fetchall()
    
    return render_template('shop/dashboard.html', orders=orders, total_books_sold=total_books_sold, total_sales=total_sales)

@app.route('/shop/detail_order/<int:order_id>', methods=['GET', 'POST'])
def detail_order(order_id):
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    db = get_db()
    shop_id = session.get('shop_id')
    query_orders = '''
    SELECT 
        orders.order_id, buyer.buyer_id, buyer.username AS buyer_name, 
        books.book_name, orderitems.quantity, orderitems.price, 
        orderitems.total_price, orders.total, orders.order_date, 
        orders.delivery_address, orders.status

    FROM 
        orders
    JOIN orderitems ON orders.order_id = orderitems.order_id
    JOIN buyer ON orders.buyer_id = buyer.buyer_id
    JOIN books ON books.book_id = orderitems.book_id
    WHERE 
        orders.status = 'paid' AND
        orderitems.shop_id = ? AND
        orders.order_id = ?
    '''

    cur = db.execute(query_orders, (shop_id, order_id))
    orders = cur.fetchall()

    return render_template('shop/detail_order.html', orders=orders)

@app.route('/')
def index():
    template = 'customer/index.html'
    if session.get('role') == 'buyer':
        template = 'customer/buyer_index.html'
    elif session.get('role') == 'shop':
        template = 'shop/shop_index.html'
    return render_template(template, books=[], format_currency=format_currency)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    form = LoginForm()
    if form.validate_on_submit():
        admin_name = form.username.data
        password = form.password.data

        db = get_db()
        cur = db.execute('SELECT * FROM admin WHERE admin_name = ?', (admin_name,))
        admin = cur.fetchone()

        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['admin_id']
            session['admin_name'] = admin['admin_name']
            session['role'] = 'admin'
            flash('Admin login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin name or password.', 'danger')

    return render_template('admin/admin_login.html', form=form)

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to access this page.', 'danger')
        return redirect(url_for('admin_login'))

    db = get_db()
    buyers = db.execute('SELECT * FROM buyer').fetchall()
    shops = db.execute('SELECT * FROM shop').fetchall()
    return render_template('admin/admin_dashboard.html', buyers=buyers, shops=shops)


@app.route('/admin/delete/<user_type>/<int:user_id>', methods=['POST'])
def admin_delete(user_type, user_id):
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to perform this action.', 'danger')
        return redirect(url_for('admin_login'))

    db = get_db()
    if user_type == 'buyer':
        db.execute('DELETE FROM buyer WHERE buyer_id = ?', (user_id,))
    elif user_type == 'shop':
        db.execute('DELETE FROM shop WHERE shop_id = ?', (user_id,))
    else:
        flash('Invalid user type.', 'danger')
        return redirect(url_for('admin_dashboard'))

    db.commit()
    flash(f'{user_type.capitalize()} deleted successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/buyer_index', methods=['GET'])
def buyer_index():
    if 'user_id' not in session:
        flash('You need to be logged in to access the buyer index.', 'warning')
        return redirect(url_for('login'))

    db = get_db()
    books = db.execute('SELECT * FROM books').fetchall()
    return render_template('customer/buyer_index.html', books=books, format_currency=format_currency)


@app.route('/shop/order', methods=['Get'])
def shop_order():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))
    
    db = get_db()
    shop_id = session.get('shop_id')

    query = '''
    SELECT 
        orders.order_id, orders.buyer_id, 
        orders.order_date, orders.subtotal, orders.total, 
        orders.status, orders.delivery_address, shipment.status AS shipment_status
    FROM 
        orders
     LEFT JOIN 
        shipment 
    ON 
        orders.order_id = shipment.order_id
    JOIN orderitems
    ON 
        orders.order_id = orderitems.order_id
    WHERE 
        orderitems.shop_id = ?
    '''

    cur = db.execute(query, (shop_id,))
    orders = cur.fetchall()

    return render_template('shop/orders.html', orders=orders)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        dob = form.dob.data
        email = form.email.data
        phone_number = form.phone_number.data
        password = form.password.data
        buyer_address = form.buyer_address.data

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            db = get_db()
            db.execute('''INSERT INTO buyer (username, dob, email, phone_number, password, buyer_address) 
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (username, dob, email, phone_number, hashed_password, buyer_address))
            db.commit()
            flash('You have successfully registered! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    return render_template('customer/register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        db = get_db()
        cur = db.execute('SELECT * FROM buyer WHERE username = ?', (username,))
        user = cur.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['buyer_id']
            session['username'] = user['username']
            session['role'] = 'buyer'
            flash('Login successful!', 'success')
            return redirect(url_for('buyer_index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('customer/login.html', form=form)


@app.route('/shop/register', methods=['GET', 'POST'])
def shop_register():
    form = ShopRegisterForm()
    if form.validate_on_submit():
        shop_name = form.shop_name.data
        owner_name = form.owner_name.data
        shop_phone = form.shop_phone.data
        password = form.password.data
        shop_address = form.shop_address.data
        shop_email = form.shop_email.data
        shop_description = form.shop_description.data

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        try:
            db = get_db()
            db.execute('''INSERT INTO shop (shop_name, owner_name, shop_phone, shop_address, shop_email, shop_description, password)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                       (shop_name, owner_name, shop_phone, shop_address, shop_email, shop_description, hashed_password))
            db.commit()
            flash('Your shop has been successfully registered! Please log in.', 'success')
            return redirect(url_for('shop_login'))
        except sqlite3.IntegrityError:
            flash('Shop name, email or phone number already exists.', 'danger')
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    return render_template('shop/shop_register.html', form=form)


@app.route('/shop/login', methods=['GET', 'POST'])
def shop_login():
    form = LoginForm()
    if form.validate_on_submit():
        shop_name = form.username.data
        password = form.password.data

        db = get_db()
        cur = db.execute('SELECT * FROM shop WHERE shop_name = ?', (shop_name,))
        shop = cur.fetchone()

        if shop and check_password_hash(shop['password'], password):
            session['shop_id'] = shop['shop_id']
            session['shop_name'] = shop['shop_name']
            session['role'] = 'shop'
            if not is_shop_verified(shop['shop_id']):
                session['verification_message'] = 'Your shop is not verified. Please contact admin.'
                return redirect(url_for('logout'))
            flash('Login successful!', 'success')
            return redirect(url_for('manage_books'))
        else:
            flash('Invalid shop name or password.', 'danger')

    return render_template('shop/shop_login.html', form=form)

@app.route('/admin/verify_shop/<int:shop_id>', methods=['POST'])
def verify_shop(shop_id):
    if 'admin_id' not in session:
        flash('You must be logged in as an admin to perform this action.', 'danger')
        return redirect(url_for('admin_login'))

    db = get_db()
    db.execute('UPDATE shop SET isverified = 1 WHERE shop_id = ?', (shop_id,))
    db.commit()
    flash('Shop verified successfully.', 'success')
    return redirect(url_for('admin_dashboard'))

def is_shop_verified(shop_id):
    db = get_db()
    cur = db.execute('SELECT isverified FROM shop WHERE shop_id = ?', (shop_id,))
    shop = cur.fetchone()
    return shop and shop['isverified'] == 1

@app.route('/shop/profile', methods=['GET'])
def profile():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))
    
    db = get_db()
    shop_id = session.get('shop_id')

    query_total_books = '''
    SELECT 
        SUM(books.stock) AS total_books
    FROM 
        books
    WHERE 
        books.shop_id = ?
    '''
    cur = db.execute(query_total_books, (shop_id,))
    total_books = cur.fetchone()['total_books']

    query_total_sales = '''
    SELECT 
        SUM(orderitems.total_price) AS total_sales
    FROM 
        orders
    JOIN orderitems
    ON 
        orders.order_id = orderitems.order_id
    WHERE 
        orders.status = 'paid' AND
        orderitems.shop_id = ?
    '''
    cur = db.execute(query_total_sales, (shop_id,))
    total_sales = cur.fetchone()['total_sales']


    cur = db.execute('SELECT * FROM shop WHERE shop_id = ?', (shop_id,))
    shop_data = cur.fetchone()

    return render_template('shop/profile.html', shop_data=shop_data, total_books=total_books, total_sales=total_sales)

@app.route('/shop/edit_profile/<int:shop_id>', methods=['GET', 'POST'])
def edit_profile(shop_id):
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    db = get_db()
    form = ShopUpdateForm()

    # Fetch current shop data
    shop_data = db.execute('SELECT * FROM shop WHERE shop_id = ?', (shop_id,)).fetchone()

    if not shop_data or shop_data['shop_id'] != session.get('shop_id'):
        flash('Shop data not found or you do not have permission to edit this profile.', 'danger')
        return redirect(url_for('profile'))

    if request.method == 'GET':
        # Populate form with current shop data
        form.shop_name.data = shop_data['shop_name']
        form.owner_name.data = shop_data['owner_name']
        form.shop_phone.data = shop_data['shop_phone']
        form.shop_address.data = shop_data['shop_address']
        form.shop_email.data = shop_data['shop_email']
        form.shop_description.data = shop_data['shop_description']

    if form.validate_on_submit():
        shop_name = form.shop_name.data
        owner_name = form.owner_name.data
        shop_phone = form.shop_phone.data
        shop_address = form.shop_address.data
        shop_email = form.shop_email.data
        shop_description = form.shop_description.data

        try:
            db.execute('''
                UPDATE shop
                SET shop_name = ?, owner_name = ?, shop_phone = ?, shop_address = ?, shop_email = ?, shop_description = ?
                WHERE shop_id = ?
            ''', (
                shop_name, owner_name, shop_phone, shop_address, shop_email, shop_description, shop_id
            ))
            db.commit()
            flash('Shop profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    return render_template('shop/edit_profile.html', form=form, shop_id=shop_id)


@app.route('/logout')
def logout():
    verification_message = session.pop('verification_message', None)
    session.clear()
    if verification_message:
        flash('verification_message', 'danger')
    else:
        flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/book/<int:book_id>')
def book(book_id):
    try:
        db = get_db()
        cur = db.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
        book = cur.fetchone()
        category_name = None
        if book and book['category_id']:
            cur = db.execute('SELECT category_name FROM categories WHERE category_id = ?', (book['category_id'],))
            category = cur.fetchone()
            category_name = category['category_name'] if category else "No category"
        return render_template('customer/book.html', book=book, category_name=category_name,
                               format_currency=format_currency)
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('index'))



@app.route('/add_to_cart/<int:book_id>', methods=['POST'])
def add_to_cart(book_id):
    if 'user_id' not in session:
        flash('You need to be logged in to add items to the cart.', 'warning')
        return redirect(url_for('login'))

    try:
        db = get_db()
        cur = db.execute('SELECT * FROM books WHERE book_id = ?', (book_id,))
        book = cur.fetchone()

        if book:
            # Check if there is an existing open cart for the user
            cart_cur = db.execute('SELECT cart_id FROM cart WHERE buyer_id = ? AND status = ?',
                                  (session['user_id'], 'open'))
            cart_id = cart_cur.fetchone()

            # If no open cart exists, create a new one
            if not cart_id:
                db.execute('INSERT INTO cart (buyer_id, status) VALUES (?, ?)',
                           (session['user_id'], 'open'))
                cart_id = db.execute('SELECT cart_id FROM cart WHERE buyer_id = ? AND status = ?',
                                     (session['user_id'], 'open')).fetchone()

            # Check if the book is already in the cart
            cur = db.execute(
                'SELECT * FROM cartitems WHERE cart_id = ? AND book_id = ?',
                (cart_id['cart_id'], book_id)
            )
            item = cur.fetchone()

            if item:
                db.execute('UPDATE cartitems SET quantity = quantity + 1 WHERE cart_item_id = ?',
                           (item['cart_item_id'],))
            else:
                db.execute('INSERT INTO cartitems (cart_id, book_id, quantity) VALUES (?, ?, ?)',
                           (cart_id['cart_id'], book_id, 1))

            db.commit()
            flash('Book added to cart!', 'success')
        else:
            flash('Book not found.', 'danger')

        return redirect(url_for('buyer_index'))
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('buyer_index'))



@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('You need to be logged in to view your cart.', 'warning')
        return redirect(url_for('login'))

    try:
        db = get_db()
        cur = db.execute('''
            SELECT b.book_id, b.book_name, b.author, IFNULL(b.price, 0) as price, ci.quantity
            FROM cartitems ci
            JOIN books b ON ci.book_id = b.book_id
            JOIN cart c ON ci.cart_id = c.cart_id
            WHERE c.buyer_id = ? AND c.status = "open"
        ''', (session['user_id'],))
        cart_items = cur.fetchall()
        return render_template('customer/cart.html', cart_items=cart_items, format_currency=format_currency)
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')
        return redirect(url_for('index'))

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    if 'user_id' not in session:
        flash('You need to be logged in to clear your cart.', 'warning')
        return redirect(url_for('login'))

    try:
        db = get_db()
        db.execute('''
            DELETE FROM cartitems
            WHERE cart_id = (SELECT cart_id FROM cart WHERE buyer_id = ? AND status = "open")
        ''', (session['user_id'],))
        db.commit()
        flash('Your cart has been cleared.', 'success')
    except Exception as e:
        flash(f'An error occurred while clearing your cart: {e}', 'danger')

    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('You need to be logged in to checkout.', 'warning')
        return redirect(url_for('login'))

    try:
        db = get_db()
        user_id = session['user_id']

        # Get the cart items
        cur = db.execute('''
            SELECT b.book_name, b.desc, b.price, c.quantity, b.book_id, sh.shop_id, b.price as individual_price, 
                            (c.quantity * b.price) as total_price, sh.shop_email, sh.shop_name, sh.owner_name,
                            c.cart_id
            FROM cartitems c
            JOIN books b ON c.book_id = b.book_id
            JOIN shop sh ON sh.shop_id = b.shop_id
            WHERE c.cart_id = (SELECT cart_id FROM cart WHERE buyer_id = ? AND status = ?)
        ''', (user_id, 'open'))
        cart_items = cur.fetchall()

        if not cart_items:
            flash('Your cart is empty.', 'warning')
            return redirect(url_for('index'))

        # Get the payment methods
        cur = db.execute('SELECT method_id, method_name FROM paymentmethods')
        payment_methods = cur.fetchall()

        if request.method == 'POST':
            # Create a new order
            total_price = sum(item['price'] * item['quantity'] for item in cart_items)
            address = request.form.get('address')  # Collect delivery address

            cur = db.cursor()  # Use a cursor object to execute the insert command

            # Retrieve the cart_id from the cart_items
            cart_id = cart_items[0]['cart_id'] if cart_items else 0

            # Calculate the platform fee
            platform_fee = total_price * 0.05
            total_price_with_fee = total_price + platform_fee

            cur.execute(
                'INSERT INTO orders (cart_id, buyer_id, subtotal, total, status, delivery_address, order_date) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)',
                (cart_id, user_id, total_price, total_price_with_fee, 'initiated', address))
            order_id = cur.lastrowid  # Get the ID of the new order

            for item in cart_items:
                cur.execute(
                    'INSERT INTO orderitems (order_id, book_id, shop_id, quantity, price, total_price) VALUES (?, ?, ?, ?, ?, ?)',
                    (order_id, item['book_id'], item['shop_id'], item['quantity'], item['individual_price'],
                     item['total_price']))

            db.commit()

            # Update cart status
            cur.execute('UPDATE cart SET status = ? WHERE cart_id = ?', ('completed', cart_id))
            db.commit()
            cur.close()  # Close the cursor

            flash('Your order has been placed successfully. Please proceed with the payment.', 'success')
            return redirect(url_for('payment', order_id=order_id))

        total = sum(item['price'] * item['quantity'] for item in cart_items)
        platform_fee = total * 0.05
        total_with_fee = total + platform_fee

        return render_template('customer/checkout.html', cart=cart_items, total=total, platform_fee=platform_fee,
                               total_with_fee=total_with_fee, payment_methods=payment_methods,
                               format_currency=format_currency)

    except sqlite3.Error as e:
        app.logger.error('Database error occurred: %s', e)
        flash('An error occurred while processing your request. Please try again.', 'danger')
    except Exception as e:
        app.logger.error('Error occurred: %s', e)
        flash('An unexpected error occurred. Please try again.', 'danger')
    return redirect(url_for('index'))





def process_payment(order_id, method_id, amount):
    payment_url = "http://127.0.0.1:5001/process_payment"
    payload = json.dumps({
        "method_id": method_id,
        "order_id": order_id,
        "amount": amount
    })
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(payment_url, headers=headers, data=payload)
    return response.json()


def create_shipment(order_id, address):
    shipment_url = "http://127.0.0.1:5002/create_shipment"
    payload = json.dumps({
        "order_id": order_id,
        "address": address
    })
    headers = {
        'Content-Type': 'application/json'
    }
    response = requests.post(shipment_url, headers=headers, data=payload)
    return response.json()


@app.route('/payment/<int:order_id>', methods=['GET', 'POST'])
def payment(order_id):
    if 'user_id' not in session:
        flash('You need to be logged in to make a payment.', 'warning')
        return redirect(url_for('login'))

    db = get_db()

    # Fetch order details
    order = db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()

    if request.method == 'POST':
        method_id = request.form.get('method')

        # Retrieve method_name for method_id
        method_name = db.execute('SELECT method_name FROM paymentmethods WHERE method_id = ?', (method_id,)).fetchone()[
            'method_name']

        # Define payment gateway API URL
        payment_url = 'http://localhost:5001/process_payment'
        data = {
            "amount": order['total'],
            "method_id": method_id,
            "method_name": method_name,
            "order_id": order_id
        }

        try:
            response = requests.post(payment_url, json=data)
            try:
                response_data = response.json()
                if response.status_code == 200 and response_data['status'] == 'success':
                    transaction_id = response_data['data']['transaction_id']
                    payment_status = response_data['data']['payment_status']
                    payment_total = order['total']  # Retrieve payment total from order

                    # Insert payment details
                    db.execute(
                        'INSERT INTO payments (method_id, order_id, transaction_id, payment_date, payment_status, payment_total) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)',
                        (method_id, order_id, transaction_id, payment_status, payment_total))
                    db.execute('UPDATE orders SET status = ? WHERE order_id = ?', ('paid', order_id))
                    db.commit()
                    flash('Payment successful!', 'success')
                else:
                    flash('Payment declined by the gateway.', 'danger')
            except requests.exceptions.JSONDecodeError:
                flash('Payment gateway returned an invalid response.', 'danger')
        except requests.ConnectionError:
            flash('Failed to connect to the payment gateway.', 'danger')

        return redirect(url_for('buyer_index'))

    # Fetch available payment methods
    methods = db.execute('SELECT * FROM paymentmethods').fetchall()
    return render_template('customer/payment.html', order=order, methods=methods, format_currency=format_currency)


@app.route('/shop/manage_books', methods=['GET', 'POST'])
def manage_books():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    db = get_db()
    shop_id = session.get('shop_id')

    query = '''
    SELECT 
        books.book_id, books.book_name, books.isbn, books.author, books.desc, books.price, books.stock, books.img_url, categories.category_name
    FROM 
        books
    LEFT JOIN 
        categories 
    ON 
        books.category_id = categories.category_id
    WHERE 
        books.shop_id = ?
    '''

    cur = db.execute(query, (shop_id,))
    books = cur.fetchall()

    return render_template('shop/manage_books.html', books=books, format_currency=format_currency)


@app.route('/shop/add_book', methods=['GET', 'POST'])
def add_book():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    form = BookForm()
    db = get_db()

    # Fetch categories for the category dropdown
    categories = db.execute('SELECT * FROM categories').fetchall()
    form.category_id.choices = [(c['category_id'], c['category_name']) for c in categories]

    if form.validate_on_submit():
        book_name = form.book_name.data
        isbn = form.isbn.data
        author = form.author.data
        desc = form.desc.data
        price = form.price.data
        stock = form.stock.data
        category_id = form.category_id.data
        shop_id = session.get('shop_id')
        image_file = save_image(form.image.data)

        try:
            db.execute('''
                INSERT INTO books (category_id, shop_id, book_name, isbn, author, desc, price, stock, img_url) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (category_id, shop_id, book_name, isbn, author, desc, price, stock, image_file))
            db.commit()
            flash('Book added successfully!', 'success')
            return redirect(url_for('manage_books'))
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    return render_template('shop/add_book.html', form=form)


def save_image(file):
    if not file:
        return None
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return filename


@app.route('/shop/edit_book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    db = get_db()
    form = BookForm()

    # Fetch categories for the category dropdown
    categories = db.execute('SELECT * FROM categories').fetchall()
    form.category_id.choices = [(c['category_id'], c['category_name']) for c in categories]

    book = db.execute('SELECT * FROM books WHERE book_id = ? AND shop_id = ?', (book_id, session['shop_id'])).fetchone()
    if not book:
        flash('Book not found or you do not have permission to edit this book.', 'warning')
        return redirect(url_for('manage_books'))

    if form.validate_on_submit():
        book_name = form.book_name.data
        isbn = form.isbn.data
        author = form.author.data
        desc = form.desc.data
        price = form.price.data
        stock = form.stock.data
        category_id = form.category_id.data

        # Check if a new image file is uploaded
        if form.image.data:
            image_file = save_image(form.image.data)
        else:
            image_file = book['img_url']

        try:
            db.execute('''
                UPDATE books 
                SET category_id = ?, book_name = ?, isbn = ?, author = ?, desc = ?, price = ?, stock = ?, img_url = ? 
                WHERE book_id = ? AND shop_id = ?
            ''', (category_id, book_name, isbn, author, desc, price, stock, image_file, book_id, session['shop_id']))
            db.commit()
            flash('Book updated successfully!', 'success')
            return redirect(url_for('manage_books'))
        except Exception as e:
            flash(f'An error occurred: {e}', 'danger')

    form.book_name.data = book['book_name']
    form.isbn.data = book['isbn']
    form.author.data = book['author']
    form.desc.data = book['desc']
    form.price.data = book['price']
    form.stock.data = book['stock']
    form.category_id.data = book['category_id']

    return render_template('shop/edit_book.html', form=form, book_id=book_id)




@app.route('/shop/delete_book/<int:book_id>', methods=['POST'])
def delete_book(book_id):
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    db = get_db()
    try:
        db.execute('DELETE FROM books WHERE book_id = ? AND shop_id = ?', (book_id, session['shop_id']))
        db.commit()
        flash('Book deleted successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('manage_books'))

@app.route('/shop/create_shipment/<int:order_id>', methods=['POST'])
def create_shipment_route(order_id):
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to perform this action.', 'warning')
        return redirect(url_for('shop_login'))

    try:
        db = get_db()
        # Check if order exists
        order = db.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
        if not order:
            flash('Order not found!', 'danger')
            return redirect(url_for('shop_order'))

        # Call external shipment service
        shipment_service_url = 'http://localhost:5002/initiate_shipment'
        shipment_service_payload = {
            'order_id': order_id,
            'shipment_service': 'default_service'  # or any other parameter as needed
        }

        response = requests.post(shipment_service_url, json=shipment_service_payload)
        shipment_response = response.json()

        if shipment_response.get('status') == 'success':
            flash('Shipment created successfully!', 'success')
        else:
            flash(f"Failed to create shipment: {shipment_response.get('message', 'Unknown error.')}", 'danger')

    except requests.exceptions.RequestException as e:
        flash(f'An error occurred while contacting the shipment service: {e}', 'danger')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('view_shipments'))


@app.route('/shop/view_shipments')
def view_shipments():
    if session.get('role') != 'shop':
        flash('You need to be logged in as a shop to access this page.', 'warning')
        return redirect(url_for('shop_login'))

    try:
        db = get_db()
        shipments = db.execute('''
            SELECT s.*, o.order_date, o.delivery_address
            FROM shipment s
            JOIN orders o ON s.order_id = o.order_id
            JOIN orderitems oi ON oi.order_id = o.order_id
            WHERE oi.shop_id = ?
        ''', (session.get('shop_id'),)).fetchall()

        return render_template('shop/view_shipments.html', shipments=shipments)

    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('dashboard'))


@app.route('/buyer/view_shipments')
def buyer_view_shipments():
    if session.get('role') != 'buyer':
        flash('You need to be logged in as a buyer to access this page.', 'warning')
        return redirect(url_for('buyer_login'))

    try:
        db = get_db()
        shipments = db.execute('''
                 SELECT s.shipment_id, s.tracking_no, s.shipment_date, s.received_date, s.status, s.shipment_service,
                        o.order_date, o.delivery_address
                 FROM shipment s
                 INNER JOIN orders o ON s.order_id = o.order_id
                 WHERE o.buyer_id = ?
             ''', (session.get('user_id'),)).fetchall()

        return render_template('customer/view_shipments.html', shipments=shipments)

    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('buyer_index'))


@app.route('/buyer/track_shipment/<tracking_no>')
def track_shipment_route(tracking_no):
    if session.get('role') != 'buyer':
        flash('You need to be logged in as a buyer to perform this action.', 'warning')
        return redirect(url_for('buyer_login'))

    try:
        # Call external shipment tracking service
        tracking_service_url = f'http://localhost:5002/track_shipment/{tracking_no}'

        response = requests.get(tracking_service_url)
        tracking_response = response.json()

        if tracking_response.get('status') == 'success':
            tracking_info = tracking_response['shipment_data']
            return render_template('customer/track_shipment.html', tracking_info=tracking_info)
        else:
            flash(tracking_response.get('message', 'An error occurred during shipment tracking.'), 'danger')

    except requests.exceptions.RequestException as e:
        flash(f'An error occurred while contacting the shipment service: {e}', 'danger')
    except Exception as e:
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('buyer_index'))

@app.route('/buyer/resolve_shipment/<tracking_no>', methods=['POST'])
def resolve_shipment(tracking_no):
    if session.get('role') != 'buyer':
        flash('You need to be logged in as a buyer to perform this action.', 'warning')
        return redirect(url_for('buyer_login'))

    try:
        # Perform actions needed to resolve the shipment
        # For example, update shipment status in database
        db = get_db()
        db.execute('UPDATE shipment SET status = ?, received_date = ? WHERE tracking_no = ?', ('Delivered', datetime.datetime.now().isoformat(),  tracking_no))
        db.commit()
        flash('Shipment has been resolved.', 'success')

    except Exception as e:
        flash(f'An error occurred while resolving the shipment: {e}', 'danger')

    return redirect(url_for('track_shipment_route', tracking_no=tracking_no))


if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
