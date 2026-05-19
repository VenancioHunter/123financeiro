import os

import pyrebase

for proxy_key in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
):
    os.environ.pop(proxy_key, None)

db_link = "https://caca-vazamentos-default-rtdb.firebaseio.com"

firebase_config = {
    "apiKey": "AIzaSyDkdKimHiPbDJ82XtfO1bbJi7uQSTm5l04",
    "authDomain": "caca-vazamentos.firebaseapp.com",
    "databaseURL": "https://caca-vazamentos-default-rtdb.firebaseio.com",
    "projectId": "caca-vazamentos",
    "storageBucket": "caca-vazamentos.firebasestorage.app",
    "messagingSenderId": "984183601822",
    "appId": "1:984183601822:web:a8acc13e2312b6a615d98f",
}

firebase = pyrebase.initialize_app(firebase_config)
storage = firebase.storage()
auth = firebase.auth()
db = firebase.database()
