from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from config import db, auth
from functools import wraps
from operator import itemgetter
from collections import defaultdict
from datetime import datetime
from core.financeiro.analytics import (
    MONTH_NAMES,
    build_system_notifications_context,
    build_profit_analysis_context,
    build_cashflow_context,
    build_dashboard_context,
    build_homepage_context,
    build_lancamentos_context,
    create_city,
    get_available_years,
    list_destinatarios,
    save_budget_entry,
)
from core.lancamento.class_financeiro import Financeiro
from core.tecnico.class_tecnico import Tecnico
from core.wallet.class_wallet_os import Wallet
from core.user.class_user_wallet import User_Wallet
app = Flask(__name__)
app.secret_key = 'secret'


@app.context_processor
def inject_system_notifications():
    if not session.get('user') or session.get('role') != 'admin':
        return {"system_notifications": {"has_notifications": False, "total_count": 0}}

    return {"system_notifications": build_system_notifications_context()}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = user['localId']
            session['email'] = email

            user_data = db.child("users").child(user['localId']).get().val()
            session['role'] = user_data.get('role', 'user')
            session['name'] = user_data.get('name')
            
            if session['role'] == 'admin':
                return redirect(url_for('homepage'))
        except:
            return "Falha no login"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('email', None)
    return redirect(url_for('login'))

def check_roles(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user' not in session:
                return redirect(url_for('login'))
            user_role = db.child("users").child(session['user']).get().val().get('role')  # type: ignore
            if user_role not in allowed_roles:
                return "Acesso negado"
            return f(*args, **kwargs)

        return decorated_function

    return decorator

@app.route('/')
@check_roles(['admin'])
def homepage():
    if 'user' not in session:
        return redirect(url_for('login'))
    user_email = session.get('email', 'Usuario')
    return render_template('index.html', **build_homepage_context(user_email))
    user_email = session.get('email', 'Usuário')
    return render_template('index.html', user_email=user_email)

def convert_monetary_value(value_str):
    # Verifique se o valor já está no formato desejado
    if '.' in value_str and ',' not in value_str:
        # Retorne o valor como está, pois já está no formato correto
        return value_str

    # Se não estiver no formato desejado, faça a substituição necessária
    clean_value = value_str.replace('.', '').replace(',', '.')

    return clean_value

@app.route('/lancamentos', methods=['GET'])
@check_roles(['admin'])
def lancamentos():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Captura o mês e o ano selecionados no formulário
    hoje = datetime.now()
    mes = request.args.get('mes', default=hoje.month, type=int)
    ano = request.args.get('ano', default=hoje.year, type=int)
    return render_template('lancamentos.html', **build_lancamentos_context(ano, mes))

    # Supondo que você já tenha a função que busca as transações do Firebase
    transactions_list = get_transactions_by_month(ano, mes)  # Retorna as transações do mês selecionado

    caixa = db.child("financeiro").child('caixa').get().val()

    saldo = {}
    receita = 0
    despesas = 0

    destinatarios = db.child("financeiro").child('destinarios').get().val()

    for day in transactions_list:
        for id in transactions_list[day]['transactions']:
            amount = float(transactions_list[day]['transactions'][id]['amount'])  # Converter para float
            if transactions_list[day]['transactions'][id]['type'] == 'c':
                saldo[day] = saldo.get(day, 0) + amount
                receita += amount
            else:
                saldo[day] = saldo.get(day, 0) - amount
                despesas += amount
    
    dias_ordenados = sorted(saldo.keys())  # Ordena os dias em ordem crescente

    for i in range(1, len(dias_ordenados)):
        dia_anterior = dias_ordenados[i - 1]
        dia_atual = dias_ordenados[i]
        saldo[dia_atual] += (saldo[dia_anterior])      

    resultado = "{:.2f}".format(receita - despesas)


    # Passar lista de meses e anos para o template para popular o select
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    anos = [2026]  # Pode expandir essa lista conforme necessário

    return render_template('lancamentos.html', transactions=transactions_list, ano=ano, mes=mes, saldo=saldo, receita="{:.2f}".format(receita), despesas="{:.2f}".format(despesas), resultado=resultado, meses=meses, anos=anos, destinatarios=destinatarios, caixa=caixa)

def get_transactions_by_month(year, month):
    transactions_path = f"financeiro/transactions/{year}/{int(month):02}"
    month_transactions_data = db.child(transactions_path).get().val() or {}
    return month_transactions_data

# Função para exibir transações formatadas (por exemplo, em HTML)
def display_transactions(transactions):
    for transaction in transactions:
        day = transaction['day']
        description = transaction['description']
        amount = float(transaction['amount'])
        trans_type = transaction['type']  # 'c' para crédito, 'd' para débito
        
        # Formatação de débito/crédito
        if trans_type == 'c':
            amount_display = f"<span style='color: green;'>{amount:.2f}</span>"
        else:
            amount_display = f"<span style='color: red;'>-{amount:.2f}</span>"
        
        # Exibir os dados
        print(f"Dia: {day} - {description} - {amount_display}")


@app.route('/post_lancamento', methods=['POST', 'GET'])
def post_lancamento():

    user = session['name']
    id_origem = session['user']
    
    origem = (request.form.get('origem') or '').strip()
    type = (request.form.get('typeTransaction') or '').strip().lower()
    date = request.form.get('date')
    amount = convert_monetary_value(request.form.get('amount'))
    category = (request.form.get('categoria') or 'Sem categoria').strip().title()
    especie = (request.form.get('especie') or '').strip().title()
    destinatario = (request.form.get('destinatario') or '').strip()
    description = (request.form.get('descricao') or '').strip()

    Financeiro.post_transaction_credito_tecnico(date=date, type=type, amount=amount, category=category, description=description, especie=especie, destinatario=destinatario, user=user, origem=origem, id_origem=id_origem)

    return redirect(url_for('lancamentos'))

@app.route('/cadastrar_destinatario', methods=['POST', 'GET'])
def cadastrar_destinatario():
    name = request.form.get('namedestinatario').title()

    db.child("financeiro").child('destinarios').push(name)

    return redirect(url_for('lancamentos'))

@app.route('/delete_transaction', methods=['POST', 'GET'])
def delete_transaction():
    date = request.form.get('deleteDate')
    id_transaction = request.form.get('deleteTransactionId')

    try:
        
        date = datetime.strptime(date, '%Y-%m-%d')

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"
    
    except ValueError:
            return "Formato de data inválido."
        
    

    transaction =  dict(db.child("financeiro").child('transactions').child(year).child(month).child(day).child('transactions').child(id_transaction).get().val())

    get_caixa = db.child("financeiro").child('caixa').get().val()


    if transaction['type'] == 'c':

        get_credito = db.child("financeiro").child('lancamentos').child(year).child(month).child('receita').get().val() or 0
        valor_atualizado = "{:.2f}".format(float(get_credito) - float(transaction['amount']))
        
        db.child("financeiro").child('lancamentos').child(year).child(month).child('receita').set(valor_atualizado)

        caixa = "{:.2f}".format(float(get_caixa) - float(transaction['amount']))

    else:
        get_credito = db.child("financeiro").child('lancamentos').child(year).child(month).child('despesas').get().val() or 0
        valor_atualizado = "{:.2f}".format(float(get_credito) + float(transaction['amount']))
        
        db.child("financeiro").child('lancamentos').child(year).child(month).child('despesas').set(valor_atualizado)

        caixa = "{:.2f}".format(float(get_caixa) + float(transaction['amount']))
    
    db.child("financeiro").child('caixa').set(caixa)

    db.child("financeiro").child('transactions').child(year).child(month).child(day).child('transactions').child(id_transaction).remove()

    return redirect(url_for('lancamentos'))


@app.route('/novo_lancamento', methods=['GET'])
@check_roles(['admin'])
def novo_lancamento():
    if 'user' not in session:
        return redirect(url_for('login'))
    destinatarios = list_destinatarios()
    return render_template('novo_lancamento.html', destinatarios=destinatarios)

    destinatarios = db.child("financeiro").child('destinarios').get().val()


    return render_template('novo_lancamento.html', destinatarios=destinatarios)

@app.route('/profile_user/<id>', methods=['GET', 'POST'])
@check_roles(['admin'])
def profile_user(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    name = db.child("users").child(id).child('name').get().val()

    cities = db.child('users').child(id).child('cities').get().val() or 0
    print(cities)


    return render_template('profile_user.html', name=name, cities=cities)

@app.route('/lancamento_programado', methods=['GET', 'POST'])
@check_roles(['admin'])
def lancamento_programado():
    if 'user' not in session:
        return redirect(url_for('login'))

    hoje = datetime.now()
    anos = get_available_years(reference_year=hoje.year)
    anos = sorted(set(anos + [hoje.year, hoje.year + 1]))
    destinatarios = list_destinatarios()
    return render_template(
        'lancamento_programado.html',
        destinatarios=destinatarios,
        anos=anos,
        meses=MONTH_NAMES,
        ano_atual=hoje.year,
        mes_atual=f"{hoje.month:02d}",
    )
    
    destinatarios = db.child("financeiro").child('destinarios').get().val()

    return render_template('lancamento_programado.html', destinatarios=destinatarios)

@app.route('/post_novo_lancamento_programado', methods=['POST'])
def receber_lancamento():
    # Captura os dados do formulário
    type = request.form.get('typeTransaction')
    origem = request.form.get('origem')
    amount = request.form.get('amount')
    date = request.form.get('date')
    category = request.form.get('categoria')
    especie = request.form.get('especie')
    destinatario = request.form.get('destinatario')
    description = request.form.get('descricao')
    
    data = {
        'origem': origem,
        'type': type,
        'category': category.title(),
        'especie': especie.title(),
        'destinatario': destinatario,
        'description': description,
        'vencimento': date,
        'amount': convert_monetary_value(amount)    
    }
    
    Financeiro.post_programar_lancamento(date=date, data=data)
    
    # Retorne uma resposta JSON para indicar sucesso
    return jsonify({"message": "Lançamento recebido com sucesso!"}), 200


@app.route('/get_transactions_pendding/<ano>/<mes>')
def get_transactions_pendding(ano, mes):
    # Pega as transações do Firebase usando o ano e o mês
    transactions = db.child("financeiro").child('transactions_programadas').child('pedding').child(ano).child(mes).get().val()
    
    # Converte OrderedDict para lista de dicionários
    transactions_list = []
    if transactions:
        for key, value in transactions.items():
            transaction = value
            transaction['id'] = key
            transactions_list.append(transaction)
        
        # Ordena a lista de transações pela data de vencimento em ordem crescente
        transactions_list = sorted(
            transactions_list,
            key=lambda x: datetime.strptime(x['vencimento'], '%Y-%m-%d') if 'vencimento' in x and x['vencimento'] else datetime.min
        )

    # Retorna em formato JSON
    return jsonify(transactions_list)


@app.route('/post_confirmar_pagamento_programado', methods=['POST'])
def post_confirmar_pagamento_programado():
    # Captura os dados do formulário
    id = request.form.get('confirmarPagamentId')
    data_vencimento = request.form.get('dataVencimento')
    tipo_pagamento = request.form.get('pagamentototalparcial')
    amount = convert_monetary_value(request.form.get('newamount'))
    date_paymment = request.form.get('newdate')

    try:
        date = datetime.strptime(data_vencimento, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year = str(date.year)
    month = f"{date.month:02d}"

    transaction = db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).child(id).get().val()
    
    transaction['datapagamento'] = date_paymment
    transaction['valorpago'] = amount
    transaction['valororiginal'] = transaction.get('amount')

    base_description = (transaction.get('description') or '').strip()
    description_total = f"Baixa programada: {base_description}" if base_description else "Baixa programada"
    description_partial = f"Baixa parcial programada: {base_description}" if base_description else "Baixa parcial programada"
    if tipo_pagamento == 'total':
        transaction['parcial'] = False
        transaction['saldorestante'] = "0.00"
        
        Financeiro.post_transaction_credito_tecnico(date=date_paymment, type=transaction['type'], amount=amount, category=transaction['category'], description=description_total, especie=transaction['especie'], destinatario=transaction['destinatario'], user=session['name'], origem=transaction['origem'], id_origem='')
        
        Financeiro.post_confirmar_pagamento_programado(date=date_paymment, data=transaction)

        transaction = db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).child(id).remove()
    
    else:
        amount_parcial = "{:.2f}".format(float(transaction['amount']) - float(amount))
        
        Financeiro.post_transaction_credito_tecnico(
            date=date_paymment,
            type=transaction['type'],
            amount=amount,
            category=transaction['category'],
            description=description_partial,
            especie=transaction['especie'],
            destinatario=transaction['destinatario'],
            user=session['name'],
            origem=transaction['origem'],
            id_origem='',
        )

        db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).child(id).child('amount').set(amount_parcial)

        db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).child(id).child('parcial').set(True)

        transaction['parcial'] = True
        transaction['saldorestante'] = amount_parcial
        Financeiro.post_confirmar_pagamento_programado(date=date_paymment, data=transaction)
    
    # Retorne uma resposta JSON para indicar sucesso
    return jsonify({"message": "Lançamento recebido com sucesso!"}), 200


@app.route('/get_transactions_paid/<ano>/<mes>')
def get_transactions_paid(ano, mes):
    # Pega as transações do Firebase usando o ano e o mês
    transactions = db.child("financeiro").child('transactions_programadas').child('paid').child(ano).child(mes).get().val()
    
    # Converte OrderedDict para lista de dicionários
    transactions_list = []
    if transactions:
        for key, value in transactions.items():
            transaction = value
            transaction['id'] = key
            transactions_list.append(transaction)
        
        # Ordena a lista de transações pela data de vencimento em ordem crescente
        transactions_list = sorted(
            transactions_list,
            key=lambda x: datetime.strptime(x['vencimento'], '%Y-%m-%d') if 'vencimento' in x and x['vencimento'] else datetime.min
        )

    # Retorna em formato JSON
    return jsonify(transactions_list)


@app.route('/delete_transaction_programada/<id>', methods=['DELETE'])
def delete_transaction_programada(id):
    # Captura `year` e `month` dos parâmetros de consulta

    date = request.args.get('date')
    
    try:
        date = datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year = str(date.year)
    month = f"{date.month:02d}"
    
    try:

        db.child("financeiro").child('transactions_programadas').child('pedding').child(year).child(month).child(id).remove()

        return jsonify({'success': True, 'message': 'Transação cancelada com sucesso'}), 200
    except Exception as e:
        print(f"Erro ao deletar transação: {e}")
        return jsonify({'error': 'Erro ao cancelar a transação'}), 500
    
@app.route('/transacao_pendente', methods=['GET', 'POST'])
@check_roles(['admin'])
def transacao_pendente():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    pendentes = {}
    data = db.child("financeiro").child("transactions_pendentes").get().val() or {}

    for ano, meses in data.items():
        for mes, dias in meses.items():
            for dia, transacoes in dias.items():
                for pendente_id, pendente in transacoes.items():
                    pendentes[pendente_id] = {
                        **pendente,
                        "ano": ano,
                        "mes": mes,
                        "dia": dia,
                        "id": pendente_id
                    }
    return render_template('transacao_pendente.html', pendentes=pendentes)


@app.route('/post_transacao_pendente', methods=['POST', 'GET'])
def post_transacao_pendente():

    dados = request.get_json()
    print(dados)
    total_empresa = dados.get("total_empresa")
    itens = dados.get("itens", [])
    
    user = session['name']
    id_origem = itens[0]['tecnico_id']
    
    origem = itens[0]['tecnico_nome']
    
    type = "c"
    
    amount = "{:.2f}".format(total_empresa, 2)
    
    category = "Serviço"
    #especie_method = request.form.get('especie').title()
    especie = f'Remessa PIX'
    destinatario = "123 Caça Vazamentos"
    
    lista_os = [item['numero_os'] for item in itens]
    lista_numeros_os = ", ".join(lista_os)
    #taxa = request.form.get('taxa')
    description = f'Pagamento referente às OSs: {lista_numeros_os}.'

    agora = datetime.now()
    
    Financeiro.post_transaction_credito_tecnico(date=agora, type=type, amount=amount, category=category, description=description, especie=especie, destinatario=destinatario, user=user, origem=origem, id_origem=id_origem)

    id_transaction = itens[0]['id_transaction']
    

     
    for item in itens:
        date = item['date_payment']
        
        try:
            date = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
                return "Formato de data inválido."
                
        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"
            
        get_service_pedente = db.child("financeiro").child("transactions_pendentes").child(year).child(month).child(day).child(item['id_transaction']).get().val()
        db.child("financeiro").child("transactions_confirmadas").child(year).child(month).child(day).push(get_service_pedente)
        db.child("financeiro").child("transactions_pendentes").child(year).child(month).child(day).child(item['id_transaction']).remove()

        
    return True


@app.route('/transacoes_confirmadas', methods=['GET', 'POST'])
@check_roles(['admin'])
def transacoes_confirmadas():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    pendentes = {}
    data = db.child("financeiro").child("transactions_confirmadas").get().val() or {}

    for ano, meses in data.items():
        for mes, dias in meses.items():
            for dia, transacoes in dias.items():
                for pendente_id, pendente in transacoes.items():
                    pendentes[pendente_id] = {
                        **pendente,
                        "ano": ano,
                        "mes": mes,
                        "dia": dia,
                        "id": pendente_id
                    }
    return render_template('transacoes_confirmadas.html', pendentes=pendentes)


@app.route("/cancel_transaction_pendding", methods=["POST"])
def cancel_transaction_pendding():
    data = request.get_json()
    transaction_id = data.get("id")
    date_payment = data.get("date_payment")

    try:
        date = datetime.strptime(date_payment, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year = str(date.year)
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"

    data = db.child("financeiro").child("transactions_pendentes").child(year).child(month).child(day).child(transaction_id).get().val()

    id_os = data.get("id_os")
    city_os = data.get("city_os")
    date_os = data.get("date_os")
    tecnico_id = data.get("tecnico_id")
    id_create_transaction_user = data.get("id_create_transaction_user")
    id_create_transaction_wallet = data.get("id_create_transaction_wallet")


    try:
        date = datetime.strptime(date_os, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year_os = str(date.year)
    month_os = f"{date.month:02d}"
    day_os = f"{date.day:02d}"



    try:

        db.child("ordens_servico").child(city_os).child(year_os).child(month_os).child(day_os).child(id_os).child('status_paymment').remove()

        db.child("users").child(tecnico_id).child('wallet').child('cities').child(city_os).child(year).child(month).child(day).child('transactions').child('success').child(id_create_transaction_user).remove()

        db.child("wallet").child(city_os).child(year).child(month).child(day).child('transactions').child('success').child(id_create_transaction_wallet).remove()

        db.child("financeiro").child("transactions_pendentes").child(year).child(month).child(day).child(transaction_id).remove()

        print(f"ID da transação a ser deletada: {transaction_id}")
        print(f"Data de pagamento associada: {date_payment}")
        print(city_os)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    

@app.route("/cancel_transaction_confirmadas", methods=["POST"])
def cancel_transaction_confirmadas():
    data = request.get_json()
    transaction_id = data.get("id")
    date_payment = data.get("date_payment")

    try:
        date = datetime.strptime(date_payment, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year = str(date.year)
    month = f"{date.month:02d}"
    day = f"{date.day:02d}"

    data = db.child("financeiro").child("transactions_confirmadas").child(year).child(month).child(day).child(transaction_id).get().val()

    id_os = data.get("id_os")
    city_os = data.get("city_os")
    date_os = data.get("date_os")
    tecnico_id = data.get("tecnico_id")
    id_create_transaction_user = data.get("id_create_transaction_user")
    id_create_transaction_wallet = data.get("id_create_transaction_wallet")


    try:
        date = datetime.strptime(date_os, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."
            
    year_os = str(date.year)
    month_os = f"{date.month:02d}"
    day_os = f"{date.day:02d}"



    try:

        db.child("ordens_servico").child(city_os).child(year_os).child(month_os).child(day_os).child(id_os).child('status_paymment').remove()

        db.child("users").child(tecnico_id).child('wallet').child('cities').child(city_os).child(year).child(month).child(day).child('transactions').child('success').child(id_create_transaction_user).remove()

        db.child("wallet").child(city_os).child(year).child(month).child(day).child('transactions').child('success').child(id_create_transaction_wallet).remove()

        db.child("financeiro").child("transactions_confirmadas").child(year).child(month).child(day).child(transaction_id).remove()

        print(f"ID da transação a ser deletada: {transaction_id}")
        print(f"Data de pagamento associada: {date_payment}")
        print(city_os)

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/ordens_servico', methods=['GET', 'POST'])
@check_roles(['admin'])
def ordens_servico():
    if 'user' not in session:
        return redirect(url_for('login'))
    

    return render_template('ordens_servico.html')

@app.route("/buscar_ordens", methods=["POST"])
@check_roles(['admin'])
def buscar_ordens():
    data = request.get_json()
    ano = str(data.get("ano"))
    mes = f"{int(data.get('mes')):02d}"

    ordens = []
    tecnicos_cache = {} 

    try:
        # Buscar em todas as cidades (ativas)
        cidades_ativas = db.child("ordens_servico").get()
        if cidades_ativas.each():
            for cidade in cidades_ativas.each():
                cidade_nome = cidade.key()
                dados_mes = db.child("ordens_servico").child(cidade_nome).child(ano).child(mes).get()
                if dados_mes.each():
                    for dia in dados_mes.each():
                        for chave, item in dia.val().items():
                            item["status"] = item.get("status_paymment", "aguardando")
                            item["cidade"] = cidade_nome
                            item["city"] = cidade_nome
                            item["id_os"] = chave
                            
                            tecnico_id = item.get("tecnico_id")
                            if tecnico_id:
                                # Se ainda não está no cache, busca no servidor
                                if tecnico_id not in tecnicos_cache:
                                    tecnico_data = db.child("users").child(tecnico_id).child("name").get().val()
                                    tecnicos_cache[tecnico_id] = tecnico_data
                                # adiciona o nome do técnico ao item
                                item["tecnico_nome"] = tecnicos_cache[tecnico_id]

                            ordens.append(item)

        # Buscar em todas as cidades (canceladas)
        cidades_canceladas = db.child("canceled_services").get()
        if cidades_canceladas.each():
            for cidade in cidades_canceladas.each():
                cidade_nome = cidade.key()
                dados_mes = db.child("canceled_services").child(cidade_nome).child(ano).child(mes).get()
                if dados_mes.each():
                    for dia in dados_mes.each():
                        for chave, item in dia.val().items():
                            
                            item["status"] = "cancelada"
                            item["cidade"] = cidade_nome
                            item["city"] = cidade_nome
                            item["id_os"] = chave
                          

                            tecnico_id = item.get("tecnico_id")
                            if tecnico_id:
                                # Se ainda não está no cache, busca no servidor
                                if tecnico_id not in tecnicos_cache:
                                    tecnico_data = db.child("users").child(tecnico_id).child("name").get().val()
                                    tecnicos_cache[tecnico_id] = tecnico_data
                                # adiciona o nome do técnico ao item
                                item["tecnico_nome"] = tecnicos_cache[tecnico_id]

                            ordens.append(item)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

    return jsonify({"success": True, "ordens": ordens})


@app.route('/finalizar_os', methods=['POST'])
@check_roles(['admin'])
def finalizar_os():
    # Recebe os dados enviados pelo formulário
    data = request.json
    
    # Inicializa as variáveis de categorização
    status_pagamento = None
    detalhes_pagamento = {}
    numero_os = data.get('os_numero')
    os_id = data.get('os_id')
    os_city = data.get('os_city')
    os_date = data.get('os_date')
    dt = datetime.strptime(os_date, "%Y-%m-%d %H:%M")
    os_date = dt.strftime("%Y-%m-%d")
    os_id_tecnico = data.get('os_id_tecnico')

    os_value_service = convert_monetary_value(data.get('os_value_service'))
    os_type_service = data.get('os_type_serve')
    taxa = convert_monetary_value(data.get('taxa') or "0.00")
    outros_custos_service = convert_monetary_value(data.get('outrosCustosService') or "0.00")
    observacoes_service = data.get('observacaoService') or ""
    
    create_paymment = {}

    '''# Tenta converter a nova data para ano, mês e dia
    try:
            date_firebase = datetime.strptime(os_date, '%Y-%m-%d')
    except ValueError:
            return "Formato de data inválido."

    year = str(date_firebase.year)
    month = f"{date_firebase.month:02d}"
    day = f"{date_firebase.day:02d}"'''

    if os_type_service == 'Retorno' or os_type_service == 'retorno':

        try:
            Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment="recebido")

        except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400

    else:
        if data.get('statusPaymment') == 'received':
            
            # Filtra os dados e categoriza
            if data.get("method") in ["pix", "dinheiro"]:
                # Pagamentos recebidos
                status_pagamento = "recebido"
                detalhes_pagamento["valor"] = data.get("amount")
                detalhes_pagamento["metodo"] = data.get("method")
                name = session['name']
                method_payment = data.get("method")

                amount = "{:.2f}".format(float(convert_monetary_value(data.get('amount'))) - (float(convert_monetary_value(taxa)) + float(convert_monetary_value(outros_custos_service))))
                
                amount_financeiro = convert_monetary_value(data.get('amount'))
             
                create_paymment ={
                    'os_id': os_id,
                    'os_date': os_date,
                    'tecnico_id': os_id_tecnico,
                    'method': data.get('method'),
                    'amount': amount,
                    'taxa': taxa,
                    'outros_custos_service': outros_custos_service,
                    'observacoes_service': observacoes_service,
                    'numero_os': numero_os,
                    'valor_bruto': os_value_service,
                }

                try: 

                    id_create_transaction_wallet = Wallet.create_paymment_success(data=create_paymment, date=os_date, city=os_city)
                    
                    Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment=status_pagamento)

                    id_create_transaction_user = User_Wallet.create_transaction_success(data=create_paymment, date=os_date, city=os_city, id_tecnico=os_id_tecnico)
                  
                    Financeiro.post_transaction_pendente( numero_os=numero_os, id_os=os_id, os_city=os_city, os_date=os_date, date_payment=os_date, metodo_pagamento=method_payment, valor_recebido=amount_financeiro, valor_liquido=amount, taxa=taxa, outros_custos_service=outros_custos_service,observacoes_service=observacoes_service, id_create_transaction_user=id_create_transaction_user, id_create_transaction_wallet=id_create_transaction_wallet)
                  
                    #Financeiro.post_transaction_credito_tecnico(user=session['name'], date=os_date, amount=amount_financeiro, description=f'', method_payment=method_payment, origem=name, destinatario='', id_origem=os_id_tecnico)
                    
                    #if taxa != "0.00":
                        #taxa = "{:.2f}".format(float(taxa), 2)
                        
                        #Financeiro.post_transaction_debito(user=session['name'], date=os_date, amount=taxa, description=f'', category='financeiro', especie=f'Taxa - {method_payment}', origem=name, destinatario='', id_origem=os_id_tecnico)
                            
                except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400

            
            elif data.get("method") == "cartao":
                status_pagamento = "recebido"
                detalhes_pagamento["valor"] = data.get("cardValor")
                detalhes_pagamento["parcelas"] = data.get("installments")


                amount = "{:.2f}".format(float(convert_monetary_value(data.get('cardValor'))) - (float(convert_monetary_value(taxa)) + float(convert_monetary_value(outros_custos_service))))
                amount_financeiro = convert_monetary_value(data.get('cardValor'))
                name = session['name']
                method_payment = data.get("method")

                create_paymment ={
                    'os_id': os_id,
                    'os_date': os_date,
                    'tecnico_id': os_id_tecnico,
                    'method': data.get('method'),
                    'amount': amount,
                    'installments': data.get('installments'),
                    'taxa': taxa,
                    'outros_custos_service': outros_custos_service,
                    'observacoes_service': observacoes_service,
                    'numero_os': numero_os,
                    'valor_bruto': os_value_service,
                }

                try:

                    
                    id_create_transaction_wallet = Wallet.create_paymment_success(data=create_paymment, date=os_date, city=os_city)

                    Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment=status_pagamento)

                    id_create_transaction_user = User_Wallet.create_transaction_success(data=create_paymment, date=os_date, city=os_city, id_tecnico=os_id_tecnico)

                    Financeiro.post_transaction_pendente( numero_os=numero_os, id_os=os_id, os_city=os_city, os_date=os_date, date_payment=os_date, metodo_pagamento=method_payment, valor_recebido=amount_financeiro, valor_liquido=amount, taxa=taxa, outros_custos_service=outros_custos_service,observacoes_service=observacoes_service, id_create_transaction_user=id_create_transaction_user, id_create_transaction_wallet=id_create_transaction_wallet)

                    
                    #Financeiro.post_transaction_credito_tecnico(user=session['name'], date=os_date, amount=amount_financeiro, description=f'', method_payment=method_payment, origem=name, destinatario='', id_origem=os_id_tecnico)

                    #if taxa != "0.00":
                        #taxa = "{:.2f}".format(float(taxa), 2)

                        #Financeiro.post_transaction_debito(user=session['name'], date=os_date, amount=taxa, description=f'', category='financeiro', especie=f'Taxa - {method_payment}', origem=name, destinatario='', id_origem=os_id_tecnico)

                except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400

        if data.get('statusPaymment') == 'notreceived' or data.get("method") == "boleto":
        
            if data.get("method") == "boleto":
                # Pagamentos a receber
                status_pagamento = "pendente"
                
                create_paymment = {
                    'os_id': os_id,
                    'os_city': os_city,
                    'os_date': os_date,
                    'tecnico_id': os_id_tecnico,
                    'method': data.get('method'),
                    'amount': convert_monetary_value(data.get('boletoValor')),
                    'vencimento': data.get('boletoDate'),
                    'numero_os': numero_os,
                }

                try:
                    Wallet.create_paymment_pendding(data=create_paymment, date=os_date, city=os_city)
                    Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment=status_pagamento)
                
                except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400
                
            elif data.get("method") in ["pix", "dinheiro"]:
                # Pagamentos recebidos
                status_pagamento = "pendente"
                detalhes_pagamento["valor"] = data.get("amount")
                detalhes_pagamento["metodo"] = data.get("method")

                create_paymment ={
                    'os_id': os_id,
                    'os_date': os_date,
                    'os_city': os_city,
                    'tecnico_id': os_id_tecnico,
                    'method': data.get('method'),
                    'amount': convert_monetary_value(data.get('amount')),
                    'vencimento': os_date,
                    'numero_os': numero_os,
                }

                try: 
                    Wallet.create_paymment_pendding(data=create_paymment, date=os_date, city=os_city)
                    Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment=status_pagamento)
                    
                
                except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400

            
            elif data.get("method") == "cartao":
                status_pagamento = "pendente"
                detalhes_pagamento["valor"] = data.get("cardValor")
                detalhes_pagamento["parcelas"] = data.get("installments")

                create_paymment ={
                    'os_id': os_id,
                    'os_date': os_date,
                    'os_city': os_city,
                    'tecnico_id': os_id_tecnico,
                    'method': data.get('method'),
                    'amount': convert_monetary_value(data.get('cardValor')),
                    'installments': data.get('installments'),
                    'vencimento': os_date,
                    'numero_os': numero_os,
                }

                try:
                    Wallet.create_paymment_pendding(data=create_paymment, date=os_date, city=os_city)
                    Wallet.update_status_os(id=os_id, city=os_city, date=os_date, status_paymment=status_pagamento)


                except:
                    return jsonify({'status': 'conflict', 'message': 'Erro.'}), 400

    return jsonify({
        "success": True,
        "message": "OS finalizada com sucesso!",
        "new_status": status_pagamento or "recebido"
    })


@app.route("/salvar_observacao", methods=["POST"])
def salvar_observacao():
    data = request.get_json()

    transaction_id = data.get("transaction_id")
    texto = data.get("observacao", "").strip()
    date = data.get("date")

    if not transaction_id:
        return jsonify({"error": "ID inválido"}), 400

    try:
        
        date = datetime.strptime(date, '%Y-%m-%d')

        year = str(date.year)
        month = f"{date.month:02d}"
        day = f"{date.day:02d}"
    
    except ValueError:
            return "Formato de data inválido."
        
    

    db.child("financeiro").child('transactions').child(year).child(month).child(day).child('transactions').child(transaction_id).update({"observacao": texto})

    return jsonify({"success": True})


@app.route("/ocorrencias")
def ocorrencias():
    dados = db.child("financeiro").child("ocorrencias").get().val() or {}

    # transforma em lista
    lista = []
    for oid, o in dados.items():
        o["id"] = oid
        lista.append(o)

    # ordena por data (mais recente primeiro)
    lista.sort(
        key=lambda x: datetime.strptime(x.get("data"), "%Y-%m-%d"),
        reverse=True
    )

    all_users = db.child("users").get().val() or {}
    tecnicos = {uid: user for uid, user in all_users.items() if user['role'] == 'tecnico'}

    return render_template("ocorrencias.html", ocorrencias=lista, tecnicos=tecnicos)

@app.route("/criar_ocorrencia", methods=["POST"])
def criar_ocorrencia():
    data = request.form

    # Busca todas as ocorrências para gerar o próximo número
    ocorrencias = db.child("financeiro").child("ocorrencias").get().val() or {}

    if ocorrencias:
        ultimo_numero = max(
            o.get("numero", 0) for o in ocorrencias.values()
        )
    else:
        ultimo_numero = 0

    proximo_numero = ultimo_numero + 1

    payload = {
        "numero": proximo_numero,  # ✅ ID numérico da ocorrência
        "data": data.get("data"),
        "tecnico": data.get("tecnico"),
        "os": data.get("os"),
        "descricao": data.get("descricao"),
        "valor": convert_monetary_value(data.get("valor")),
        "acao": data.get("acao"),
        "resultado": data.get("resultado", ""),
        "situacao": data.get("situacao"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    db.child("financeiro").child("ocorrencias").push(payload)

    return redirect(url_for("ocorrencias"))


@app.route("/editar_ocorrencia", methods=["POST"])
def editar_ocorrencia():
    data = request.form
    ocorrencia_id = data.get("ocorrencia_id")

    if not ocorrencia_id:
        return redirect(url_for("ocorrencias"))

    update = {
        "data": data.get("data"),
        "tecnico": data.get("tecnico"),
        "os": data.get("os"),
        "descricao": data.get("descricao"),
        "valor": convert_monetary_value(data.get("valor")),
        "acao": data.get("acao"),
        "resultado": data.get("resultado"),
        "situacao": data.get("situacao"),
    }

    db.child("financeiro").child("ocorrencias").child(ocorrencia_id).update(update)

    return redirect(url_for("ocorrencias"))


@app.route("/deletar_ocorrencia", methods=["POST"])
def deletar_ocorrencia():
    ocorrencia_id = request.form.get("ocorrencia_id")

    if ocorrencia_id:
        db.child("financeiro").child("ocorrencias").child(ocorrencia_id).remove()

    return redirect(url_for("ocorrencias"))


@app.route('/fluxo_caixa', methods=['GET'])
@check_roles(['admin'])
def fluxo_caixa():
    if 'user' not in session:
        return redirect(url_for('login'))

    hoje = datetime.now()
    mes = request.args.get('mes', default=hoje.month, type=int)
    ano = request.args.get('ano', default=hoje.year, type=int)
    return render_template('fluxo_caixa.html', **build_cashflow_context(ano, mes))


@app.route('/analise_financeira', methods=['GET'])
@check_roles(['admin'])
def analise_financeira():
    if 'user' not in session:
        return redirect(url_for('login'))

    hoje = datetime.now()
    mes = request.args.get('mes', default=hoje.month, type=int)
    ano = request.args.get('ano', default=hoje.year, type=int)
    return render_template('analise_financeira.html', **build_profit_analysis_context(ano, mes))


@app.route('/orcamentos/salvar', methods=['POST'])
@check_roles(['admin'])
def salvar_orcamento():
    if 'user' not in session:
        return redirect(url_for('login'))

    ano = request.form.get('ano', type=int)
    mes = request.form.get('mes', type=int)
    categoria = request.form.get('category')
    receita_planejada = request.form.get('planned_revenue')
    despesa_planejada = request.form.get('planned_expense')
    notes = request.form.get('notes')

    if not ano or not mes:
        return redirect(url_for('analise_financeira'))

    success, _message = save_budget_entry(
        year=ano,
        month=mes,
        category=categoria,
        planned_revenue=receita_planejada,
        planned_expense=despesa_planejada,
        notes=notes,
    )

    return redirect(url_for('analise_financeira', ano=ano, mes=mes))


@app.route("/analytics/unidades/cidades", methods=["POST"])
@check_roles(['admin'])
def analytics_unidades_cidades():
    payload = request.get_json(silent=True) or {}
    success, message = create_city(payload.get("cidade"))

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"message": message}), 201


@app.route('/dashboard', methods=['GET', 'POST'])
@check_roles(['admin'])
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    hoje = datetime.now()
    mes = request.args.get('mes', default=hoje.month, type=int)
    ano = request.args.get('ano', default=hoje.year, type=int)
    return render_template('dashboard.html', **build_dashboard_context(ano, mes))

if __name__ == '__main__':
    app.run(debug=True, port=5039)
