from config import db
from datetime import datetime

class User_Wallet:

    def create_transaction_success(data, city, date, id_tecnico):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        transation ={
            'numero_os': data['numero_os'],
            'os_id': data['os_id'],
            'os_date': data['os_date'],
            'method': data['method'],
            'amount': data['amount'],
            'taxa': data['taxa'],
            'valor_bruto': data['valor_bruto'],
            'outros_custos_service': data['outros_custos_service'],
            'observacoes_service': data['observacoes_service'],
        }

        # Salva os dados no Firebase com o novo ID gerado automaticamente
        result = db.child("users").child(id_tecnico).child('wallet').child('cities').child(city).child(year).child(month).child(day).child('transactions').child('success').push(transation)

        return result['name']  # Retorna o ID gerado automaticamente

    def create_costs(id, date, data):
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        db.child("users").child(id).child('wallet').child('costs').child(year).child(month).child(day).push(data)

    def verify_costs(id, date):

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        data = db.child("users").child(id).child('wallet').child('costs').child(year).child(month).child(day).get().val()

        if data is not None:
            return True
        else:
            return False
        
    def get_participation(id, data):

        try:
            data = datetime.strptime(data, '%Y-%m-%d')

        except:
            pass
        
        year = str(data.year)
        month = f"{data.month:02d}"
        day = f"{data.day:02d}"

        costs_porcentagem = f"users/{id}/wallet/costs/{year}/{month}/{day}"

        # Busca os dados no Firebase
        data1 = db.child(costs_porcentagem).get().val()

        if data1:  # Verifica se data1 não é None ou vazio
            # Itera sobre o OrderedDict para encontrar 'porcentagemTecnico'
            for key, value in data1.items():
                if 'porcentagemTecnico' in value:
                    return value['porcentagemTecnico']

    
        data = db.child("users").child(id).child("porcentagem").get().val()

        return data
    
    def get_percentagem_tecnico(id_tecnico):
        
        data = db.child("users").child(id_tecnico).child("porcentagem").get().val()
        
        return data