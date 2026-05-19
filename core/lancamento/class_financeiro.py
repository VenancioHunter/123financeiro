from config import db
import datetime
import pytz
from core.lancamento.functions import post_transaction_lancamentos, post_caixa
from core.user.class_user import User
from core.user.class_user_wallet import User_Wallet

class Financeiro:

    

    def post_transaction_credito_tecnico(date, amount, description, type, category, especie, destinatario, user, origem, id_origem):

    

        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        now_in_sao_paulo = datetime.datetime.now(sao_paulo_tz)
        timestamp = now_in_sao_paulo.timestamp()
        
        year = str(now_in_sao_paulo.year)
        month = f"{now_in_sao_paulo.month:02d}"
        day = f"{now_in_sao_paulo.day:02d}"

        contador = db.child("financeiro").child("contador_transactions").get().val()
        if contador is None:
            contador = 0

        # Incrementa
        novo_numero_transaction = contador + 1
        db.child("financeiro").child("contador_transactions").set(novo_numero_transaction)

        transation = {
                    'numero_transaction': novo_numero_transaction,
                    'origem': origem,
                    'id_origem': id_origem,
                    'user': user,
                    'timestamp' : timestamp,
                    'type': type,
                    'category': category,
                    'especie': especie,
                    'destinatario': destinatario,
                    'description': description,
                    'amount': amount
                }

        db.child("financeiro").child('transactions').child(year).child(month).child(day).child('transactions').push(transation)

        post_transaction_lancamentos(year=year, month=month, type=transation['type'], amount=amount)
        post_caixa(amount=amount, type=transation['type'])

    
    def post_programar_lancamento(date, data):

        try:
            date = datetime.datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."
        
        year = str(date.year)
        month = f"{date.month:02d}"
        
        db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).push(data)

    def post_confirmar_pagamento_programado(date, data):
    
        try:
            date = datetime.datetime.strptime(date, '%Y-%m-%d')
      
        except ValueError:
            return "Formato de data inválido."
        
        year = str(date.year)
        month = f"{date.month:02d}"

        
        db.child("financeiro").child('transactions_programadas').child('paid').child(year).child(month).push(data)

    
    def post_transaction_pendente( numero_os, id_os, os_city, os_date, date_payment, metodo_pagamento, valor_recebido, valor_liquido, taxa, outros_custos_service, observacoes_service, id_create_transaction_user, id_create_transaction_wallet):



        try:
            date = datetime.datetime.strptime(os_date, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        get_os = db.child("ordens_servico").child(os_city).child(year).child(month).child(day).child(id_os).get().val()
       
        nome_tecnico = User.get_name(get_os['tecnico_id'])
       
        nome_atendente = User.get_name(get_os['user_id'])
       
        porcentagem = User_Wallet.get_percentagem_tecnico(get_os['tecnico_id'])
        

        valor_tecnico = (float(valor_liquido) * float(porcentagem)) / 100
        valor_tecnico = "{:.2f}".format(float(valor_tecnico), 2)
   

        porcentagem_empresa = 100 - float(porcentagem)
   

        participacao_taxa_empresa = "{:.2f}".format((float(valor_liquido) * porcentagem_empresa) / 100)
       
        valor_empresa = "{:.2f}".format(float(participacao_taxa_empresa), 2)
      
        create_transation = {}

        create_transation = {
            'numero_os': numero_os,
            'id_os': id_os,
            'city_os': os_city,
            'date_os': os_date,
            'date_payment': date_payment,
            'client': get_os['name'],
            'client_phone': get_os['phone'],
            'service': get_os['service'],
            'tecnico': nome_tecnico,
            'tecnico_id': get_os['tecnico_id'],
            'atendente': nome_atendente,
            'atendente_id': get_os['user_id'],
            'orcamento': get_os['newprice'],
            'metodo_pagamento': metodo_pagamento,
            'valor_recebido': valor_recebido,
            'valor_liquido': valor_liquido,
            'valor_tecnico': valor_tecnico,
            'valor_empresa': valor_empresa,
            'taxa': taxa,
            'outros_custos_service': outros_custos_service,
            'observacoes_service': observacoes_service,
            'id_create_transaction_user': id_create_transaction_user,
            'id_create_transaction_wallet': id_create_transaction_wallet,
            }
        
        
        
        try:
            date = datetime.datetime.strptime(date_payment, '%Y-%m-%d')
        except ValueError:
            return "Formato de data inválido."

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"

        db.child("financeiro").child('transactions_pendentes').child(year).child(month).child(day).push(create_transation)

        return True
