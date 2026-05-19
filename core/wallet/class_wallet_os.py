from config import db
from datetime import datetime

class Wallet():

    def update_status_os(id, city, date, status_paymment):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        # Salva os dados no Firebase com o novo ID gerado automaticamente
        db.child("ordens_servico").child(city).child(year).child(month).child(day).child(id).update({"status_paymment": status_paymment})

        return True
    
    def create_paymment_success(data, date, city):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        result = db.child("wallet").child(city).child(year).child(month).child(day).child('transactions').child('success').push(data)

        return result['name']  # Retorna o ID gerado automaticamente

    def create_paymment_pendding(data, date, city):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        db.child("wallet").child(city).child(year).child(month).child(day).child('transactions').child('pendding').push(data)

    def get_pendding(city, date, id):
        pass