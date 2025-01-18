import os
from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import hashlib
from config import *
import datetime
import random
import bcrypt
import jwt
from werkzeug.utils import secure_filename
from flask_bcrypt import check_password_hash
from functools import wraps
from flask_cors import CORS

# Initiation Flask
app = Flask(__name__)
CORS(app)

# Load DB config
app.config.from_object(DevelopmentConfig)

# Key for JWT
app.config['SECRET_KEY'] = 'girlfriendsecretkey'

# File Upload Setting
app.config['UPLOAD_FOLDER'] = 'uploads/profile_pictures'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

mysql = MySQL(app)

def token_required(func):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return func(*args, **kwargs, id=data['id'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    wrapper.__name__ = func.__name__
    return wrapper

#Function Admin check
def is_admin(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (id, ))
    data = cursor.fetchone()

    if data['role'] == 1:
        return True
    else:
        return False


# Validation function method
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Generate unique number
def generate_unique_number():
    # Get time
    now = datetime.datetime.now()
    timestamp = now.strftime('%Y%m%d%H%M%S%f')

    # generate random number
    random_number = random.randint(1000, 9999)

    # Combine timestamp with random number
    unique_number = f"{timestamp}{random_number}"
    return unique_number

# Users
@app.route('/', methods=['GET'])
def home():
    return jsonify({'message': 'API RENTAL PACAR '})
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    #input validation
    if not all(k in data for k in ('username', 'email', 'age', 'height', 'mobile_phone', 'password')):
        return jsonify({'error': 'Incomplete Data !!'})
        
    user_id = generate_unique_number()
    username = data['username']
    email = data['email']
    age = data['age']
    height = data['height']
    phone = data['mobile_phone']
    password = data['password'].encode() #Encrypt Pass
    gender = data['gender']
    role = data['role']
    try:
        hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()

        if existing_user:
            if existing_user['username'] == username:
                return jsonify({'error': 'Username is already registered!!'})
            if existing_user['email'] == email:
                return jsonify({'error': 'Email is already registered!!'})
            
        cur.execute("INSERT INTO users VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s, %s)", (user_id, username, email, age, height, phone, hashed_password.decode(), gender, role))
        mysql.connection.commit()
        return jsonify({'message': 'Registrasion Succesfully!'}), 201
    except Exception as e:
        return jsonify({'error': 'An error occurred on the server!!', 'details': str(e)}), 500
    

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    
    #Input Validation
    if not all(k in data for k in ('username', 'password')):
        return jsonify({'error': 'Incomplete Data !!'}), 400

    username = data['username']
    password = data['password'].encode() 

    try:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT * FROM users WHERE username = %s", (username, ))
        user = cur.fetchone()
        id = user['id']
        if not user:
            return jsonify({'error': 'User not found!!'}), 404
        
        # Password verify
        hashed_password = user['password'].encode()
        if bcrypt.checkpw(password, hashed_password):
            # Generate JWT Token
            token = jwt.encode({
                'id': id,
                'username': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
            }, app.config['SECRET_KEY'], algorithm='HS256')

            return jsonify({'message': 'Login successfully !!', 'token': token}), 200
        else:
            return jsonify({'error': 'Wrong password !!'}), 401
    except Exception as e:
        return jsonify({'error': 'Internal server error !! ', 'details': str(e)}), 500
        
# Protected route untuk tes JWT
@app.route('/api/protected', methods=['GET'])
def protected(func):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')  # Ambil token dari header

        if not token:
            return jsonify({'error': 'Token not given !!'}), 403

        try:
            # Decode token
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return jsonify({'message': f'Hello, {data["username"]}!'}), 200
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired !!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is not valid !!'}), 401
    wrapper.__name__ = func.__name__
    return wrapper

@app.route('/api/edit-profile', methods=['PUT'])
@token_required
def edit_profile(id):
    if 'profile_picture' in request.files:
        file = request['profile_picture']
        if file and allowed_file(file.filename):
            # Keep filename safe
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Save file to folder
            file.save(file_path)
        else:
            return jsonify({'error' : 'Invalid file type !! '}), 400
    else:
        file_path = None
    
    data = request.json #get data from form
    new_username = data['username']
    new_email = data['email']
    new_age = data['age']
    new_height = data['height']
    new_phone = data['mobile_phone']

    print(new_username)

    if not new_username or not new_email or not new_age or not new_height or not new_phone:
        return jsonify({'error' : 'Incomplete data !! '}), 400
    
    cursor = mysql.connection.cursor()

    try:
        if file_path:
            cursor.execute(
                "UPDATE users SET username = %s, email = %s, age = %s, height = %s, mobile_phone = %s, profile_picture = %s WHERE id = %s", 
                (new_username, new_email, new_age, new_height, new_phone, file_path, id))
        else:
            cursor.execute(
                "UPDATE users SET username = %s, email = %s, age = %s, height = %s, mobile_phone = %s WHERE id = %s", 
                (new_username, new_email, new_age, new_height, new_phone, id))
        mysql.connection.commit()

        return jsonify({
            'message': 'Profile update successfully',
            'updated_username': new_username,
            'updated_email': new_email,
            'update_age': new_age,
            'update_height': new_height,
            'update_phone': new_phone,
            'update_picture': file_path
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# ADMIN DELETE User
@app.route('/api/admin/user/<string:user_id>', methods=['DELETE'])
@token_required
def admin_delete_user(id, user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (id, ))
        data = cursor.fetchone()

        if data['role'] == 1:
            cursor.execute("DELETE FROM orders WHERE user_id = %s", (user_id, ))
            mysql.connection.commit()

            cursor.execute("DELETE FROM user_package WHERE user_id = %s", (user_id, ))
            mysql.connection.commit()

            cursor.execute("DELETE FROM messages WHERE sender_id = %s OR recipient_id = %s", (user_id, user_id))
            mysql.connection.commit()

            cursor.execute("DELETE FROM rating WHERE user_id = %s OR gf_bf_id = %s", (user_id, user_id))
            mysql.connection.commit()

            cursor.execute("DELETE FROM users WHERE id = %s", (user_id, ))
            mysql.connection.commit()

            return jsonify({'message': 'User deleted successfully !! '}), 200
        else:
            return jsonify({'error': 'Bad request !! '}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        


@app.route('/api/change-password', methods=['PUT'])
@token_required
def change_password(id):
    data = request.json
    old_pass = data['old_password'].encode()
    new_pass = data['new_password'].encode()

    if not old_pass or not new_pass:
        return jsonify({'error': 'Both old and new passwords are required'}), 400
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (id, ))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found !! '}), 404
        
        db_pass = user['password'].encode()

        # Verify old pass
        if bcrypt.checkpw(old_pass, db_pass):
            hashed_password = bcrypt.hashpw(new_pass, bcrypt.gensalt())

            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (hashed_password.decode(), id)
            )
            mysql.connection.commit()
            return jsonify({'message': 'Password change successfully !! '}), 200
        else:
            return jsonify({'error': 'Old password is incorrect !! '}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()     

# 

# **** User Package ****
#CREATE User Package
@app.route('/api/user_package', methods=['POST'])
@token_required
def create_user_package(id):
    data = request.get_json()
    data_id = generate_unique_number()
    if not data.get('price') or not data.get('duration') or 'available' not in data:
        return jsonify({'error': 'Missing required fields'}), 400

    cursor = mysql.connection.cursor()
    try:
        # Cari user ID berdasarkan username
        cursor.execute("SELECT id FROM users WHERE id = %s", (id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({'error': 'User not found'}), 404

        user_id = user[0]  # Ambil user ID
        # Insert ke tabel user_package
        cursor.execute(
            """
            INSERT INTO user_package (id, user_id, price, duration, available)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (data_id, user_id, data['price'], data['duration'], data['available'])
        )
        mysql.connection.commit()
        return jsonify({'message': 'User package created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
# READ ALL User Package
@app.route('/api/user_package', methods=['GET'])
def get_user_package():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM user_package")
        user_package = cursor.fetchall()
        if not user_package:
            return jsonify({'message': 'Package Not Found !! '}), 400
        packages = []
        for package in user_package:
            packages.append({
                'id': package['id'],
                'user_id': package['user_id'],
                'price': package['price'],
                'duration': str(package['duration']),  # Ambil sebagai string waktu yang sudah disimpan
                'available': package['available']
            })
        return jsonify(packages), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# READ User Package BY Id
@app.route('/api/user_package/<string:id>', methods=['GET'])
def get_user_package_by_id(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM user_package WHERE id = %s", (id,))
        user_package = cursor.fetchone()

        if not user_package:
            return jsonify({'error': 'Package not found !! '}), 404
        package = {
            'id': user_package['id'],           # Indeks 0 adalah 'id'
            'user_id': user_package['user_id'],      # Indeks 1 adalah 'user_id'
            'price': user_package['price'],        # Indeks 2 adalah 'price'
            'duration': str(user_package['duration']),# Indeks 3 adalah 'duration', ubah ke string
            'available': user_package['available']     # Indeks 4 adalah 'available'
        }
        return jsonify(package), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# READ User Package by User
@app.route('/api/<string:username>/user_package')
def get_user_package_by_user(username):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username, ))
        data = cursor.fetchone()
        if not data:
            return jsonify({'error': 'User not found !! '}), 404
        
        user_id = data['id']
        cursor.execute("SELECT * FROM user_package WHERE user_id = %s", (user_id, ))
        user_package = cursor.fetchall()
        if not user_package:
            return jsonify({'message': 'Package not available for this user !! '}), 404
        packages = []
        for package in user_package:
            packages.append({
                'id': package['id'],
                'user_id': package['user_id'],
                'price': package['price'],
                'duration': str(package['duration']),  # Ambil sebagai string waktu yang sudah disimpan
                'available': package['available']
            })
        return jsonify(packages), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
# UPDATE User Package
@app.route('/api/user_package/<string:package_id>', methods=['PUT'])
@token_required
def update_user_package(id, package_id):
    data = request.json
    price = data['price']
    duration = data['duration']
    available = data['available']

    print(package_id)
    print(id)
    if not price or not duration or not available:
        return jsonify({'error': 'Incomplete data !! '}), 401
    
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute("SELECT * FROM user_package WHERE id = %s AND user_id = %s", (package_id, id))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Package not found !! '}), 404

        cursor.execute(
            "UPDATE user_package SET price = %s, duration = %s, available = %s WHERE id = %s AND user_id = %s",
            (price, duration, available, package_id, id)
        )
        mysql.connection.commit()
        return jsonify({'message': 'Data updated successfully !! '}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# DELETE User Package
@app.route('/api/user_package/<string:package_id>', methods=['DELETE'])
@token_required
def delete_user_package(id, package_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM orders WHERE package_id = %s", (package_id, ))
        mysql.connection.commit()

        cursor.execute("DELETE FROM user_package WHERE id = %s AND user_id = %s", (package_id, id))
        mysql.connection.commit()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Package not found !! '}), 404
        return jsonify({'message': 'User package deleted successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#ADMIN DELETE USER PACKAGE
@app.route('/api/admin/user_package/<string:package_id>', methods=['DELETE'])
@token_required
def admin_delete_user_package(id, package_id):
    if is_admin(id):
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("DELETE FROM orders WHERE package_id = %s", (package_id, ))
            mysql.connection.commit()

            cursor.execute("DELETE FROM user_package WHERE id = %s", (package_id, ))
            mysql.connection.commit()

            if cursor.rowcount == 0:
                return jsonify({'error': 'Package not found !! '}), 404
            return jsonify({'message': 'User package deleted successfully !! '}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
    else:
        return jsonify({'error': 'Bad request !! '}), 401
# **** RATING ****
#CREATE Rating
@app.route('/api/rating', methods=['POST'])
@token_required
def create_rating(id):
    rating_id = generate_unique_number()
    data = request.json
    gf_bf_id = data['gf_bf_id']
    user_id = id
    rate = data['rate']
    review = data['review']

    if not gf_bf_id or not user_id or not rate or not review:
        return jsonify({'error': 'incomplete data !! '}), 401
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM rating WHERE gf_bf_id = %s AND user_id = %s", (gf_bf_id, user_id))
        user = cursor.fetchone()
        if not user:
            cursor.execute("INSERT INTO rating VALUES (%s, %s, %s, %s, %s)", (rating_id, gf_bf_id, user_id, rate, review))
            mysql.connection.commit()
            return jsonify({'message': 'Data uploaded successfully !! '}), 200
        else:
            return jsonify({'message': 'You have already rated this !! '}), 401

        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#READ Rating
@app.route('/api/rating', methods=['GET'])
def read_rating():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM rating")
        data = cursor.fetchall()
        if not data:
            return jsonify({'message': 'Data is not available !! '}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# SUM Rating
@app.route('/api/sum-rating/<string:bf_gf_id>', methods=['GET'])
def sum_rating(bf_gf_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        cursor.execute("SELECT SUM(rate) AS total_rate, COUNT(rate) AS total_count FROM rating WHERE gf_bf_id = %s", (bf_gf_id, ))
        data = cursor.fetchone()
        print(data['total_rate'])

        if not data or data['total_count'] == 0:
            return jsonify({'message': 'No rates found for this ID.'}), 404
        
        # Get Mean
        total_rate = data['total_rate']
        total_count = data['total_count']

        average_rate = total_rate / total_count

        return jsonify({
            'total_rate': total_rate,
            'total_count': total_count,
            'average rate': round(average_rate, 2)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#READ Rating by  Gf Bf Id
@app.route('/api/rating/<string:id>', methods=['GET'])
def read_rating_by_id(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM rating WHERE gf_bf_id = %s", (id, ))
        data = cursor.fetchone()

        if not data:
            return jsonify({'message': 'Data is not available !! '}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# UPDATE Rating
@app.route('/api/rating/<string:rating_id>', methods=['PUT'])
@token_required
def update_rating(id, rating_id):
    data = request.json
    user_id = id
    rate = data['rate']
    review = data['review']

    if not user_id or not rate or not review:
        return jsonify({'error': 'Incomplete data !! '}), 401
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM rating WHERE id = %s AND user_id = %s", (rating_id, id))
        rating = cursor.fetchone()
        if not rating:
            return jsonify({'error': 'Data not found !! '}), 404
        
        cursor.execute("UPDATE rating SET rate = %s, review = %s", (rate, review))
        mysql.connection.commit()

        return jsonify({'message': 'Data updated successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# DELETE Rating
@app.route('/api/rating/<string:rating_id>', methods=['DELETE'])
@token_required
def delete_rating(id, rating_id):
    cursor = mysql.connection.cursor()

    try:
        cursor.execute("SELECT * FROM rating WHERE id = %s AND user_id = %s", (rating_id, id))
        data = cursor.fetchone()

        if not data:
            return jsonify({'error': 'Data not found !! '}), 400
        
        cursor.execute("DELETE FROM rating WHERE id = %s AND user_id = %s", (rating_id, id))
        mysql.connection.commit()

        return jsonify({'message': 'Data deleted successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# Admin delete rating
@app.route('/api/admin/rating/<string:rating_id>', methods=['DELETE'])
@token_required
def admin_delete_rating(id, rating_id):
    if is_admin(id):
        cursor = mysql.connection.cursor()

        try:
            cursor.execute("DELETE FROM rating WHERE id = %s", (rating_id, ))
            mysql.connection.commit()

            return jsonify({'message': 'Data deleted successfully !! '}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        finally:
            cursor.close()
    else:
        return jsonify({'error': 'Bad request !! '}), 401

# **** ORDERS ****
#CREATE Order
@app.route('/api/order', methods=['POST'])
@token_required
def create_order(id):
    order_id = generate_unique_number()
    data = request.json
    package_id = data['package_id']
    user_id = id
    total_price = data['total_price']
    status = data['status']

    if not package_id or not user_id or not total_price or not status:
        return jsonify({'error': 'Incomplete data !! '}), 401
    
    cursor = mysql.connection.cursor()

    try:
        cursor.execute("INSERT INTO orders VALUES (%s, %s, %s, %s, %s)", (order_id, package_id, user_id, total_price, status))
        mysql.connection.commit()

        return jsonify({'message': 'Data uploaded successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# GET ALL Orders
@app.route('/api/order', methods=['GET'])
def get_order():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders")
        data = cursor.fetchall()

        if not data:
            return jsonify({'message': 'Data not found !! '}), 404
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#GET Order by Id
@app.route('/api/order/<string:id>')
def get_order_by_id(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = %s", (id, ))
        data = cursor.fetchone()

        if not data:
            return jsonify({'message': 'Data not found !! '}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#GET Order by Package
@app.route('/api/package/order/<string:id>', methods=['GET'])
def get_order_by_package(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE package_id = %s", (id, ))
        data = cursor.fetchall()

        if not data:
            return jsonify({'message': 'Data not found !! '}), 404
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#GET Order by User
@app.route('/api/user/order')
@token_required
def get_order_by_user(id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE user_id = %s", (id, ))
        data = cursor.fetchall()

        if not data:
            return jsonify({'message': 'Data not found !! '}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

#UPDATE Order
@app.route('/api/order/<string:order_id>', methods=['PUT'])
@token_required
def update_order(id, order_id):
    data = request.json
    package_id = data['package_id']
    user_id = id
    total_price = data['total_price']
    status = data['status']

    if not package_id or not user_id or not total_price or not status:
        return jsonify({'error': 'Incomplete data !! '}), 404
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = %s AND user_id = %s", (order_id, id))
        order = cursor.fetchone()
        if not order:
            return jsonify({'error': 'Data not found !! '}), 404
        
        cursor.execute("UPDATE orders SET package_id = %s, user_id = %s, total_price = %s, status = %s WHERE id = %s AND user_id = %s", (package_id, user_id, total_price, status, order_id, id))
        mysql.connection.commit()
        return jsonify({'message': 'Data updated successfully !! '}), 200
    except Exception as e:
        return jsonify({'error', str(e)}), 500
    finally:
        cursor.close()

#DELETE Order
@app.route('/api/order/<string:order_id>', methods=['DELETE'])
@token_required
def delete_order(id, order_id):
    print(id)
    print(order_id)
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM orders WHERE id = %s AND user_id = %s", (order_id, id))
        data = cursor.fetchone()

        if not data:
            return jsonify({'message': 'Data not found !! '}), 404
        
        cursor.execute("DELETE FROM orders WHERE id = %s AND user_id = %s", (order_id, id))
        mysql.connection.commit()

        return jsonify({'message': 'Deleted data successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        cursor.close()
#ADMIN DELETE Order
@app.route('/api/admin/order/<string:order_id>', methods=['DELETE'])
@token_required
def admin_delete_order(id, order_id):
    if is_admin(id):
        cursor = mysql.connection.cursor()
        try:
            cursor.execute("DELETE FROM orders WHERE id = %s", (order_id, ))
            mysql.connection.commit()

            return jsonify({'message': 'Deleted data successfully !! '}), 200
        except Exception as e:
            return jsonify({'error': str(e)})
        finally:
            cursor.close()

# **** Message ****
#GET Message
@app.route('/api/message/<string:recipient_id>', methods=['GET'])
@token_required
def get_mesagge(id, recipient_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM messages WHERE sender_id = %s AND recipient_id = %s", (id, recipient_id))
        data = cursor.fetchall()

        if not data:
            return jsonify({'message': 'There is no chat yet !! '}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()

# CREATE Message
@app.route('/api/message', methods=['POST'])
@token_required
def create_message(id):
    message_id = generate_unique_number() #Generate random number for id
    data = request.json
    sender_id = id
    recipient_id = data['recipient_id']
    message = data['message']
    is_read = 1

    if not sender_id or not recipient_id or not message or not is_read:
        return jsonify({'error': 'Incomplete data !! '}), 401
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO messages VALUES (%s, %s, %s, %s, %s)", (message_id, sender_id, recipient_id, message, is_read))
        mysql.connection.commit()

        return jsonify({'message': 'Your message has been sent !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)})
    finally:
        cursor.close()
# DELETE Message
@app.route('/api/message/<string:message_id>', methods=['DELETE'])
@token_required
def delete_message(id, message_id):
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM messages WHERE id = %s AND sender_id = %s", (message_id, id))
        data = cursor.fetchone()

        if not data:
            return jsonify({'error': 'Data not found !! '}), 404
        cursor.execute("DELETE FROM messages WHERE id = %s", (message_id, ))
        mysql.connection.commit()

        return jsonify({'message': 'Message deleted successfully !! '}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()


if __name__ == '__main__':
    app.run(port=3001, debug=True)
    # app.run(debug=True)