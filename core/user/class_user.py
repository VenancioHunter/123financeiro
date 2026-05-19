from config import db
from datetime import datetime

class User:

    def get_name(id):

        data = db.child("users").child(id).child("name").get().val()

        return data
    
    def get_users():

        users_data = db.child("users").get().val() or {}

        return users_data