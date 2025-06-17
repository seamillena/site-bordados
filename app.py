from flask import Flask, flash,  get_flashed_messages, render_template, request, redirect, session, url_for, make_response, send_from_directory, Response
from flask_mysqldb import MySQL # type: ignore
from collections import defaultdict
import pymysql # type: ignore
import uuid
import os
from werkzeug.utils import secure_filename
import os
import random
import string
from datetime import datetime


#DEF CONFIGURAÇÕES E SUPORTE

app = Flask(__name__)

app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'Millen@1801')
app.config['MYSQL_DB'] = 'bordados_db'

app.config['UPLOAD_FOLDER'] = 'static/imagens'

app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

mysql = MySQL(app)



def gerar_codigo_pedido(tamanho=10):
    caracteres = string.ascii_uppercase + string.digits
    codigo = ''.join(random.choices(caracteres, k=tamanho))
    return codigo

def gerar_publicacao(tamanho=15):
    caracteres = string.ascii_uppercase + string.digits
    publicacao = ''.join(random.choices(caracteres, k=tamanho))
    return publicacao


@app.route('/user')
def user():
    usuario_id = request.cookies.get("usuario_id")
    return f"<p>Usuário ID: {usuario_id}</p>"

def notificacao_carrinho():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return False 
    usuario = 'usuario'
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM carrinhos WHERE id_usuario = %s AND usuario = %s
    """, (id_usuario, usuario))
    count = cur.fetchone()[0]
    cur.close()

    return count > 0 

def notificacao_carrinho_cliente():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return False
    usuario = session.get('usuario')
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM carrinhos WHERE id_usuario = %s AND usuario = %s
    """, (id_usuario, usuario))
    count = cur.fetchone()[0]
    cur.close()

    return count > 0 

def get_contatos():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM contatos")
    dados = cur.fetchall()
    colunas = [desc[0]for desc in cur.description]
    cur.close()

    contatos = [dict(zip(colunas, linha)) for linha in dados]

    return contatos

@app.context_processor
def inject_contatos():
    return {'contatos' :get_contatos()}

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

def verificar_admin():
    if 'usuario' not in session:
        return False

    cur = mysql.connection.cursor()
    cur.execute("SELECT tipo FROM usuarios WHERE usuario = %s", (session['usuario'],))
    resultado = cur.fetchone()
    cur.close()

    return resultado and resultado[0] == 'administrador'

def verificar_cliente():
    if 'usuario' not in session:
        return False

    cur = mysql.connection.cursor()
    cur.execute("SELECT tipo FROM usuarios WHERE usuario = %s", (session['usuario'],))
    resultado = cur.fetchone()
    cur.close()

    return resultado and resultado[0] == 'cliente'

@app.route('/login', methods=['GET', 'POST'])
def login():
    mensagem = None
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha']

        cur = mysql.connection.cursor()
        cur.execute('SELECT * FROM usuarios WHERE usuario = %s', (usuario,))
        resultado = cur.fetchone()
        cur.close()

        if resultado and resultado[1] == senha:

            session['usuario'] = usuario

            tipo_usuario = resultado[6]  

            if tipo_usuario == 'administrador':
                session['inicioadm'] = True
                return redirect(url_for('inicioadm'))

            elif tipo_usuario == 'cliente':
                session['inicio_cliente'] = True
                return redirect(url_for('inicio_cliente'))

            else:
                mensagem = "Tipo de usuário desconhecido."

        else:
            mensagem = "Usuário ou senha inválidos."

    return render_template('usuarios/login.html', mensagem=mensagem)

#DEF USUÁRIOS

@app.route('/')
def inicio():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM iniciodb")
    dados = cur.fetchall() 

    cursor= mysql.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM iniciodb")
    colunas = [col[0] for col in cursor.fetchall()]

    
    cur.close()
    cursor.close()

    iniciodb = [dict(zip(colunas, linha)) for linha in dados]
    item_carrinho = notificacao_carrinho()
   

    return render_template('usuarios/inicio.html', iniciodb=iniciodb, item_carrinho=item_carrinho)


@app.route('/catalogo')
def catalogo():
    try:
        tema = request.args.get('tema')
        cursor = mysql.connection.cursor()

        cursor.execute("SELECT DISTINCT temas FROM bordados")
        todos_os_temas = cursor.fetchall()

        lista_temas = set()
        for linha in todos_os_temas:
            temas_str = linha[0]
            if temas_str:
                temas = [t.strip().capitalize() for t in temas_str.split(',')]
                lista_temas.update(temas)


        temas_ordenados = sorted(lista_temas)

        if tema:
            cursor.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))
        else:
            cursor.execute("SELECT * FROM bordados ORDER BY nome ASC")

        dados = cursor.fetchall()
        cursor.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cursor.fetchall()]
        cursor.close()

        bordados = [dict(zip(colunas, linha)) for linha in dados]
        item_carrinho = notificacao_carrinho()
   

        return render_template(
            'usuarios/catalogo.html',
            bordados=bordados,
            temas_ordenados=temas_ordenados,
            tema_atual=tema,
            item_carrinho=item_carrinho
        )
    except Exception as e:
        return f"<p>Erro ao carregar catálogo: {str(e)}</p>"

@app.route('/detalhes/<int:id>')
def detalhes(id):
    try:
        tema = request.args.get('tema') 
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM bordados WHERE id = %s", (id,))
        resultado = cursor.fetchone()

        cursor.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cursor.fetchall()]
        cursor.close()

        if resultado:
            bordado = dict(zip(colunas, resultado))
            item_carrinho = notificacao_carrinho()
   
            imagens = []
            if bordado.get("imagem"):
                imagens.append(bordado["imagem"])

            if bordado.get("imagens_extras"):
                extras = [img.strip() for img in bordado["imagens_extras"].split(",") if img.strip()]
                imagens.extend(extras)

            bordado["imagens"] = imagens

            cursor = mysql.connection.cursor()

            if not tema or tema.lower() == "todos":
                cursor.execute("SELECT * FROM bordados ORDER BY nome ASC")
            else:
                cursor.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))

            bordados_com_tema = cursor.fetchall()
            cursor.close()

            bordado_ids = [b[0] for b in bordados_com_tema]
            current_index = bordado_ids.index(id)

            next_id = bordado_ids[(current_index + 1) % len(bordado_ids)]
            prev_id = bordado_ids[(current_index - 1) % len(bordado_ids)]

            return render_template('usuarios/detalhes.html', bordado=bordado, 
                                   tema=tema, next_id=next_id, prev_id=prev_id, item_carrinho=item_carrinho)
        else:
            return "<p>Bordado não encontrado.</p>"

    except Exception as e:
        return f"<p>Erro ao carregar detalhes: {str(e)}</p>"


@app.route('/atualizar_carrinho', methods=['POST'])
def atualizar_carrinho():

    id_bordado = request.form.get('id')
    id_usuario = request.cookies.get('usuario_id')
    usuario = 'usuario'
    if not id_usuario:
        id_usuario = str(uuid.uuid4())
        response = make_response(redirect(url_for('detalhes', id=id_bordado)))
        response.set_cookie('usuario_id', id_usuario)
        return response

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT quantidade FROM carrinhos
        WHERE id_usuario = %s AND id_bordado = %s AND usuario = %s
    """, (id_usuario, id_bordado, usuario))
    resultado = cur.fetchone()

    if resultado:
        cur.execute("""
            UPDATE carrinhos
            SET quantidade = quantidade + 1
            WHERE id_usuario = %s AND id_bordado = %s AND usuario =%s
        """, (id_usuario, id_bordado, usuario))
    else:
        cur.execute("""
            INSERT INTO carrinhos (id_usuario, id_bordado, usuario, quantidade)
            VALUES (%s, %s, %s, 1)
        """, (id_usuario, id_bordado, usuario))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('detalhes', id=id_bordado))

@app.route('/esvaziar_carrinho', methods=['POST'])
def esvaziar_carrinho():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return redirect(url_for('carrinho'))
    usuario = 'usuario'
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM carrinhos WHERE id_usuario = %s AND usuario =%s", (id_usuario, usuario))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('carrinho'))

@app.route('/remover_item', methods=['POST'])
def remover_item():
    id_usuario = request.cookies.get('usuario_id')
    id_bordado = request.form.get('id')
    usuario = 'usuario'
    if not id_usuario or not id_bordado:
        return redirect(url_for('carrinho'))

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM carrinhos WHERE id_usuario = %s AND id_bordado = %s AND usuario = %s",
        (id_usuario, id_bordado, usuario)
    )
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('carrinho'))

@app.route('/quantidade', methods=['POST'])
def quantidade():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return redirect(url_for('carrinho'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT id_bordado FROM carrinhos WHERE id_usuario = %s AND usuario = %s", (id_usuario, usuario))
    dados = cur.fetchall()
    cur.close()
    usuario = 'usuario'
    for linha in dados:
        id_bordado = linha[0]
        campo_quantidade = f'quantidade_{id_bordado}'
        nova_quantidade = request.form.get(campo_quantidade)

        if nova_quantidade and nova_quantidade.isdigit() and int(nova_quantidade) > 0:
            cur = mysql.connection.cursor()
            cur.execute(
                "UPDATE carrinhos SET quantidade = %s WHERE id_usuario = %s AND id_bordado = %s AND usuario = %s",
                (int(nova_quantidade), id_usuario, id_bordado, usuario)
            )
            mysql.connection.commit()
            cur.close()

    return redirect(url_for('carrinho'))


@app.route('/realizar_pedido', methods=['POST'])
def realizar_pedido():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return redirect(url_for('carrinho'))

    cur = mysql.connection.cursor()
    usuario ='usuario'
    cur.execute("""
        SELECT c.id_bordado, c.quantidade, b.preco, b.imagem, b.nome, b.descricao
        FROM carrinhos c
        JOIN bordados b ON c.id_bordado = b.id
        WHERE c.id_usuario = %s AND usuario = %s
    """, (id_usuario, usuario))
    dados = cur.fetchall()

    for linha in dados:
        id_bordado = linha[0]
        campo_quantidade = f'quantidade_{id_bordado}'
        quantidade = request.form.get(campo_quantidade)

        if quantidade and quantidade.isdigit() and int(quantidade) > 0:
            quantidade_int = int(quantidade)
            cur.execute("""
                UPDATE carrinhos 
                SET quantidade = %s 
                WHERE id_usuario = %s AND id_bordado = %s AND usuario = %s
            """, (quantidade_int, id_usuario, id_bordado, usuario))
    mysql.connection.commit()

    cur.execute("""
        SELECT c.id_bordado, c.quantidade, b.preco, b.imagem, b.nome, b.descricao
        FROM carrinhos c
        JOIN bordados b ON c.id_bordado = b.id
        WHERE c.id_usuario = %s AND usuario = %s
    """, (id_usuario, usuario))
    dados_atualizados = cur.fetchall()
    cur.close()

    bordados = []
    for linha in dados_atualizados:
        bordados.append({
            'id': linha[0],
            'quantidade': linha[1],
            'preco': linha[2],
            'imagem': linha[3],
            'nome': linha[4],
            'descricao': linha[5]
        })

    valor_total = sum(item['preco'] * item['quantidade'] for item in bordados)

    return render_template('usuarios/realizar-pedido.html', bordados=bordados, valor_total=valor_total)

@app.route('/finalizar_pedido', methods=['POST'])
def finalizar_pedido():
    nome = request.form.get('nome_cliente')
    telefone = request.form.get('tel_cliente')
    email = request.form.get('email_cliente')
    status = 'Pendente'
    data_pedido = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    id_usuario = request.cookies.get('usuario_id')
    codigo_pedido = gerar_codigo_pedido()

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT b.id, b.descricao, c.quantidade FROM bordados b
        JOIN carrinhos c ON b.id = c.id_bordado
        WHERE c.id_usuario = %s
    """, (id_usuario,))
    bordados = cursor.fetchall()

    for linha in bordados:
        id_bordado = str(linha[0])
        quantidade = int(linha[2])  # Corrigido aqui

        descricao = request.form.get(f'descricao_{id_bordado}')
        fotos = request.files.getlist(f'fotos_{id_bordado}')

        fotos_salvas = []
        for imagem in fotos:
            if imagem and imagem.filename != '':
                nome_foto = secure_filename(imagem.filename)
                caminho_foto = os.path.join('static/imagens', nome_foto)
                imagem.save(caminho_foto)
                fotos_salvas.append(nome_foto)
        
        imagens_string = ','.join(fotos_salvas) if fotos_salvas else None

        cursor.execute("""
            INSERT INTO pedidos 
                (fotos, descricao, data_pedido, nome_cliente, tel_cliente, email_cliente, status_pedido, codigo_pedido, id_bordado, quantidade)
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            imagens_string, descricao, data_pedido,
            nome, telefone, email,
            status, codigo_pedido, id_bordado, quantidade
        ))

    cursor.execute("DELETE FROM carrinhos WHERE id_usuario = %s", (id_usuario,))
    mysql.connection.commit()
    cursor.close()

    codigo_pedido = request.form.get('codigo_pedido', codigo_pedido)
    return redirect('/info-pedido' + f'/{codigo_pedido}')


@app.route('/info-pedido/<codigo_pedido>')
def info_pedido(codigo_pedido):
    cur = mysql.connection.cursor()
    cur.execute("""
          SELECT p.*, p.id_bordado, p.codigo_pedido, p.nome_cliente, p.tel_cliente, p.fotos,
               p.email_cliente, p.status_pedido, p.data_pedido, p.descricao AS pedido_descricao, p.quantidade,
               b.id AS bordado_id, b.imagem, b.preco, b.descricao AS bordado_descricao
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.codigo_pedido = %s
    """, (codigo_pedido,))
    dados = cur.fetchall()


    if not dados:
        return "Pedido não encontrado", 404

    colunas = [desc[0] for desc in cur.description]
    pedidos = [dict(zip(colunas, linha)) for linha in dados]

    total = sum(p['preco'] * p['quantidade'] for p in pedidos)
    data_pedido = pedidos[0]['data_pedido']

    cur.close()
    return render_template('usuarios/info-pedido.html', pedidos=pedidos, codigo_pedido=codigo_pedido, total=total, data_pedido=data_pedido)

@app.route('/carrinho')
def carrinho():
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return render_template('usuarios/carrinho.html', bordados=[], valor_total=0)
    usuario = 'usuario'
    cur = mysql.connection.cursor()
    query = """
        SELECT b.*, c.quantidade
        FROM carrinhos c
        JOIN bordados b ON c.id_bordado = b.id
        WHERE c.id_usuario = %s AND usuario = %s
    """
    cur.execute(query, (id_usuario, usuario))
    dados = cur.fetchall()

    cursor = mysql.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM bordados")
    colunas_bordados = [col[0] for col in cursor.fetchall()]
    cursor.close()
    colunas = colunas_bordados + ['quantidade']

    cur.close()

    bordados = [dict(zip(colunas, linha)) for linha in dados]

    valor_total = 0
    for item in bordados:
        preco = float(item.get('preco', 0))
        quantidade = int(item.get('quantidade', 1))
        valor_total += preco * quantidade

    return render_template('usuarios/carrinho.html', bordados=bordados, valor_total=valor_total)

@app.route('/pedido', methods=['GET', 'POST'])
def pedido():
    termo_busca = ''
    pedidos = []
    codigo_pedido = request.args.get('codigo_pedido', '')

    if request.method == 'POST':
        termo_busca = request.form['termo_busca']

        cur = mysql.connection.cursor()
        query = """
            SELECT p.*, p.id_bordado, p.codigo_pedido, p.nome_cliente, p.tel_cliente, p.fotos,
                   p.email_cliente, p.status_pedido, p.data_pedido, p.descricao AS pedido_descricao, p.quantidade,
                   b.id AS bordado_id, b.imagem, b.preco, b.descricao AS bordado_descricao
            FROM pedidos p
            JOIN bordados b ON p.id_bordado = b.id
            WHERE p.codigo_pedido = %s
        """
        cur.execute(query, (termo_busca,))
        resultados = cur.fetchall()

        if resultados:
            colunas = [desc[0] for desc in cur.description]
            pedidos = [dict(zip(colunas, linha)) for linha in resultados]
        cur.close()

    return render_template('usuarios/pedido.html', pedidos=pedidos, termo=codigo_pedido)


@app.route('/excluir_pedido/<codigo_pedido>', methods=['POST'])
def excluir_pedido(codigo_pedido):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pedidos WHERE codigo_pedido = %s", (codigo_pedido,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('pedido'))


@app.route('/editar-pedido/<codigo_pedido>', methods=['GET', 'POST'])
def editar_pedido(codigo_pedido):
    cur = mysql.connection.cursor()

    # Primeiro, buscar o pedido
    query = """
        SELECT p.*, b.imagem, b.preco, b.descricao AS bordado_descricao
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.codigo_pedido = %s
    """
    cur.execute(query, (codigo_pedido,))
    resultado = cur.fetchone()

    if not resultado:
        cur.close()
        return "Pedido não encontrado.", 404

    colunas = [desc[0] for desc in cur.description]
    pedido = dict(zip(colunas, resultado))

    # Se o pedido não estiver pendente, bloqueia a edição
    if pedido['status_pedido'].lower() != 'pendente':
        cur.close()
        return "Este pedido não pode mais ser editado. Ele está " + pedido['status_pedido'] + ". Entre em contato com O ASTRONAUTA BORDADOS PARA REALIZAR ALTERAÇÕES.", 404

    # Se for POST e status for pendente, permite atualizar
    if request.method == 'POST':
        novo_nome = request.form.get('nome_cliente')
        novo_email = request.form.get('email_cliente')
        nova_descricao = request.form.get('descricao')
        novo_tel = request.form.get('tel_cliente')

        cur.execute("""
            UPDATE pedidos
            SET nome_cliente = %s, email_cliente = %s, descricao = %s, tel_cliente = %s
            WHERE codigo_pedido = %s
        """, (novo_nome, novo_email, nova_descricao, novo_tel, codigo_pedido))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('pedido', codigo_pedido=codigo_pedido)) 

    cur.close()
    return render_template('usuarios/editar-pedido.html', pedido=pedido)


@app.route('/mural', methods=['GET', 'POST'])
def mural():
    item_carrinho = notificacao_carrinho()
    cur = mysql.connection.cursor()

 
    # Buscar todas as publicações com dados do usuário, sem usar GROUP BY
    cur.execute("""
        SELECT m.publicacao, m.usuario, m.fotos, m.curtidas, m.legendas, m.data_publicacao, m.hora_publicacao,
               u.foto, u.nome, u.sobrenome
        FROM mural m
        JOIN usuarios u ON m.usuario = u.usuario
        ORDER BY m.data_publicacao DESC, m.hora_publicacao DESC
    """)
    mural_dados = cur.fetchall()

    colunas_mural = ['publicacao', 'usuario', 'fotos', 'curtidas', 'legendas', 'data_publicacao', 'hora_publicacao',
                     'foto', 'nome', 'sobrenome']

    # Filtrar duplicatas por publicacao manualmente
    publicacoes_vistas = set()
    mural = []
    for linha in mural_dados:
        item = dict(zip(colunas_mural, linha))
        if item['publicacao'] not in publicacoes_vistas:
            mural.append(item)
            publicacoes_vistas.add(item['publicacao'])

    # Buscar comentários para cada publicação
    comentarios_por_post = {}
    cur.execute("SHOW COLUMNS FROM comentarios")
    colunas_coment = [col[0] for col in cur.fetchall()]

    for item in mural:
        publicacao = item['publicacao']
        cur.execute("""
            SELECT * FROM comentarios WHERE publicacao = %s ORDER BY data_comentario DESC, hora_comentario DESC
        """, (publicacao,))
        dados_coment = cur.fetchall()
        comentarios_por_post[publicacao] = [dict(zip(colunas_coment, linha)) for linha in dados_coment]

    cur.close()

    return render_template('usuarios/mural.html', item_carrinho=item_carrinho, mural = mural, comentarios_por_post=comentarios_por_post)


@app.route('/comentarios', methods=['POST'])
def comentarios():
    publicacao = request.form.get('publicacao')
    
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM comentarios WHERE publicacao = %s ORDER BY data_comentario DESC, hora_comentario DESC
    """, (publicacao,))
    dados = cur.fetchall()

    cur.execute("SHOW COLUMNS FROM comentarios")
    colunas = [col[0] for col in cur.fetchall()]
    cur.close()

    comentarios = [dict(zip(colunas, linha)) for linha in dados]

    return render_template('usuarios/comentarios.html', comentarios=comentarios, publicacao=publicacao)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    mensagem = None

    if request.method == 'POST':
        novo_nome = request.form.get('novo_nome')
        novo_sobrenome = request.form.get('novo_sobrenome')
        novo_email = request.form.get('novo_email')
        confirmar_email = request.form.get('confirmar_email')
        novo_telefone = request.form.get('novo_telefone')
        novo_usuario = request.form.get('novo_usuario')
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')
        tipo = 'cliente'

        if novo_email != confirmar_email:
            mensagem = "Os e-mails não coincidem."
        elif nova_senha != confirmar_senha:
            mensagem = "As senhas não coincidem."

        else:
            cur = mysql.connection.cursor()
            cur.execute('SELECT id FROM usuarios WHERE usuario = %s', (novo_usuario,))
            if cur.fetchone():
                mensagem = "Esse nome de usuário já está em uso."
            else:
                cur.execute('''
                    INSERT INTO usuarios (nome, sobrenome, email, telefone, usuario, senha, tipo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (novo_nome, novo_sobrenome, novo_email, novo_telefone, novo_usuario, nova_senha, tipo))

                mysql.connection.commit()
                cur.close()
                mensagem = 'Conta criada!'
                return redirect(url_for('login'))


    return render_template('usuarios/cadastro.html', mensagem=mensagem)



@app.route('/excluir_imagem_extra', methods=['POST'])
def excluir_imagem_extra():
    id = request.form.get('id')
    imagem_excluir = request.form.get('imagem')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM bordados WHERE id = %s", (id,))
    bordado = cur.fetchone()

    if bordado:
        imagens = bordado[4].split(',') if bordado[4] else []
        imagens = [img.strip() for img in imagens if img.strip() != imagem_excluir]
        nova_string = ','.join(imagens)

        cur.execute("UPDATE bordados SET imagens_extras = %s WHERE id = %s", (nova_string, id))
        mysql.connection.commit()
        cur.close()

    return redirect(url_for('editar-bordado', id=id))


@app.context_processor
def foto_perfil():
    usuario = session.get('usuario')
    
    if not usuario:
        return dict(foto='user.png')

    cur = mysql.connection.cursor()
    cur.execute("SELECT foto FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    cur.close()

    if resultado:
        return dict(foto=resultado[0])
    else:
        return dict(foto='user.png')




@app.context_processor
def nome():
    usuario = session.get('usuario')
    print('Usuário da sessão:', usuario)

    if not usuario:
        return dict(nome='', sobrenome='')

    cur = mysql.connection.cursor()
    cur.execute("SELECT nome FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    cur.close()

    print('Resultado da consulta SQL:', resultado)

    if resultado:
        return dict(nome=resultado[0])
    else:
        return dict(nome='')
    
@app.context_processor
def sobrenome():
    usuario = session.get('usuario')
    print('Usuário da sessão:', usuario)

    if not usuario:
        return dict(nome='', sobrenome='')

    cur = mysql.connection.cursor()
    cur.execute("SELECT sobrenome FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    cur.close()

    print('Resultado da consulta SQL:', resultado)

    if resultado:
        return dict(sobrenome=resultado[0])
    else:
        return dict(sobrenome='')
    
@app.context_processor
def usuario():
    usuario = session.get('usuario')

    cur = mysql.connection.cursor()
    cur.execute("SELECT usuario FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    cur.close()

    if resultado:
        return dict(usuario=resultado[0])
    else:
        return dict(usuario='')

#DEF CLIENTES

@app.route('/inicio-cliente')
def inicio_cliente():
    if not verificar_cliente():
        return redirect('/login')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM iniciodb")
    dados = cur.fetchall() 

    cursor= mysql.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM iniciodb")
    colunas = [col[0] for col in cursor.fetchall()]

    
    cur.close()
    cursor.close()

    iniciodb = [dict(zip(colunas, linha)) for linha in dados]
    item_carrinho = notificacao_carrinho_cliente()
   

    return render_template('clientes/inicio-cliente.html', iniciodb=iniciodb, item_carrinho=item_carrinho)


@app.route('/catalogo-cliente')
def catalogo_cliente():
    if not verificar_cliente():
        return redirect('/login')
    try:
        tema = request.args.get('tema')
        cursor = mysql.connection.cursor()

        cursor.execute("SELECT DISTINCT temas FROM bordados")
        todos_os_temas = cursor.fetchall()

        lista_temas = set()
        for linha in todos_os_temas:
            temas_str = linha[0]
            if temas_str:
                temas = [t.strip().capitalize() for t in temas_str.split(',')]
                lista_temas.update(temas)


        temas_ordenados = sorted(lista_temas)

        if tema:
            cursor.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))
        else:
            cursor.execute("SELECT * FROM bordados ORDER BY nome ASC")

        dados = cursor.fetchall()
        cursor.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cursor.fetchall()]
        cursor.close()

        bordados = [dict(zip(colunas, linha)) for linha in dados]
        item_carrinho = notificacao_carrinho_cliente()
   

        return render_template(
            'clientes/catalogo-cliente.html',
            bordados=bordados,
            temas_ordenados=temas_ordenados,
            tema_atual=tema,
            item_carrinho=item_carrinho
        )
    except Exception as e:
        return f"<p>Erro ao carregar catálogo: {str(e)}</p>"

@app.route('/perfil')
def perfil():
    if not verificar_cliente():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT tipo FROM usuarios WHERE usuario = %s", (session['usuario'],))
    cur.close()

    cur = mysql.connection.cursor()
 
    return render_template('clientes/perfil.html')

@app.route('/perfiladm')
def perfiladm():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT tipo FROM usuarios WHERE usuario = %s", (session['usuario'],))
    cur.close()

    cur = mysql.connection.cursor()
 
    return render_template('administradores/perfiladm.html')


@app.route('/detalhes-cliente/<int:id>')
def detalhes_cliente(id):
    if not verificar_cliente():
        return redirect('/login')
    try:
        tema = request.args.get('tema') 
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM bordados WHERE id = %s", (id,))
        resultado = cursor.fetchone()

        cursor.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cursor.fetchall()]
        cursor.close()

        if resultado:
            bordado = dict(zip(colunas, resultado))
            item_carrinho = notificacao_carrinho_cliente()
   
            imagens = []
            if bordado.get("imagem"):
                imagens.append(bordado["imagem"])

            if bordado.get("imagens_extras"):
                extras = [img.strip() for img in bordado["imagens_extras"].split(",") if img.strip()]
                imagens.extend(extras)

            bordado["imagens"] = imagens

            cursor = mysql.connection.cursor()

            if not tema or tema.lower() == "todos":
                cursor.execute("SELECT * FROM bordados ORDER BY nome ASC")
            else:
                cursor.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))

            bordados_com_tema = cursor.fetchall()
            cursor.close()

            bordado_ids = [b[0] for b in bordados_com_tema]
            current_index = bordado_ids.index(id)

            next_id = bordado_ids[(current_index + 1) % len(bordado_ids)]
            prev_id = bordado_ids[(current_index - 1) % len(bordado_ids)]

            return render_template('clientes/detalhes-cliente.html', bordado=bordado, 
                                   tema=tema, next_id=next_id, prev_id=prev_id, item_carrinho=item_carrinho)
        else:
            return "<p>Bordado não encontrado.</p>"

    except Exception as e:
        return f"<p>Erro ao carregar detalhes: {str(e)}</p>"


@app.route('/atualizar_carrinho_cliente', methods=['POST'])
def atualizar_carrinho_cliente():
    if not verificar_cliente():
        return redirect('/login')
    
    usuario = session.get('usuario')
    id_bordado = request.form.get('id')
    id_usuario = request.cookies.get('usuario_id')
   
    if not id_usuario:
        id_usuario = str(uuid.uuid4())
        response = make_response(redirect(url_for('detalhes_cliente', id=id_bordado)))
        response.set_cookie('usuario_id', id_usuario)
        return response

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT quantidade FROM carrinhos
        WHERE id_usuario = %s AND usuario = %s AND id_bordado = %s
    """, (id_usuario, usuario, id_bordado))
    resultado = cur.fetchone()

    if resultado:
        cur.execute("""
            UPDATE carrinhos
            SET quantidade = quantidade + 1
            WHERE id_usuario = %s AND usuario = %s AND id_bordado = %s
        """, (id_usuario, usuario, id_bordado))
    else:
        cur.execute("""
            INSERT INTO carrinhos (id_usuario, usuario, id_bordado, quantidade)
            VALUES (%s, %s, %s, 1)
        """, (id_usuario, usuario, id_bordado))

    mysql.connection.commit()
    cur.close()

    return redirect(url_for('detalhes_cliente', id=id_bordado))

@app.route('/esvaziar_carrinho_cliente', methods=['POST'])
def esvaziar_carrinho_cliente():
    if not verificar_cliente():
        return redirect('/login')
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return redirect(url_for('carrinho-cliente'))
    usuario = session.get('usuario')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM carrinhos WHERE id_usuario = %s AND usuario = %s", (id_usuario, usuario))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('carrinho_cliente'))

@app.route('/remover_item_cliente', methods=['POST'])
def remover_item_cliente():
    if not verificar_cliente():
        return redirect('/login')
    
    id_usuario = request.cookies.get('usuario_id')
    id_bordado = request.form.get('id')

    if not id_usuario or not id_bordado:
        return redirect(url_for('carrinho-cliente'))

    cur = mysql.connection.cursor()
    cur.execute(
        "DELETE FROM carrinhos WHERE id_usuario = %s AND id_bordado = %s",
        (id_usuario, id_bordado)
    )
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('carrinho-cliente'))

@app.route('/quantidade_cliente', methods=['POST'])
def quantidade_cliente():
    if not verificar_cliente():
        return redirect('/login')
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return redirect(url_for('carrinho-cliente'))

    cur = mysql.connection.cursor()

    cur.execute("SELECT id_bordado FROM carrinhos WHERE id_usuario = %s", (id_usuario,))
    dados = cur.fetchall()
    cur.close()

    for linha in dados:
        id_bordado = linha[0]
        campo_quantidade = f'quantidade_{id_bordado}'
        nova_quantidade = request.form.get(campo_quantidade)

        if nova_quantidade and nova_quantidade.isdigit() and int(nova_quantidade) > 0:
            cur = mysql.connection.cursor()
            cur.execute(
                "UPDATE carrinhos SET quantidade = %s WHERE id_usuario = %s AND id_bordado = %s",
                (int(nova_quantidade), id_usuario, id_bordado)
            )
            mysql.connection.commit()
            cur.close()

    return redirect(url_for('carrinho-cliente'))


@app.route('/realizar_pedido_cliente', methods=['POST'])
def realizar_pedido_cliente():
    if not verificar_cliente():
        return redirect('/login')

    id_usuario = request.cookies.get('usuario_id')
    usuario = session.get('usuario')
    cur = mysql.connection.cursor()

    # Buscar os itens do carrinho
    cur.execute("""
        SELECT c.id_bordado, c.quantidade, b.preco, b.imagem, b.nome, b.descricao
        FROM carrinhos c
        JOIN bordados b ON c.id_bordado = b.id
        WHERE c.id_usuario = %s AND c.usuario = %s
    """, (id_usuario, usuario))
    dados_carrinho = cur.fetchall()

    # Buscar os dados do cliente
    cur.execute("""
        SELECT nome, telefone, email, usuario FROM usuarios WHERE id = %s
    """, (id_usuario,))
    cliente = cur.fetchone()
    cur.close()

    # Transformar os dados em dicionários
    bordados = []
    for linha in dados_carrinho:
        bordados.append({
            'id': linha[0],
            'quantidade': linha[1],
            'preco': linha[2],
            'imagem': linha[3],
            'nome': linha[4],
            'descricao': linha[5]
        })

    valor_total = sum(item['preco'] * item['quantidade'] for item in bordados)

    return render_template('clientes/realizar-pedido-cliente.html', 
                           bordados=bordados, 
                           valor_total=valor_total, 
                           cliente=cliente)

@app.route('/finalizar_pedido_cliente', methods=['POST'])
def finalizar_pedido_cliente():
    if not verificar_cliente():
        return redirect('/login')

    id_usuario = request.cookies.get('usuario_id')
    usuario = session.get('usuario')
    cursor = mysql.connection.cursor()

    # Buscar os dados do cliente na tabela usuarios
    cursor.execute("""
        SELECT nome, telefone, email FROM usuarios WHERE usuario = %s
    """, (usuario,))
    dados_cliente = cursor.fetchone()

    if not dados_cliente:
        cursor.close()
        return "Erro: Usuário não encontrado na tabela usuarios."

    # Salvar os dados em variáveis com os nomes corretos para o INSERT
    nome_cliente = dados_cliente[0]
    tel_cliente = dados_cliente[1]
    email_cliente = dados_cliente[2]

    status = 'Pendente'
    data_pedido = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    codigo_pedido = gerar_codigo_pedido()

    # Buscar os itens do carrinho deste usuário
    cursor.execute("""
        SELECT b.id, b.descricao, c.quantidade
        FROM bordados b
        JOIN carrinhos c ON b.id = c.id_bordado
        WHERE c.id_usuario = %s
    """, (id_usuario,))
    bordados = cursor.fetchall()

    for linha in bordados:
        id_bordado = str(linha[0])
        quantidade = int(linha[2])

        # Descrição enviada pelo cliente (se houver)
        descricao = request.form.get(f'descricao_{id_bordado}')

        # Fotos enviadas pelo cliente (se houver)
        fotos = request.files.getlist(f'fotos_{id_bordado}')
        fotos_salvas = []

        for imagem in fotos:
            if imagem and imagem.filename != '':
                nome_foto = secure_filename(imagem.filename)
                caminho_foto = os.path.join('static/imagens', nome_foto)
                imagem.save(caminho_foto)
                fotos_salvas.append(nome_foto)

        imagens_string = ','.join(fotos_salvas) if fotos_salvas else None

        # Inserir o pedido no banco
        cursor.execute("""
            INSERT INTO pedidos 
                (fotos, descricao, data_pedido, nome_cliente, tel_cliente, email_cliente, status_pedido, codigo_pedido, id_bordado, quantidade, usuario)
            VALUES 
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            imagens_string, descricao, data_pedido,
            nome_cliente, tel_cliente, email_cliente,
            status, codigo_pedido, id_bordado, quantidade, usuario
        ))

    # Limpar o carrinho depois de finalizar
    cursor.execute("DELETE FROM carrinhos WHERE id_usuario = %s", (id_usuario,))
    mysql.connection.commit()
    cursor.close()

    return redirect('/pedido-cliente')


@app.route('/carrinho-cliente')
def carrinho_cliente():
    if not verificar_cliente():
        return redirect('/login')
    id_usuario = request.cookies.get('usuario_id')
    if not id_usuario:
        return render_template('usuarios/carrinho.html', bordados=[], valor_total=0)
    usuario = session.get('usuario')
    cur = mysql.connection.cursor()
    query = """
        SELECT b.*, c.quantidade, c.usuario
        FROM carrinhos c
        JOIN bordados b ON c.id_bordado = b.id
        WHERE c.id_usuario = %s AND c.usuario = %s
    """
    cur.execute(query, (id_usuario, usuario))
    dados = cur.fetchall()

    cursor = mysql.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM bordados")
    colunas_bordados = [col[0] for col in cursor.fetchall()]
    cursor.close()
    colunas = colunas_bordados + ['quantidade']

    cur.close()

    bordados = [dict(zip(colunas, linha)) for linha in dados]

    valor_total = 0
    for item in bordados:
        preco = float(item.get('preco', 0))
        quantidade = int(item.get('quantidade', 1))
        valor_total += preco * quantidade

    item_carrinho = notificacao_carrinho_cliente()

    return render_template('clientes/carrinho-cliente.html', bordados=bordados, valor_total=valor_total, item_carrinho=item_carrinho)

@app.route('/pedido-cliente', methods=['GET', 'POST'])
def pedido_cliente():
    if not verificar_cliente():
        return redirect('/login')
    pedidos = []
    usuario = session.get('usuario')

    # Primeiro pegar o email do usuário logado
    cur = mysql.connection.cursor()
    cur.execute("SELECT email FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    if resultado:
        email_usuario = resultado[0]
    else:
        email_usuario = None
    cur.close()

    cur = mysql.connection.cursor()
    query = """
        SELECT p.*, p.id_bordado, p.codigo_pedido, p.nome_cliente, p.tel_cliente, p.fotos,
               p.email_cliente, p.status_pedido, p.data_pedido, p.descricao AS pedido_descricao, p.quantidade,
               b.id AS bordado_id, b.imagem, b.preco, b.descricao AS bordado_descricao
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.usuario = %s OR p.email_cliente = %s
    """
    cur.execute(query, (usuario, email_usuario))
    resultados = cur.fetchall()

    if resultados:
        colunas = [desc[0] for desc in cur.description]
        pedidos = [dict(zip(colunas, linha)) for linha in resultados]
    cur.close()
    item_carrinho = notificacao_carrinho_cliente()
    return render_template('clientes/pedido-cliente.html', pedidos=pedidos, usuario=usuario, item_carrinho=item_carrinho)

@app.route('/editar_perfil_adm/', methods=['POST'])
def editar_perfil_adm():
    usuario = session.get('usuario')
    if not verificar_admin():
        return redirect('/login')

    novo_nome = request.form['nome']
    novo_sobrenome = request.form['sobrenome']
    novo_usuario = request.form['usuario']
    
    senha_atual_form = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    foto = request.files.get('imagem')

    mensagem = None

    cur = mysql.connection.cursor()

    # Buscar senha e foto atuais
    cur.execute("SELECT senha, foto FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    if not resultado:
        mensagem = 'Usuário não encontrado.'
        cur.close()
        return render_template('administradores/perfil.html', mensagem=mensagem, usuario=usuario, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))

    senha_armazenada, foto_atual = resultado

    # Se o novo usuário for diferente do atual, verificar se já existe alguém com esse nome de usuário
    # Se o novo usuário for diferente do atual, verificar se já existe alguém com esse nome de usuário
    if novo_usuario != usuario:
        cur.execute("SELECT id FROM usuarios WHERE usuario = %s", (novo_usuario,))
        if cur.fetchone():
            cur.close()
            mensagem = 'Este nome de usuário já está em uso. Escolha outro.'
            return render_template('administradores/perfiladm.html', mensagem=mensagem, usuario=usuario, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))
    if nova_senha:
        if not senha_atual_form:
            mensagem = 'Digite sua senha atual para alterar a senha.'
            cur.close()
            return render_template('administradores/perfiladm.html', mensagem=mensagem, usuario=usuario, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))

        if senha_atual_form != senha_armazenada:
            mensagem = 'Senha atual incorreta.'
            cur.close()
            return render_template('administradores/perfiladn.html', mensagem=mensagem, usuario=usuario, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))

        senha_para_salvar = nova_senha
    else:
        senha_para_salvar = senha_armazenada

    # Verificar a foto
    if foto and foto.filename:
        nova_foto = secure_filename(foto.filename)
        foto.save(os.path.join('static/imagens', nova_foto))
    else:
        nova_foto = foto_atual

    # Atualizar no banco
    sql = """
        UPDATE usuarios 
        SET nome = %s, sobrenome = %s, foto = %s, senha = %s, usuario = %s 
        WHERE usuario = %s
    """
    valores = (novo_nome, novo_sobrenome, nova_foto, senha_para_salvar, novo_usuario, usuario)
    cur.execute(sql, valores)
    mysql.connection.commit()
    cur.close()

    # Atualizar sessão
    session['usuario'] = novo_usuario
    session['nome'] = novo_nome
    session['sobrenome'] = novo_sobrenome
    session['foto'] = nova_foto

    mensagem = 'Perfil atualizado com sucesso!'
  

    return render_template('administradores/perfiladm.html', mensagem=mensagem, usuario=novo_usuario, nome=novo_nome, sobrenome=novo_sobrenome, foto=nova_foto)


@app.route('/excluir_publicacao/<publicacao>', methods=['POST'])
def excluir_publicacao(publicacao):
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session.get('usuario')

    cur = mysql.connection.cursor()
    cur.execute("SELECT tipo FROM usuarios WHERE usuario = %s", (usuario,))
    resultado = cur.fetchone()
    tipo = resultado[0] if resultado else None
    if tipo == 'administrador':
        # Admin pode excluir qualquer post
        cur.execute("DELETE FROM comentarios WHERE publicacao = %s", (publicacao,))
        cur.execute("DELETE FROM mural WHERE publicacao = %s", (publicacao,))
        mysql.connection.commit()
    else:
        # Usuário normal só pode excluir os próprios
        cur.execute("SELECT * FROM mural WHERE publicacao = %s AND usuario = %s", (publicacao, usuario))
        resultado = cur.fetchone()
        if resultado:
            cur.execute("DELETE FROM comentarios WHERE publicacao = %s", (publicacao,))
            cur.execute("DELETE FROM mural WHERE publicacao = %s", (publicacao,))
            mysql.connection.commit()

    cur.close()
    return redirect(request.referrer)


@app.route('/excluir_comentario/<int:id>', methods=['POST'])
def excluir_comentario(id):
    if 'usuario' not in session:
        return redirect('/login')

    usuario = session['usuario']
    cur = mysql.connection.cursor()

    # Se for administrador, pode excluir qualquer comentário
    if session.get('tipo') == 'administrador':
        cur.execute("DELETE FROM comentarios WHERE id = %s", (id,))
        mysql.connection.commit()
    else:
        # Senão, só pode excluir o próprio comentário
        cur.execute("SELECT * FROM comentarios WHERE id = %s AND usuario = %s ", (id, usuario))
        resultado = cur.fetchone()
        if resultado:
            cur.execute("DELETE FROM comentarios WHERE id = %s ", (id,))
            mysql.connection.commit()

    cur.close()
    return redirect(request.referrer)



@app.route('/excluir_pedido_cliente/<codigo_pedido>', methods=['POST'])
def excluir_pedido_cliente(codigo_pedido):
    if not verificar_cliente():
        return redirect('/login')
    
    id_bordado = request.form.get('id_bordado')
    usuario = session.get('usuario')
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pedidos WHERE codigo_pedido = %s AND id_bordado = %s AND usuario = %s ", (codigo_pedido, id_bordado, usuario))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('pedido_cliente'))


@app.route('/editar-pedido-cliente/<codigo_pedido>', methods=['GET', 'POST'])
def editar_pedido_cliente(codigo_pedido):
    if not verificar_cliente():
        return redirect('/login')
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        novo_nome = request.form.get('nome_cliente')
        novo_email = request.form.get('email_cliente')
        nova_descricao = request.form.get('descricao')
        novo_tel = request.form.get('tel_cliente')

        cur.execute("""
            UPDATE pedidos
            SET nome_cliente = %s, email_cliente = %s, descricao = %s, tel_cliente = %s
            WHERE codigo_pedido = %s
        """, (novo_nome, novo_email, nova_descricao, novo_tel, codigo_pedido))

        mysql.connection.commit()
        cur.close()
        return redirect(url_for('pedido_cliente', codigo_pedido=codigo_pedido)) 

    else:
        query = """
            SELECT p.*, b.imagem, b.preco, b.descricao AS bordado_descricao
            FROM pedidos p
            JOIN bordados b ON p.id_bordado = b.id
            WHERE p.codigo_pedido = %s
        """
        cur.execute(query, (codigo_pedido,))
    resultado = cur.fetchone()

    if not resultado:
        cur.close()
        return "Pedido não encontrado.", 404

    colunas = [desc[0] for desc in cur.description]
    pedido = dict(zip(colunas, resultado))

    cur.close()
    return render_template('clientes/editar-pedido-cliente.html', pedido=pedido)


@app.route('/mural-cliente', methods=['GET', 'POST'])
def mural_cliente():
    if not verificar_cliente():
        return redirect('/login')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        legenda = request.form.get('legenda')
        usuario = session.get('usuario')
        fotos_arquivos = request.files.getlist('fotos')
        fotos_nomes = []

        for foto in fotos_arquivos:
            if foto and foto.filename:
                nome_arquivo = f"mural_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto.filename}"
                caminho = os.path.join('static/imagens/mural', nome_arquivo)
                foto.save(caminho)
                fotos_nomes.append(nome_arquivo)

        fotos = ','.join(fotos_nomes)
        curtidas = 0
        publicacao = gerar_publicacao()
        agora = datetime.now()

        cur.execute("""
            INSERT INTO mural (publicacao, usuario, fotos, curtidas, legendas, data_publicacao, hora_publicacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (publicacao, usuario, fotos, curtidas, legenda, agora.date(), agora.time()))
        mysql.connection.commit()

    # Buscar todas as publicações com dados do usuário, sem usar GROUP BY
    cur.execute("""
        SELECT m.publicacao, m.usuario, m.fotos, m.curtidas, m.legendas, m.data_publicacao, m.hora_publicacao,
               u.foto, u.nome, u.sobrenome
        FROM mural m
        JOIN usuarios u ON m.usuario = u.usuario
        ORDER BY m.data_publicacao DESC, m.hora_publicacao DESC
    """)
    mural_dados = cur.fetchall()

    colunas_mural = ['publicacao', 'usuario', 'fotos', 'curtidas', 'legendas', 'data_publicacao', 'hora_publicacao',
                     'foto', 'nome', 'sobrenome']

    # Filtrar duplicatas por publicacao manualmente
    publicacoes_vistas = set()
    mural = []
    for linha in mural_dados:
        item = dict(zip(colunas_mural, linha))
        if item['publicacao'] not in publicacoes_vistas:
            mural.append(item)
            publicacoes_vistas.add(item['publicacao'])

    # Buscar comentários para cada publicação
    comentarios_por_post = {}
    cur.execute("SHOW COLUMNS FROM comentarios")
    colunas_coment = [col[0] for col in cur.fetchall()]

    for item in mural:
        publicacao = item['publicacao']
        cur.execute("""
            SELECT * FROM comentarios WHERE publicacao = %s ORDER BY data_comentario DESC, hora_comentario DESC
        """, (publicacao,))
        dados_coment = cur.fetchall()
        comentarios_por_post[publicacao] = [dict(zip(colunas_coment, linha)) for linha in dados_coment]

    cur.close()
    item_carrinho = notificacao_carrinho_cliente()
    return render_template('clientes/mural-cliente.html', mural=mural, comentarios_por_post=comentarios_por_post, item_carrinho =item_carrinho)


@app.route('/publicacao-cliente', methods=['GET', 'POST'])
def publicacao_cliente():
    if usuario in session:
        return redirect('/login')

    if request.method == 'POST':
        legenda = request.form.get('legenda')
        usuario = session.get('usuario')
        fotos_arquivos = request.files.getlist('fotos')  # Nome do campo no form
        fotos_nomes = []
        
        # Salvar fotos na pasta static/imagens/mural
        for foto in fotos_arquivos:
            if foto and foto.filename:  # Verifica se o arquivo foi enviado
                nome_arquivo = f"mural_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto.filename}"
                caminho = os.path.join('static/imagens/mural', nome_arquivo)
                foto.save(caminho)
                fotos_nomes.append(nome_arquivo)

        fotos = ','.join(fotos_nomes)  # Salvar no banco como string separada por vírgula
        curtidas = 0
        comentarios = ''
        publicacao = gerar_publicacao()
        agora = datetime.now()
        data_publicacao = agora.date()
        hora_publicacao = agora.time()

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO mural (publicacao, usuario, fotos, curtidas, legendas, comentarios, data_publicacao, hora_publicacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (publicacao, usuario, fotos, curtidas, legenda, comentarios, data_publicacao, hora_publicacao))

        mysql.connection.commit()
        cur.close()

        return redirect(request.referrer)

    return redirect(request.referrer,mural = mural)

@app.route('/curtir', methods=['POST'])
def curtir():
    if 'usuario' not in session:
        mensagem = 'Faça login para curtir'

    publicacao = request.form.get('publicacao')
    usuario = session['usuario']

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT * FROM curtidas WHERE usuario = %s AND publicacao = %s
    """, (usuario, publicacao))
    curtida_existente = cur.fetchone()

    if curtida_existente:
        cur.execute("""
            UPDATE mural SET curtidas = curtidas - 1 WHERE publicacao = %s
        """, (publicacao,))

        cur.execute("""
            DELETE FROM curtidas WHERE usuario = %s AND publicacao = %s
        """, (usuario, publicacao))
    else:

        cur.execute("""
            UPDATE mural SET curtidas = curtidas + 1 WHERE publicacao = %s
        """, (publicacao,))

        cur.execute("""
            INSERT INTO curtidas (usuario, publicacao) VALUES (%s, %s)
        """, (usuario, publicacao))

    mysql.connection.commit()
    cur.close()

    return redirect(request.referrer)

@app.route('/comentarioadm', methods=['POST'])
def comentarioadm():
    if not verificar_admin():
        return redirect('/login')

    comentario = request.form.get('comentario')
    usuario = session.get('usuario')
    publicacao = request.form.get('publicacao')
    agora = datetime.now()
    data_comentario = agora.date()
    hora_comentario = agora.time()

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO comentarios (comentario, usuario, publicacao, data_comentario, hora_comentario)
        VALUES (%s, %s, %s, %s, %s)
    """, (comentario, usuario, publicacao, data_comentario, hora_comentario))

    mysql.connection.commit()
    cur.close()

    return redirect(request.referrer or '/muraladm')

@app.route('/comentario-cliente', methods=['POST'])
def comentario_cliente():
    if not verificar_cliente():
        return redirect('/login')

    comentario = request.form.get('comentario')
    usuario = session.get('usuario')
    publicacao = request.form.get('publicacao')
    agora = datetime.now()
    data_comentario = agora.date()
    hora_comentario = agora.time()

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO comentarios (comentario, usuario, publicacao, data_comentario, hora_comentario)
        VALUES (%s, %s, %s, %s, %s)
    """, (comentario, usuario, publicacao, data_comentario, hora_comentario))

    mysql.connection.commit()
    cur.close()

    return redirect(request.referrer or '/mural-cliente')


@app.route('/excluir_imagem_extra_cliente', methods=['POST'])
def excluir_imagem_extra_cliente():
    id = request.form.get('id')
    imagem_excluir = request.form.get('imagem')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM bordados WHERE id = %s", (id,))
    bordado = cur.fetchone()

    if bordado:
        imagens = bordado[4].split(',') if bordado[4] else []
        imagens = [img.strip() for img in imagens if img.strip() != imagem_excluir]
        nova_string = ','.join(imagens)

        cur.execute("UPDATE bordados SET imagens_extras = %s WHERE id = %s", (nova_string, id))
        mysql.connection.commit()
        cur.close()

    return redirect(url_for('editar-bordado-cliente', id=id))


#DEF ADMINISTRADORES
@app.route('/inicioadm')
def inicioadm():
    if not verificar_admin():
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM iniciodb")
    dados = cur.fetchall()

    cur.execute("SHOW COLUMNS FROM iniciodb")
    colunas = [col[0] for col in cur.fetchall()]

    
    cur.close()

    iniciodb = [dict(zip(colunas, linha)) for linha in dados]
    
    return render_template('administradores/inicioadm.html', iniciodb=iniciodb)

@app.route('/excluir_pedidoadm/<codigo_pedido>', methods=['POST'])
def excluir_pedidoadm(codigo_pedido):
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM pedidos WHERE codigo_pedido = %s", (codigo_pedido,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('pedidos'))

@app.route('/muraladm', methods=['GET', 'POST'])
def muraladm():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()

    if request.method == 'POST':
        legenda = request.form.get('legenda')
        usuario = session.get('usuario')
        fotos_arquivos = request.files.getlist('fotos')
        fotos_nomes = []

        for foto in fotos_arquivos:
            if foto and foto.filename:
                nome_arquivo = f"mural_{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto.filename}"
                caminho = os.path.join('static/imagens/mural', nome_arquivo)
                foto.save(caminho)
                fotos_nomes.append(nome_arquivo)

        fotos = ','.join(fotos_nomes)
        curtidas = 0
        publicacao = gerar_publicacao()
        agora = datetime.now()

        cur.execute("""
            INSERT INTO mural (publicacao, usuario, fotos, curtidas, legendas, data_publicacao, hora_publicacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (publicacao, usuario, fotos, curtidas, legenda, agora.date(), agora.time()))
        mysql.connection.commit()

    # Buscar todas as publicações com dados do usuário, sem usar GROUP BY
    cur.execute("""
        SELECT m.publicacao, m.usuario, m.fotos, m.curtidas, m.legendas, m.data_publicacao, m.hora_publicacao,
               u.foto, u.nome, u.sobrenome
        FROM mural m
        JOIN usuarios u ON m.usuario = u.usuario
        ORDER BY m.data_publicacao DESC, m.hora_publicacao DESC
    """)
    mural_dados = cur.fetchall()

    colunas_mural = ['publicacao', 'usuario', 'fotos', 'curtidas', 'legendas', 'data_publicacao', 'hora_publicacao',
                     'foto', 'nome', 'sobrenome']

    # Filtrar duplicatas por publicacao manualmente
    publicacoes_vistas = set()
    mural = []
    for linha in mural_dados:
        item = dict(zip(colunas_mural, linha))
        if item['publicacao'] not in publicacoes_vistas:
            mural.append(item)
            publicacoes_vistas.add(item['publicacao'])

    # Buscar comentários para cada publicação
    comentarios_por_post = {}
    cur.execute("SHOW COLUMNS FROM comentarios")
    colunas_coment = [col[0] for col in cur.fetchall()]

    for item in mural:
        publicacao = item['publicacao']
        cur.execute("""
            SELECT * FROM comentarios WHERE publicacao = %s ORDER BY data_comentario DESC, hora_comentario DESC
        """, (publicacao,))
        dados_coment = cur.fetchall()
        comentarios_por_post[publicacao] = [dict(zip(colunas_coment, linha)) for linha in dados_coment]

    cur.close()

    return render_template('administradores/muraladm.html', mural=mural, comentarios_por_post=comentarios_por_post)



@app.route('/detalhesadm/<int:id>')
def detalhesadm(id):
    if not verificar_admin():
        return redirect('/login')

    try:
        tema = request.args.get('tema')
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM bordados WHERE id = %s", (id,))
        resultado = cursor.fetchone()

        cursor.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cursor.fetchall()]
        cursor.close()

        if resultado:
            bordado = dict(zip(colunas, resultado))
            imagens = []
            if bordado.get("imagem"):
                imagens.append(bordado["imagem"])

            if bordado.get("imagens_extras"):
                extras = [img.strip() for img in bordado["imagens_extras"].split(",") if img.strip()]
                imagens.extend(extras)

            bordado["imagens"] = imagens
            cursor = mysql.connection.cursor()

            if not tema or tema.lower() == "todos":
                cursor.execute("SELECT * FROM bordados ORDER BY nome ASC")
            else:
                cursor.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))

            bordados_com_tema = cursor.fetchall()
            cursor.close()

            bordado_ids = [b[0] for b in bordados_com_tema]
            current_index = bordado_ids.index(id)

            next_id = bordado_ids[(current_index + 1) % len(bordado_ids)]
            prev_id = bordado_ids[(current_index - 1) % len(bordado_ids)]

            return render_template('administradores/detalhesadm.html', bordado=bordado, tema=tema, next_id=next_id, prev_id=prev_id)
        else:
            return "<p>Bordado não encontrado.</p>"

    except Exception as e:
        return f"<p>Erro ao carregar detalhes: {str(e)}</p>"
    
@app.route('/configuracoes' , methods=['GET', 'POST'])
def configuracoes():
    if not verificar_admin():
        return redirect('/login')

    return render_template('administradores/configuracoes.html')    

@app.route('/editar-bordado/<int:id>', methods=['GET', 'POST'])
def editar_bordado(id):
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    
    cur.execute("SELECT * FROM bordados WHERE id = %s", (id,))
    linha = cur.fetchone()

    if not linha:
        return "Bordado não encontrado", 404

    cur.execute("SHOW COLUMNS FROM bordados")
    colunas = [col[0] for col in cur.fetchall()]
    bordado = dict(zip(colunas, linha))
    cur.close()

    if bordado['imagens_extras'] is None:
        bordado['imagens_extras'] = ''

    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        preco = request.form['preco']
        temas = request.form['temas']

        imagem = request.files.get('imagem')
        if imagem and imagem.filename:
            nome_imagem = secure_filename(imagem.filename)
            imagem.save(os.path.join('static/imagens', nome_imagem))
        else:
            nome_imagem = bordado['imagem']

        imagens_extras = request.files.getlist('imagem_bordado_extra')
        novas_imagens_extras = []

        for img in imagens_extras:
            if img and img.filename != '':
                nome_arquivo = secure_filename(img.filename)
                img.save(os.path.join('static/imagens', nome_arquivo))
                novas_imagens_extras.append(nome_arquivo)

        if novas_imagens_extras:
            if bordado['imagens_extras']:
                imagens_extras_str = bordado['imagens_extras'] + ',' + ','.join(novas_imagens_extras)
            else:
                imagens_extras_str = ','.join(novas_imagens_extras)
        else:
            imagens_extras_str = bordado['imagens_extras']

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE bordados SET nome = %s, descricao = %s, preco = %s,
            temas = %s, imagem = %s, imagens_extras = %s WHERE id = %s
        """, (nome, descricao, preco, temas, nome_imagem, imagens_extras_str, id))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('detalhesadm', id=id))

    cur.close()
    return render_template('administradores/editar-bordado.html', bordado=bordado)

@app.route('/pedidos')
def pedidos():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()

    query = """
        SELECT p.*, b.imagem, b.preco, b.descricao, p.quantidade
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.status_pedido = 'Pendente'
    """
    cur.execute(query)
    dados = cur.fetchall()
    colunas = [desc[0] for desc in cur.description]
    pedidos = [dict(zip(colunas, linha)) for linha in dados]
    codigo_pedido = request.args.get('codigo_pedido', '')
    cur.close()
    pedidos_agrupados = defaultdict(list)
    for pedido in pedidos:
        pedidos_agrupados[pedido['codigo_pedido']].append(pedido)

    pedidos_agrupados = list(pedidos_agrupados.items())
    total_pedidos = len(pedidos_agrupados)
    valor_pedidos = sum(pedido['preco'] * pedido['quantidade'] for pedido in pedidos)

    return render_template('administradores/pedidos.html', pedidos=pedidos, codigo_pedido=codigo_pedido, pedidos_agrupados=pedidos_agrupados, total_pedidos=total_pedidos, valor_pedidos=valor_pedidos)

@app.route('/detalhe_pedido/<codigo_pedido>')
def detalhe_pedido(codigo_pedido):
    if not verificar_admin():
        return redirect('/login')

    cur = mysql.connection.cursor()

    query = """
        SELECT p.*, p.id_bordado, p.codigo_pedido, p.nome_cliente, p.tel_cliente, p.fotos,
               p.email_cliente, p.status_pedido, p.data_pedido, p.descricao AS pedido_descricao, p.quantidade,
               b.id AS bordado_id, b.imagem, b.preco, b.descricao AS bordado_descricao
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.codigo_pedido = %s
    """
    cur.execute(query, (codigo_pedido,))
    resultados = cur.fetchall()

    if not resultados:
        cur.close()
        return "Pedido não encontrado", 404

    colunas = [desc[0] for desc in cur.description]
    pedidos = [dict(zip(colunas, linha)) for linha in resultados]
   
    cur.close()
    return render_template('administradores/detalhe_pedido.html', pedidos=pedidos)

@app.route('/status_pedido', methods=['POST'])
def status_pedido():
    if not verificar_admin():
        return redirect('/login')

    for key in request.form:
        if key.startswith("status"):
            novo_status = request.form[key]
            break
    else:
        return "Dados inválidos", 400

    codigo_pedido = request.form.get('codigo_pedido')
    if not codigo_pedido:
        return "Código do pedido não enviado", 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE pedidos SET status_pedido = %s WHERE codigo_pedido = %s", (novo_status, codigo_pedido))
        mysql.connection.commit()
        cur.close()
        return redirect(f'/pedidos?codigo_pedido={codigo_pedido}')
    except Exception as e:
        return f"Erro: {e}", 500

@app.route('/processo')
def processo():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()

    query = """
        SELECT p.*, b.imagem, b.preco, b.descricao, p.quantidade
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.status_pedido = 'Em andamento'
    """
    cur.execute(query)
    dados = cur.fetchall()
    colunas = [desc[0] for desc in cur.description]
    pedidos = [dict(zip(colunas, linha)) for linha in dados]
    codigo_pedido = request.args.get('codigo_pedido', '')
    cur.close()
    pedidos_agrupados = defaultdict(list)
    for pedido in pedidos:
        pedidos_agrupados[pedido['codigo_pedido']].append(pedido)

    pedidos_agrupados = list(pedidos_agrupados.items())
    total_pedidos = len(pedidos_agrupados)
    valor_pedidos = sum(pedido['preco'] * pedido['quantidade'] for pedido in pedidos)


    return render_template('administradores/processo.html', pedidos=pedidos, codigo_pedido=codigo_pedido, pedidos_agrupados=pedidos_agrupados, total_pedidos=total_pedidos, valor_pedidos=valor_pedidos)



@app.route('/finalizado')
def finalizado():
    if not verificar_admin():
        return redirect('/login')
   
    cur = mysql.connection.cursor()
    query = """
        SELECT p.*, b.imagem, b.preco, b.descricao, p.quantidade
        FROM pedidos p
        JOIN bordados b ON p.id_bordado = b.id
        WHERE p.status_pedido = 'Finalizado'
    """
    cur.execute(query)
    dados = cur.fetchall()
    colunas = [desc[0] for desc in cur.description]
    pedidos = [dict(zip(colunas, linha)) for linha in dados]
    codigo_pedido = request.args.get('codigo_pedido', '')
    cur.close()
    pedidos_agrupados = defaultdict(list)
    for pedido in pedidos:
        pedidos_agrupados[pedido['codigo_pedido']].append(pedido)

    pedidos_agrupados = list(pedidos_agrupados.items())
    total_pedidos = len(pedidos_agrupados)
    valor_pedidos = sum(pedido['preco'] * pedido['quantidade'] for pedido in pedidos)


    return render_template('administradores/finalizado.html', pedidos=pedidos, codigo_pedido=codigo_pedido, pedidos_agrupados=pedidos_agrupados, total_pedidos=total_pedidos, valor_pedidos=valor_pedidos)

@app.route('/catalogoadm')
def catalogoadm():
    if not verificar_admin():
        return redirect('/login')

    try:
        tema = request.args.get('tema')
        cur = mysql.connection.cursor()

        cur.execute("SELECT DISTINCT temas FROM bordados")
        todos_os_temas = cur.fetchall()

        lista_temas = set()
        for linha in todos_os_temas:
            temas_str = linha[0]
            if temas_str:
                temas = [t.strip().capitalize() for t in temas_str.split(',')]
                lista_temas.update(temas)

        temas_ordenados = sorted(lista_temas)

        if tema:
            cur.execute("SELECT * FROM bordados WHERE LOWER(temas) LIKE %s ORDER BY nome ASC", ('%' + tema.lower() + '%',))
        else:
            cur.execute("SELECT * FROM bordados ORDER BY nome ASC")

        dados = cur.fetchall()
        cur.execute("SHOW COLUMNS FROM bordados")
        colunas = [col[0] for col in cur.fetchall()]
        cur.close()

        bordados = [dict(zip(colunas, linha)) for linha in dados]

        return render_template(
            'administradores/catalogoadm.html',
            bordados=bordados,
            temas_ordenados=temas_ordenados,
            tema_atual=tema
        )
    except Exception as e:
        return f"<p>Erro ao carregar catálogo: {str(e)}</p>"


@app.route('/editar/<int:id>', methods=['POST'])
def editar_item(id):
    if not verificar_admin():
        return redirect('/login')

    novo_titulo = request.form['titulo']
    novo_texto = request.form['textos']
    imagem_arquivo = request.files.get('imagens')

    if imagem_arquivo and imagem_arquivo.filename != '':

        from werkzeug.utils import secure_filename
        nome_arquivo = secure_filename(imagem_arquivo.filename)
        caminho = os.path.join('static/imagens', nome_arquivo)
        imagem_arquivo.save(caminho)
        nova_imagem = nome_arquivo
    else:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT imagens FROM iniciodb WHERE id = %s", (id,))
        resultado = cursor.fetchone()
        nova_imagem = resultado[0]
        cursor.close()

    cursor = mysql.connection.cursor()
    sql = "UPDATE iniciodb SET titulo = %s, textos = %s, imagens = %s WHERE id = %s"
    valores = (novo_titulo, novo_texto, nova_imagem, id)
    cursor.execute(sql, valores)
    mysql.connection.commit()
    cursor.close()

    return redirect('/inicioadm')  

@app.route('/administradores' , methods=['GET', 'POST'])
def administradores():
    if not verificar_admin():
        return redirect('/login')
    
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM usuarios where tipo ='administrador'")
    dados = cur.fetchall() 

    colunas = [desc[0] for desc in cur.description]

    cur.close()

    usuarios = [dict(zip(colunas, linha)) for linha in dados]
    return render_template('administradores/administradores.html', usuarios=usuarios)

@app.route('/clientes' , methods=['GET', 'POST'])
def clientes():
    if not verificar_admin():
        return redirect('/login')
   
    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM usuarios where tipo ='cliente'")
    
    dados = cur.fetchall() 
    
    colunas = [desc[0] for desc in cur.description]

    cur.close()
    
    usuarios = [dict(zip(colunas, linha)) for linha in dados]
    return render_template('administradores/cliente.html', usuarios=usuarios)


@app.route('/editar_contatos/<int:id>', methods=['POST'])
def editar_contatos(id):
    if not verificar_admin():
        return redirect('/login')
   
    novo_numero = request.form['numero']
    novo_email = request.form['email']
    novo_insta = request.form['insta']


    cursor = mysql.connection.cursor()
    sql = "UPDATE contatos SET numero = %s, email = %s, insta = %s WHERE id = %s"
    valores = (novo_numero, novo_email, novo_insta, id)
    cursor.execute(sql, valores)
    mysql.connection.commit()
    cursor.close()

    return redirect('/configuracoes') 

@app.route('/editar_administradores', methods=['POST'])
def editar_administradores():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    tipo = request.form.get('tipo')
    usuario = request.form.get('usuario')
    cur.execute("""
        UPDATE usuarios
        SET tipo = %s 
        WHERE usuario = %s
    """, (tipo, usuario))

    mysql.connection.commit()
    cur.close()
    return redirect('/administradores')



@app.route('/editar_clientes', methods=['POST'])
def editar_clientes():
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    tipo = request.form.get('tipo')
    usuario = request.form.get('usuario')
    cur.execute("""
        UPDATE usuarios
        SET tipo = %s 
        WHERE usuario = %s
    """, (tipo, usuario))

    mysql.connection.commit()
    cur.close()
    return redirect('/clientes')

@app.route('/excluir_usuario/<int:id>', methods=['POST'])
def excluir_usuario(id):
    if not verificar_admin():
        return redirect('/login')
    
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM usuarios WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    

    return redirect('/clientes')



@app.route('/adicionar-bordado', methods=['GET', 'POST'])
def adicionar_bordado():
    if not verificar_admin():
        return redirect('/login')
    
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        preco = request.form['preco']
        temas = request.form['temas']
        imagem_bordado = request.files['imagem']

        imagem_bordado_extra = request.files.getlist('imagem_bordado_extra')
        imagens_extra_salvas = []
        
        for imagem in imagem_bordado_extra:
            if imagem.filename != '': 
                nome_arquivo_extra = secure_filename(imagem.filename)
                caminho_extra = os.path.join('static/imagens', nome_arquivo_extra)
                imagem.save(caminho_extra)
                imagens_extra_salvas.append(nome_arquivo_extra) 

        if imagem_bordado and imagem_bordado.filename != '':
            nome_arquivo = secure_filename(imagem_bordado.filename)
            caminho = os.path.join('static/imagens', nome_arquivo)
            imagem_bordado.save(caminho)
            nova_imagem = nome_arquivo
        else:
            nova_imagem = None

        imagens_extra_string = ','.join(imagens_extra_salvas) if imagens_extra_salvas else None

        cursor = mysql.connection.cursor()
        sql = "INSERT INTO bordados (nome, descricao, preco, temas, imagem, imagens_extras) VALUES (%s, %s, %s,%s, %s,%s)"
        valores = (nome, descricao, preco, temas, nova_imagem, imagens_extra_string)
        cursor.execute(sql, valores)
        mysql.connection.commit()
        cursor.close()

        return redirect('/catalogoadm')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM bordados")
    dados = cur.fetchall()

    cursor = mysql.connection.cursor()
    cursor.execute("SHOW COLUMNS FROM bordados")
    colunas = [col[0] for col in cursor.fetchall()]

    cur.close()
    cursor.close()

    bordados = [dict(zip(colunas, linha)) for linha in dados]

    return render_template('administradores/adicionar-bordado.html', bordados=bordados)

@app.route('/confirmar_exclusao/<int:bordado_id>', methods=['POST'])
def confirmar_exclusao(bordado_id):
    if not verificar_admin():
        return redirect('/login')
   
    cursor = mysql.connection.cursor()
    sql = "DELETE FROM bordados WHERE id = %s"
    cursor.execute(sql, (bordado_id,))
    mysql.connection.commit()
    cursor.close()


    return redirect('/catalogoadm') 

@app.route('/editar_perfil/', methods=['POST'])
def editar_perfil():
    usuario_atual = session.get('usuario')
    if not verificar_cliente():
        return redirect('/login')

    mensagem = None
    novo_nome = request.form['nome']
    novo_sobrenome = request.form['sobrenome']
    novo_usuario = request.form['usuario']

    senha_atual_form = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    foto = request.files.get('imagem')

    cur = mysql.connection.cursor()

    # Primeiro busca o ID, senha e foto do usuário atual
    cur.execute("SELECT id, senha, foto FROM usuarios WHERE usuario = %s", (usuario_atual,))
    resultado = cur.fetchone()

    if not resultado:
        cur.close()
        mensagem = 'Usuário não encontrado.'
        return render_template('clientes/perfil.html', mensagem=mensagem, usuario=usuario_atual, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))

    id_usuario, senha_armazenada, foto_atual = resultado

    # Verificar se o NOVO nome de usuário já existe em outro usuário
    cur.execute("SELECT id FROM usuarios WHERE usuario = %s AND id != %s", (novo_usuario, id_usuario))
    usuario_existente = cur.fetchone()

    if usuario_existente:
        cur.close()
        mensagem = 'Este nome de usuário já está em uso. Escolha outro.'
        return render_template('clientes/perfil.html', mensagem=mensagem, usuario=usuario_atual, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))

    # Se o usuário quiser trocar de senha, exigir confirmação da senha atual
    if nova_senha:
        if senha_atual_form != senha_armazenada:
            cur.close()
            mensagem = 'Senha atual incorreta.'
            return render_template('clientes/perfil.html', mensagem=mensagem, usuario=usuario_atual, nome=session.get('nome'), sobrenome=session.get('sobrenome'), foto=session.get('foto'))
        senha_para_salvar = nova_senha
    else:
        senha_para_salvar = senha_armazenada

    # Foto de perfil
    if foto and foto.filename:
        nova_foto = secure_filename(foto.filename)
        foto.save(os.path.join('static/imagens', nova_foto))
    else:
        nova_foto = foto_atual

    # Atualiza no banco
    sql = """
        UPDATE usuarios 
        SET nome = %s, sobrenome = %s, foto = %s, senha = %s, usuario = %s
        WHERE id = %s
    """
    valores = (novo_nome, novo_sobrenome, nova_foto, senha_para_salvar, novo_usuario, id_usuario)
    cur.execute(sql, valores)
    mysql.connection.commit()
    cur.close()

    # Atualiza sessão
    session['usuario'] = novo_usuario
    session['nome'] = novo_nome
    session['sobrenome'] = novo_sobrenome
    session['foto'] = nova_foto

    mensagem = 'Perfil atualizado com sucesso!'
    return render_template('clientes/perfil.html', mensagem=mensagem, usuario=novo_usuario, nome=novo_nome, sobrenome=novo_sobrenome, foto=nova_foto)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Usa a porta do Render ou 5000 localmente
    app.run(host="0.0.0.0", port=port)