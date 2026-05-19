from config import db
from datetime import datetime

class User_Wallet_Attendant:

    def create_transaction_credito(id_user, date, info):
        if float(info['price']) >= 1000.00:
            print(type(info['price']))
            print(info['price'])

            info["value"] = "30.00"
            info['type'] = "c"

        else:
            info["value"] = "2.50"
            info['type'] = "c"
        
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')
        year = str(date.year)
        month = f"{date.month:02d}"

        db.child('users').child(id_user).child('wallet').child('credit_for_servide').child(year).child(month).push(info)

    def create_transaction_debito(id_user, date, info):
        if float(info['price']) >= 1000.00:
            info["value"] = "30.00"
            info['type'] = "d"

        else:
            info["value"] = "2.50"
            info['type'] = "d"
            
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d')

        year = str(date.year)
        month = f"{date.month:02d}"

        db.child('users').child(id_user).child('wallet').child('credit_for_servide').child(year).child(month).push(info)

        

