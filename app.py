from flask import Flask, render_template,request, send_from_directory,redirect,url_for,make_response,request
from authentication import extract_credentials,validate_password,extract_credentialslogin
from pymongo import MongoClient
from db import db
import bcrypt
import hashlib
import secrets
import extra
import chats

app = Flask(__name__)

@app.after_request
def add_header(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.route('/')
def index():
    print("hello")
    auth_token = request.cookies.get("auth_token")

    username = None
    # checks if user is logged in
    if auth_token:
        log = True
        hashed_token = hashlib.sha256(auth_token.encode()).hexdigest()
        user = db.accounts.find_one({"token":hashed_token})
        if(user != None):
            username = user['username']
            # check for posts and load posts
            if db.posts is not None:  #if there is a database
                data = db.posts.find({})
                return render_template("index.html", content_type='text/html', logged_in=log, data=data, username=username)  
            else:
                return render_template("index.html", content_type='text/html', logged_in=log, username=username)
    else:
        log = False
    #for guest page, check for posts and loads them
    if db.posts is not None:  #if there is a database
        data = db.posts.find({})
        return render_template("index.html", content_type='text/html', logged_in=log, data=data)
    
    return render_template("index.html", content_type='text/html', logged_in=log)


#takes the user to the register form
@app.route("/register")
def registerPath():
    return render_template('register.html', content_type='text/html')

#takes the user to the login form
@app.route("/login")
def loginPath():
    return render_template('login.html', content_type='text/html')

#takes the user to the post form
@app.route("/post")
def postPath():
    auth_token = request.cookies.get("auth_token")
    
    # User must be logged in to post
    if auth_token:
        return render_template('post.html', content_type='text/html', logged_in=True)
    else:
        return redirect('/login')
    
@app.route('/send-post', methods=['POST'])
def posting():
    body = extra.escape_html(request.get_data(as_text=True))
    split = body.split('&', 1)
    t = extra.replace_encoded(split[0].split('=', 1)[1])
    q = extra.replace_encoded(split[1].split('=', 1)[1])
    auth_token = request.cookies.get("auth_token")
    username = "Guest" # If shows up as Guest (something is broken)
    if auth_token:
        hashed_token = hashlib.sha256(auth_token.encode()).hexdigest()
        user = db.accounts.find_one({"token":hashed_token})
        username = user['username']

    if db.posts is not None:
        if db.posts.find_one({}) is None: 
            db.posts.insert_one({'title': t, "question": q, "username": username, "post_id": 1, "liked_users": [], "like_count": 0})
        else:
            collections = list(db.posts.find({}))
            num = len(collections)
            db.posts.insert_one({'title': t, "question": q, "username": username, "post_id": num+1, "liked_users": [], "like_count": 0})

    return redirect('/')

@app.route('/like/<post_id>', methods=['POST'])
def like(post_id):
    auth_token = request.cookies.get("auth_token")
    # checks if user is logged in
    if auth_token:
        hashed_token = hashlib.sha256(auth_token.encode()).hexdigest()
        user = db.accounts.find_one({"token":hashed_token})
        username = user['username']
        
        dbPost = db.posts.find_one({'post_id': int(post_id)})
        if username in dbPost['liked_users']:    #check if the user has liked the post (liking again == not liking)
            arr = dbPost['liked_users']
            arr.remove(username)
            updateM = {
                "$set": {
                    'title': dbPost['title'], 
                    "question": dbPost["question"], 
                    "username": dbPost["username"], 
                    "post_id": dbPost["post_id"], 
                    "liked_users": arr, 
                    "like_count": len(arr)
                    }
            }
            db.posts.update_one({'post_id': int(post_id)}, updateM)
        else: # if they have not liked or have unliked,they can like the post
            arr = dbPost['liked_users']
            arr.append(username)
            updateM = {
                "$set": {
                    'title': dbPost['title'], 
                    "question": dbPost["question"], 
                    "username": dbPost["username"], 
                    "post_id": dbPost["post_id"], 
                    "liked_users": arr, 
                    "like_count": len(arr)
                }
            }
            db.posts.update_one({'post_id': int(post_id)}, updateM)
        return redirect('/')
    else:
        return redirect('/login')

# Register user
@app.route('/auth-register', methods=['POST'])
def register():
    username, password1, password2 = extract_credentials(request)
    if password1 != password2:
        return "The entered passwords do not match"
    
    if not validate_password(password1):
        return 'Password does not meet the requirements'
    
    user = db.accounts.find_one({'username': username})
    if user:
        return "Username is taken"
    
    # Generate a salt
    salt = bcrypt.gensalt()
    
    # Hash the password with the salt
    hashed_password = bcrypt.hashpw(password1.encode('utf-8'), salt)
    
    # Store the username, hashed password, and salt in the database
    
    #REMEMBER TO REMOVE PASSWORD FIELD WHEN FINAL SUBMISSION
    data = {"username": username, "hash": hashed_password, "salt": salt}
    db.accounts.insert_one(data)
    
    return redirect(url_for('loginPath'))

@app.route('/auth-login', methods=['POST'])
def login():
    username, password = extract_credentialslogin(request)

    # Retrieve user from database
    user = db.accounts.find_one({'username': username})

    if user:
        salt = user['salt']
        hash = bcrypt.hashpw(password.encode('utf-8'),salt)

        if(hash == user["hash"]):
            token = secrets.token_hex(16)
            hashed_token = hashlib.sha256(token.encode()).hexdigest()
            db.accounts.update_one({'username':username},{'$set':{'token':hashed_token}})

            # Create a response object
            resp = make_response(redirect('/'))  # Redirect to the homepage

            # Set the token as a cookie
            resp.set_cookie('auth_token', token, httponly=True, max_age=3600)  # Expires in 1 hour

            return resp

    return 'Invalid username or password'

@app.route("/logout", methods=["POST"])
def logout():
    token = request.cookies.get("auth_token")
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    
    db.accounts.update_one({"token": hashed_token},{"$unset":{"token":""}})

    resp = make_response(redirect('/'))

    resp.set_cookie('auth_token', '', expires=0)
    return resp

@app.route('/static/js/<path:filename>')
def js(filename):   
    return send_from_directory('static/js', filename, mimetype='text/javascript')

@app.route('/static/css/<path:filename>')
def css(filename):
    return send_from_directory('static/css', filename, mimetype='text/css')

@app.route('/static/image/<path:filename>')
def img(filename):
    return send_from_directory('static/image', filename, mimetype='image/png')



if __name__ == __name__:
    app.run(debug=True, host='0.0.0.0', port=8080)
