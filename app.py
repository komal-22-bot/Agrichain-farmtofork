from flask import Flask, redirect, request, jsonify, send_from_directory, session
import mysql.connector
from flask_cors import CORS
from block_data import Blockchain
import razorpay
import os
from werkzeug.utils import secure_filename
from db import mysql
from datetime import timedelta

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg","webp"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
CORS(app)
blockchain = Blockchain()

razorpay_client = razorpay.Client(auth=("rzp_test_SRtws3hBkoQHdH", "xCzks7P7vevpBR9MwBDv0zGF"))

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="student",
        database="agridb"
    )


@app.route("/", methods=["GET"])
def home():
    return "AgriChain backend running"

@app.route("/login", methods=["POST"])
def login():
    print("LOGIN API CALLED")

    data = request.get_json(force=True)
    print("DATA RECEIVED:", data)

    email = data.get("email")
    password = data.get("password")

    app.permanent_session_lifetime = timedelta(days=7)

    if data.get("remember_me"):
        session.permanent = True

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email or password missing"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT user_id as id, name, email, role, password FROM users WHERE email=%s",
        (email,)
    )
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if user:
        stored_password = user["password"]

        # 🔥 SIMPLE PASSWORD CHECK
        if password == stored_password:
            user.pop("password", None)  # remove password from response

            return jsonify({
                "success": True,
                "user": user
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Invalid password"
            }), 401
    else:
        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404
    
@app.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.json

    email = data.get('email')
    new_password = data.get('new_password')

    if not email or not new_password:
        return jsonify({
            "success": False,
            "message": "Email or new password missing"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET password=%s WHERE email=%s",
        (new_password, email)
    )

    conn.commit()

    if cursor.rowcount == 0:
        cursor.close()
        conn.close()
        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Password reset successfully"
    }), 200
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.json

        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')
        phone = data.get('phone')
        address = data.get('address')
        farm_size = data.get('farm_size') if role == "farmer" else None

        if not all([name, email, password, role, phone, address]):
            return jsonify({"message": "Missing fields"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO users (name, email, password, role, phone, address, farm_size) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (name, email, password, role, phone, address, farm_size)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "User registered successfully"})

    except Exception as e:
        print("REGISTER ERROR:", str(e))  # 👈 VERY IMPORTANT
        return jsonify({"message": "Server error", "error": str(e)}), 500

@app.route('/add-product', methods=['POST'])
def add_product():
    try:
        data = request.get_json(force=True)
        print("FINAL DATA:", data)

        import re
        from datetime import datetime, date

        # 1. Product Name → only letters
        if not re.match(r"^[A-Za-z\s]+$", data.get('name', '')):
            return jsonify({"message": "Only letters allowed in product name"}), 400

        # 2. Quantity & Price → must be positive
        if data.get('quantity') is None or data.get('price') is None:
            return jsonify({"message": "Missing quantity or price"}), 400

        if int(data.get('quantity')) <= 0 or float(data.get('price')) <= 0:
            return jsonify({"message": "Quantity and price must be positive"}), 400

        # 3. Harvest date → no future date
        if data.get('harvest_date'):
            harvest_date = datetime.strptime(data.get('harvest_date'), "%Y-%m-%d").date()
            if harvest_date > date.today():
                return jsonify({"message": "Future harvest date not allowed"}), 400

        # 4. Description → max 100 characters
        if data.get('description') and len(data.get('description')) > 100:
            return jsonify({"message": "Description too long (max 100 chars)"}), 400

        block_data = {
            "name": data.get('name'),
            "category": data.get('category'),
            "price": data.get('price'),
            "quantity": data.get('quantity'),
            "unit": data.get('unit'),
            "harvest_date": data.get('harvest_date'),
            "farmer_id": data.get('farmer_id')
        }

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        new_block = blockchain.add_block(block_data)
        block_hash = new_block["currentHash"]

        cursor.execute("""
            INSERT INTO blockchain_ledger (trans_id, hash_val, prev_hash, timestamp)
            VALUES (%s, %s, %s, NOW())
        """, (
            len(blockchain.chain),
            new_block["currentHash"],
            new_block["previousHash"]
        ))

        cursor.execute("""
            INSERT INTO products 
            (name, category, price, quantity, unit, harvest_date, status, description, image, isOrganic, farmer_id, hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            data.get('name'),
            data.get('category'),
            data.get('price'),
            data.get('quantity'),
            data.get('unit'),
            data.get('harvest_date'),
            'available',
            data.get('description'),
            data.get('image'),
            data.get('isOrganic'),
            data.get('farmer_id'),
            block_hash
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Product added successfully"}), 201

    except Exception as e:
        print("ADD PRODUCT ERROR:", str(e))
        return jsonify({"message": "Server error", "error": str(e)}), 500
    
@app.route('/get-farmer-orders/<int:farmer_id>', methods=['GET'])
def get_farmer_orders(farmer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.order_id,
            o.quantity,
            o.total_price,
            o.status,
            p.name AS product_name,
            u.name AS buyer_name
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        JOIN users u ON o.buyer_id = u.user_id
        WHERE p.farmer_id = %s
    """, (farmer_id,))

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(orders)


@app.route("/products/<int:farmer_id>", methods=["GET"])
def get_products(farmer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products WHERE farmer_id = %s", (farmer_id,))
    products = cursor.fetchall()
    cursor.close()
    conn.close()    
    return jsonify(products)

@app.route("/products", methods=["GET"])
def get_all_products(): 
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        cursor.execute("""
                       SELECT products.*, 
                       users.name AS farmer_name,
                       users.address AS farmer_address, 
                       users.phone AS farmer_phone
        FROM products 
        JOIN users ON products.farmer_id = users.user_id""")
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(products)
    except Exception as e:
        return jsonify({"message": f"Error fetching products: {str(e)}"}), 500

@app.route("/product/<int:product_id>", methods=["GET"])
def get_single_product(product_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get product + farmer info
        cursor.execute("""
            SELECT p.*, 
                   u.name AS farmer_name,
                   u.address AS farmer_location,
                   u.phone AS farmer_phone,
                   u.farm_size
            FROM products p
            JOIN users u ON p.farmer_id = u.user_id
            WHERE p.product_id = %s
        """, (product_id,))

        product = cursor.fetchone()

        if not product:
            return jsonify({"error": "Product not found"}), 404

        # Get rating from feedback table
        cursor.execute("""
            SELECT AVG(rating) AS avg_rating,
                   COUNT(*) AS total_reviews
            FROM feedback
            WHERE farmer_id = %s
        """, (product["farmer_id"],))

        rating_data = cursor.fetchone()

        avg_rating = 0
        total_reviews = 0

        if rating_data:
            avg_rating = round(rating_data["avg_rating"], 1) if rating_data["avg_rating"] else 0
            total_reviews = rating_data["total_reviews"]

        # Format product data
        product_data = {
            "product_id": product["product_id"],
            "name": product["name"],
            "category": product["category"],
            "price": product["price"],
            "unit": product["unit"],
            "quantity": product["quantity"],
            "harvestDate": product["harvest_date"],
            "blockchainHash": product["hash"],
            "farmer_id":product["farmer_id"],
            "image": product["image"],
        }

        cursor.close()
        conn.close()

        return jsonify({
            "product": product_data,
            "farmer": {
                "name": product["farmer_name"],
                "phone": product["farmer_phone"],
                "location": product["farmer_location"],
                "farmSize": product["farm_size"],
                "rating": avg_rating,
                "total_reviews": total_reviews,
                "crops": ["Wheat", "Rice", "Vegetables"]
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/blockchain", methods=["GET"])
def get_blockchain():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT bl.*, p.name AS product_name
    FROM blockchain_ledger bl
    LEFT JOIN products p ON bl.hash_val = p.hash
    ORDER BY bl.trans_id ASC
""")
    rows = cursor.fetchall()

    formatted = []
    for i, row in enumerate(rows):
        formatted.append({
            "blockNumber": row["trans_id"],
            "transactionType": row["product_name"],
            "currentHash": row["hash_val"],
            "previousHash": row["prev_hash"],
            "timestamp": row["timestamp"]
        })

    cursor.close()
    conn.close()

    return jsonify(formatted)

@app.route("/statistics", methods=["GET"])
def get_statistics():
    return jsonify({
        "satisfactionRate": 92,
        "totalVolume": 1500,
        "cropsTraded": 12
    })
    
@app.route('/uploads/<filename>')
def get_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)
    [1].lower() in {"png", "jpg", "jpeg", "webp"}

@app.route('/upload-image', methods=['POST'])
def upload_image():
    print("FILES RECEIVED:", request.files)
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    print("Filename:",file.filename)

    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if file and allowed_file(file.filename):
        print("Saving file...")
        filename = secure_filename(file.filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        return jsonify({
            "message": "Image uploaded successfully",
            "image_url": f"http://127.0.0.1:5000/uploads/{filename}"
        })
    return jsonify({"message": "Invalid file type"}), 400
    
@app.route("/delete-product/<int:product_id>", methods=["DELETE"])
def delete_product(product_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if product exists
        cursor.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
        product = cursor.fetchone()

        if not product:
            return jsonify({"message": "Product not found"}), 404

        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Product deleted successfully"})
    except Exception as e:
        return jsonify({"message": f"Error deleting product: {str(e)}"}), 500
    
@app.route("/delete-user/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"message": "User not found"}), 404

        # Delete user
        cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "User deleted successfully"})
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route("/cancel-order/<int:order_id>", methods=["DELETE"])
def cancel_order(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check order
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            return jsonify({"message": "Order not found"}), 404

        if order["status"].strip().lower() != "placed":
            return jsonify({"message": "Only placed orders can be cancelled"}), 400

        # Restore stock
        cursor.execute("""
            UPDATE products 
            SET quantity = quantity + %s 
            WHERE product_id = %s
        """, (order["quantity"], order["product_id"]))

        # Delete order
        cursor.execute("DELETE FROM orders WHERE order_id = %s", (order_id,))

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Order cancelled and removed"})

    except Exception as e:
        print("CANCEL ERROR:", e)
        return jsonify({"message": str(e)}), 500
    
@app.route("/update-stock/<int:product_id>", methods=["PUT"])
def update_stock(product_id):
    try:
        data = request.json
        added_qty = int(data.get("quantity", 0))

        if added_qty <= 0:
            return jsonify({"message": "Invalid quantity"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE products
            SET quantity = quantity + %s
            WHERE product_id = %s
        """, (added_qty, product_id))

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Stock updated successfully"})

    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route("/verify_product/<int:product_id>", methods=["GET"])
def verify_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT hash FROM products WHERE product_id=%s",(product_id,))
    product = cursor.fetchone()

    cursor.close()
    conn.close()

    if not product:
        return jsonify({"valid": False})

    valid = blockchain.verify_block(product["hash"])

    return jsonify({
        "product_id": product_id,
        "blockchain_valid": valid
    })

@app.route("/place_order", methods=["POST"])
def place_order():
    conn = None
    cursor = None

    try:
        data = request.json
        buyer_id = data["buyer_id"]
        product_id = data["product_id"]
        quantity = data["quantity"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check product
        cursor.execute(
            "SELECT price, quantity FROM products WHERE product_id = %s",
            (product_id,)
        )
        product = cursor.fetchone()

        if not product:
            return jsonify({"message": "Product not found"}), 404

        if quantity > product["quantity"]:
            return jsonify({"message": "Not enough stock"}), 400

        total_price = quantity * product["price"]

        # INSERT ORDER
        cursor.execute("""
            INSERT INTO orders (buyer_id, product_id, quantity, total_price, status, payment_status)
            VALUES (%s, %s, %s, %s, 'placed','pending')
        """, (buyer_id, product_id, quantity, total_price))

        order_id = cursor.lastrowid

        # UPDATE STOCK
        cursor.execute("""
            UPDATE products
            SET quantity = quantity - %s
            WHERE product_id = %s
        """, (quantity, product_id))

        conn.commit()

        return jsonify({"message": "Order placed successfully",
                        "order_id": order_id
                        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"message": f"Error placing order: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close() 


@app.route("/orders", methods=["GET"])
def get_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.order_id AS id,
            o.product_id,
            o.total_price AS totalPrice,
            o.status,
            p.name AS productName,
            b.name AS buyerName,
            f.name AS farmerName
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        JOIN users b ON o.buyer_id = b.user_id
        JOIN users f ON p.farmer_id = f.user_id
    """)

    orders = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(orders)
@app.route("/my_orders/<int:buyer_id>", methods=["GET"])
def get_my_orders(buyer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
                   o.order_id, 
                   o.quantity, 
                   o.total_price, 
                   o.status, 
                   o.payment_status,
                   o.order_date,
                   p.name AS product_name, 
                   u.name AS farmer_name,
                   u.user_id AS farmer_id
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        JOIN users u ON p.farmer_id = u.user_id
        WHERE o.buyer_id = %s
    """, (buyer_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(orders)

@app.route("/update-order-status/<int:order_id>", methods=["PUT"])
def update_order_status(order_id):
    data = request.json
    status = data.get("status")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET status = %s
        WHERE order_id = %s
    """, (status, order_id))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success":True,"message": "Order status updated"})

@app.route("/pay_order/<int:order_id>", methods=["POST"])
def pay_order(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Insert transaction record
        cursor.execute("""
            INSERT INTO transactions (order_id, payment_method, payment_status)
            VALUES (%s, %s, %s)
        """, (order_id, "Online", "Completed"))

        # Update order
        cursor.execute("""
            UPDATE orders
            SET payment_status='paid',
                status='accepted'
            WHERE order_id=%s
        """, (order_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Payment Completed"})

    except Exception as e:
        return jsonify({"message": str(e)}), 500
    
@app.route("/create_payment/<int:order_id>", methods=["POST"])
def create_payment(order_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT total_price
        FROM orders
        WHERE order_id = %s
    """, (order_id,))

    order = cursor.fetchone()

    if not order:
        return jsonify({"success": False, "message": "Order not found"}), 404

    payment = razorpay_client.order.create({
        "amount": int(order["total_price"] * 100),
        "currency": "INR",
        "payment_capture": 1,
        "notes": {
            "db_order_id": order_id
        }
    })

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "key": "rzp_test_SRtws3hBkoQHdH",
        "amount": payment["amount"],
        "currency": payment["currency"],
        "razorpay_order_id": payment["id"]
    })

@app.route("/verify_payment", methods=["POST"])
def verify_payment():
    data = request.json

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature
        })

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get original order id from receipt
        receipt_order_id = data.get("db_order_id")

        # Insert transaction
        cursor.execute("""
            INSERT INTO transactions 
            (order_id, payment_method, payment_status)
            VALUES (%s, %s, %s)
        """, (receipt_order_id, "UPI", "Completed"))

        # Update order
        cursor.execute("""
            UPDATE orders
            SET payment_status='paid',
                status='accepted'
            WHERE order_id=%s
        """, (receipt_order_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@app.route("/generate_invoice/<int:order_id>", methods=["GET"])
def generate_invoice(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.order_id, o.quantity, o.total_price,
               o.order_date, p.name AS product_name,
               u.name AS buyer_name
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        JOIN users u ON o.buyer_id = u.user_id
        WHERE o.order_id = %s
    """, (order_id,))

    order = cursor.fetchone()
    cursor.close()
    conn.close()

    if not order:
        return jsonify({"error": "Order not found"}), 404

    return jsonify(order)


@app.route('/get-delivery-orders', methods=['GET'])
def get_delivery_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.order_id,
            o.quantity,
            o.total_price,
            o.status,
            o.order_date,
            p.name AS product_name,
            f.name AS farmer_name,
            f.phone AS farmer_phone,
            f.address AS pickup_address,
            b.name AS buyer_name,
            b.phone AS buyer_phone,
            b.address AS delivery_address
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        JOIN users f ON p.farmer_id = f.user_id
        JOIN users b ON o.buyer_id = b.user_id
    """)

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(orders)

@app.route("/delivery_partners", methods=["GET"])
def get_delivery_partners():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id, name, phone, address
        FROM users
        WHERE role = 'delivery'
    """)

    partners = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(partners)


@app.route('/admin/stats', methods=['GET'])
def admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()['total_users']

    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()['total_products']

    cursor.execute("SELECT COUNT(*) AS total_orders FROM orders")
    total_orders = cursor.fetchone()['total_orders']

    return jsonify({
        "total_users": total_users,
        "total_products": total_products,
        "total_orders": total_orders
    })   

@app.route("/users", methods=["GET"])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT user_id AS id, name, email, role AS type
        FROM users
    """)

    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify(users)

@app.route("/add-feedback", methods=["POST"])
def add_feedback():
    try:
        data = request.get_json(force=True)

        buyer_id = data["buyer_id"]
        farmer_id = data["farmer_id"]
        rating = data["rating"]
        comment = data["comment"]
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO feedback (buyer_id, farmer_id, rating, comments)
            VALUES (%s, %s, %s, %s)
        """, (buyer_id, farmer_id, rating, comment))

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Feedback added"})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500
    
@app.route("/get-feedback/<int:farmer_id>", methods=["GET"])
def get_feedback(farmer_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT f.feedback_id, f.rating, f.comments, f.created_at,
                   u.name AS buyer_name
            FROM feedback f
            JOIN users u ON f.buyer_id = u.user_id   -- ✅ FIXED HERE
            WHERE f.farmer_id = %s
            ORDER BY f.created_at DESC
        """, (farmer_id,))

        feedbacks = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify(feedbacks)

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": str(e)}), 500
    
@app.route("/farmer-stats/<int:farmer_id>", methods=["GET"])
def farmer_stats(farmer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total Products
    cursor.execute("""
        SELECT COUNT(*) AS total_products
        FROM products
        WHERE farmer_id = %s
    """, (farmer_id,))
    total_products = cursor.fetchone()["total_products"]

    # Total Orders
    cursor.execute("""
        SELECT COUNT(*) AS total_orders
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE p.farmer_id = %s
    """, (farmer_id,))
    total_orders = cursor.fetchone()["total_orders"]

    # Total Revenue (ONLY delivered or paid)
    cursor.execute("""
        SELECT SUM(o.total_price) AS total_revenue
        FROM orders o
        JOIN products p ON o.product_id = p.product_id
        WHERE p.farmer_id = %s
        AND o.status IN ('delivered','paid')
    """, (farmer_id,))
    revenue_data = cursor.fetchone()
    total_revenue = revenue_data["total_revenue"] or 0

    # Average Rating
    cursor.execute("""
        SELECT AVG(rating) AS avg_rating, COUNT(*) AS
        total_reviews
        FROM feedback
        WHERE farmer_id = %s
    """, (farmer_id,))
    rating_data = cursor.fetchone()
    avg_rating = round(rating_data["avg_rating"],1) if rating_data["avg_rating"] else 0
    total_reviews = rating_data["total_reviews"]

    cursor.close()
    conn.close()

    return jsonify({
        "total_products": int(total_products),
        "total_orders": int(total_orders),
        "total_revenue": float(total_revenue),
        "avg_rating": float(avg_rating)
    })

if __name__ == "__main__":
    print(app.url_map)
    app.run(host='0.0.0.0', port=5000, debug=True)




