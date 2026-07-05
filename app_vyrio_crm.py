import sqlite3
import re
import urllib.parse
from datetime import date, datetime, timedelta
import random

import pandas as pd
import plotly.express as px
import streamlit as st

APP_TITLE = "Vyrio Sistemas — CRM de Vendas e Cobrança"
LOGO_URL = "https://i.postimg.cc/2j984FL7/Whats-App-Image-2026-06-29-at-16-41-48-(1).jpg"
DB_PATH = "vyrio_crm.db"

STATUS_CLIENTE = ["Ativo", "Inativo", "Bloqueado", "Em negociação", "Convertido", "Perdido"]
TIPOS_CARTEIRA = ["Vendas", "Cobrança", "Mista"]
STATUS_COBRANCA = ["Aberto", "Em negociação", "Acordo enviado", "Acordo fechado", "Pagamento parcial", "Pago", "Quebra de acordo", "Sem contato", "Recusou negociação", "Pré-jurídico", "Jurídico", "Baixado", "Cancelado"]
ETAPAS_VENDAS = ["Lead recebido", "Primeiro contato", "Qualificação", "Diagnóstico", "Proposta enviada", "Negociação", "Contrato enviado", "Ganho", "Perdido"]
CATEGORIAS = ["Cliente novo", "Cliente recorrente", "Cliente inadimplente", "Cliente recuperado", "Cliente VIP", "Cliente estratégico", "Lead frio", "Lead morno", "Lead quente"]
SEGMENTACOES = ["Alto valor", "Baixo valor", "Capital", "Interior", "Digital", "Telefone", "Pré-jurídico", "Cross-sell", "Reativação"]
CANAIS = ["Ligação", "WhatsApp", "E-mail", "SMS", "Reunião", "Visita", "Sistema", "Outro"]
PRIORIDADES = ["Baixa", "Média", "Alta", "Urgente"]
STATUS_TAREFA = ["Pendente", "Em andamento", "Concluída", "Cancelada", "Vencida"]

st.set_page_config(page_title=APP_TITLE, page_icon="📊", layout="wide")
st.markdown("""
<style>
.main .block-container{padding-top:1rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#020617,#0f172a)}
[data-testid="stSidebar"] *{color:#e5e7eb!important}
.hero{padding:24px;border-radius:22px;background:linear-gradient(135deg,#020617,#0f172a,#082f49);color:white;margin-bottom:18px;box-shadow:0 14px 38px rgba(2,6,23,.18)}
.hero h1{font-size:34px;margin:0 0 6px 0}.hero p{color:#cbd5e1;margin:0;font-size:15px}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;background:#e0f2fe;color:#075985;font-weight:700;font-size:12px;margin-right:5px;margin-bottom:5px}
.lgpd{padding:14px 16px;background:#f0f9ff;border-left:5px solid #38bdf8;border-radius:12px;margin:10px 0;color:#0f172a}
a.wpp{display:inline-block;padding:.55rem .85rem;background:#16a34a;color:white!important;border-radius:12px;text-decoration:none;font-weight:800}
.stButton button,.stDownloadButton button{border-radius:12px;font-weight:700}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def exec_sql(sql, params=()):
    cur = conn().cursor(); cur.execute(sql, params); conn().commit(); return cur.lastrowid

def qdf(sql, params=()):
    return pd.read_sql_query(sql, conn(), params=params)

def qone(sql, params=()):
    cur = conn().cursor(); cur.execute(sql, params); row = cur.fetchone(); return dict(row) if row else None

def count_table(tabela):
    return int(qone(f"SELECT COUNT(*) total FROM {tabela}")["total"])

def init_db():
    sqls = [
        """CREATE TABLE IF NOT EXISTS configuracoes(chave TEXT PRIMARY KEY, valor TEXT)""",
        """CREATE TABLE IF NOT EXISTS carteiras(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, codigo TEXT, tipo TEXT, cliente_contratante TEXT, responsavel TEXT, status TEXT, meta_recuperacao REAL, meta_vendas REAL, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS clientes(id INTEGER PRIMARY KEY AUTOINCREMENT, codigo_externo TEXT, nome TEXT NOT NULL, tipo_pessoa TEXT, documento TEXT, data_nascimento TEXT, idade INTEGER, faixa_idade TEXT, categoria TEXT, segmentacao TEXT, carteira_id INTEGER, status TEXT, responsavel TEXT, origem TEXT, cidade TEXT, estado TEXT, endereco TEXT, observacoes TEXT, data_cadastro TEXT, data_atualizacao TEXT)""",
        """CREATE TABLE IF NOT EXISTS contatos(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, nome_contato TEXT, telefone TEXT, email TEXT, pais TEXT DEFAULT '55', status_telefone TEXT, possui_whatsapp TEXT, principal TEXT, preferencia_canal TEXT, observacoes TEXT, data_validacao TEXT)""",
        """CREATE TABLE IF NOT EXISTS dividas(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, carteira_id INTEGER, contrato TEXT, produto TEXT, numero_titulo TEXT, data_vencimento TEXT, dias_atraso INTEGER, faixa_atraso TEXT, valor_original REAL, valor_atualizado REAL, valor_desconto REAL, valor_minimo REAL, status TEXT, responsavel TEXT, etapa TEXT, data_proximo_followup TEXT, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS acordos(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, divida_id INTEGER, data_acordo TEXT, valor_negociado REAL, valor_entrada REAL, quantidade_parcelas INTEGER, status TEXT, responsavel TEXT, canal TEXT, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS pagamentos(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, divida_id INTEGER, acordo_id INTEGER, data_pagamento TEXT, valor_pago REAL, forma_pagamento TEXT, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS oportunidades(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, nome TEXT, produto_servico TEXT, valor_estimado REAL, etapa TEXT, probabilidade REAL, origem TEXT, responsavel TEXT, data_abertura TEXT, data_prevista_fechamento TEXT, status TEXT, motivo_perda TEXT, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS interacoes(id INTEGER PRIMARY KEY AUTOINCREMENT, cliente_id INTEGER, tipo TEXT, canal TEXT, data_hora TEXT, responsavel TEXT, resultado TEXT, descricao TEXT, proxima_acao TEXT, data_proximo_contato TEXT)""",
        """CREATE TABLE IF NOT EXISTS tarefas(id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT, descricao TEXT, cliente_id INTEGER, tipo TEXT, responsavel TEXT, prioridade TEXT, status TEXT, data_criacao TEXT, data_vencimento TEXT, data_conclusao TEXT, observacoes TEXT)""",
        """CREATE TABLE IF NOT EXISTS logs_auditoria(id INTEGER PRIMARY KEY AUTOINCREMENT, tabela TEXT, registro_id INTEGER, acao TEXT, descricao TEXT, usuario TEXT, data_hora TEXT)""",
    ]
    for sql in sqls: exec_sql(sql)

def moeda(v):
    try: return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception: return "R$ 0,00"

def clean_numero(v): return re.sub(r"\D", "", str(v or ""))

def parse_data(v):
    if not v: return None
    if isinstance(v, date): return v
    try: return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except Exception: return None

def calcular_idade(nascimento):
    nasc = parse_data(nascimento)
    if not nasc: return None
    hoje = date.today()
    return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))

def classificar_idade(i):
    if i is None: return "Não informado"
    i = int(i)
    if i <= 18: return "Até 18 anos"
    if i <= 25: return "19 a 25 anos"
    if i <= 35: return "26 a 35 anos"
    if i <= 45: return "36 a 45 anos"
    if i <= 60: return "46 a 60 anos"
    return "Acima de 60 anos"

def calcular_atraso(vencimento):
    venc = parse_data(vencimento)
    return max(0, (date.today() - venc).days) if venc else 0

def classificar_atraso(dias):
    dias = int(dias or 0)
    if dias <= 0: return "Sem atraso"
    if dias <= 30: return "1 a 30 dias"
    if dias <= 60: return "31 a 60 dias"
    if dias <= 90: return "61 a 90 dias"
    if dias <= 180: return "91 a 180 dias"
    if dias <= 360: return "181 a 360 dias"
    return "Acima de 360 dias"

def whatsapp_url(numero, mensagem="", pais="55"):
    numero = clean_numero(numero); pais = clean_numero(pais) or "55"
    if numero.startswith("0"): numero = numero[1:]
    if not numero.startswith(pais): numero = pais + numero
    texto = urllib.parse.quote(mensagem or "")
    return f"https://web.whatsapp.com/send?phone={numero}" + (f"&text={texto}" if texto else "")

def botao_whatsapp(numero, mensagem="", label="Chamar no WhatsApp"):
    st.markdown(f'<a class="wpp" href="{whatsapp_url(numero, mensagem)}" target="_blank">💬 {label}</a>', unsafe_allow_html=True)

def get_config(chave, padrao=""):
    r = qone("SELECT valor FROM configuracoes WHERE chave=?", (chave,)); return r["valor"] if r else padrao

def set_config(chave, valor):
    exec_sql("INSERT INTO configuracoes(chave,valor) VALUES(?,?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, valor))

def hero(titulo, subtitulo):
    st.markdown(f'<div class="hero"><h1>{titulo}</h1><p>{subtitulo}</p></div>', unsafe_allow_html=True)

def baixar_csv(df, nome):
    st.download_button("Exportar CSV", df.to_csv(index=False, sep=";", encoding="utf-8-sig"), nome, "text/csv")

def mapa_clientes():
    df = qdf("SELECT id,nome FROM clientes ORDER BY nome")
    return {f"{r.nome} | ID {r.id}": int(r.id) for _, r in df.iterrows()}

def mapa_carteiras():
    df = qdf("SELECT id,nome FROM carteiras ORDER BY nome")
    return {f"{r.nome} | ID {r.id}": int(r.id) for _, r in df.iterrows()}

def atualizar_calculos():
    for _, r in qdf("SELECT id,data_nascimento FROM clientes").iterrows():
        i = calcular_idade(r.data_nascimento)
        exec_sql("UPDATE clientes SET idade=?, faixa_idade=? WHERE id=?", (i, classificar_idade(i), int(r.id)))
    for _, r in qdf("SELECT id,data_vencimento FROM dividas").iterrows():
        d = calcular_atraso(r.data_vencimento)
        exec_sql("UPDATE dividas SET dias_atraso=?, faixa_atraso=? WHERE id=?", (d, classificar_atraso(d), int(r.id)))

def log(tabela, registro_id, acao, descricao=""):
    exec_sql("INSERT INTO logs_auditoria(tabela,registro_id,acao,descricao,usuario,data_hora) VALUES(?,?,?,?,?,?)", (tabela, registro_id, acao, descricao, "Usuário local", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def seed_demo():
    if count_table("configuracoes") == 0:
        set_config("empresa", "Vyrio Sistemas")
        set_config("mensagem_cobranca", "Olá, {nome}. Tudo bem? Identificamos uma oportunidade de regularização disponível para você. Podemos te ajudar por aqui?")
        set_config("mensagem_vendas", "Olá, {nome}. Tudo bem? Temos uma condição especial disponível e gostaríamos de apresentar uma oportunidade para você.")
    if count_table("carteiras") == 0:
        for c in [("Carteira Vendas B2B","VEN-B2B","Vendas","","Gestor Comercial","Ativa",0,250000,"Prospecção B2B"),("Carteira Vendas B2C","VEN-B2C","Vendas","","Gestor Comercial","Ativa",0,120000,"Vendas B2C"),("Carteira Cobrança Early","COB-EARLY","Cobrança","Cliente A","Gestor Cobrança","Ativa",35,0,"Cobrança até 60 dias"),("Carteira Cobrança Pré-Judicial","COB-PJ","Cobrança","Cliente B","Gestor Cobrança","Ativa",25,0,"Pré-jurídico"),("Carteira Mista Estratégica","MISTA-01","Mista","Cliente C","Administrador","Ativa",30,180000,"Vendas e cobrança")]:
            exec_sql("INSERT INTO carteiras(nome,codigo,tipo,cliente_contratante,responsavel,status,meta_recuperacao,meta_vendas,observacoes) VALUES(?,?,?,?,?,?,?,?,?)", c)
    if count_table("clientes") > 0: return
    nomes = ["Ana Paula Martins","Carlos Roberto Silva","Mariana Oliveira","João Pedro Almeida","Fernanda Costa","Ricardo Souza","Patrícia Lima","Bruno Torres","Juliana Barbosa","Marcelo Ribeiro","Camila Nunes","Eduardo Gomes","Renata Rocha","Diego Fernandes","Larissa Cardoso","Felipe Santos","Beatriz Moreira","Gustavo Pereira","Aline Teixeira","Rafael Duarte"]
    carteiras = qdf("SELECT id FROM carteiras").id.tolist()
    for i, nome in enumerate(nomes, 1):
        nasc = date.today() - timedelta(days=random.randint(22*365, 65*365)); idade = calcular_idade(nasc)
        cid = exec_sql("""INSERT INTO clientes(codigo_externo,nome,tipo_pessoa,documento,data_nascimento,idade,faixa_idade,categoria,segmentacao,carteira_id,status,responsavel,origem,cidade,estado,endereco,observacoes,data_cadastro,data_atualizacao) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,date('now'),date('now'))""", (f"CLI-{i:04d}", nome, "Pessoa Física", str(random.randint(10000000000,99999999999)), nasc.isoformat(), idade, classificar_idade(idade), random.choice(CATEGORIAS), random.choice(SEGMENTACOES), random.choice(carteiras), random.choice(["Ativo","Em negociação","Convertido"]), random.choice(["Gestor Comercial","Gestor Cobrança","Operador 01"]), random.choice(["Importação","Indicação","Campanha"]), random.choice(["Porto Alegre","Canoas","Gravataí","Caxias do Sul"]), random.choice(["RS","SC","PR"]), "Rua Exemplo, 100", "Cliente fictício para teste."))
        tel = f"({random.randint(11,99)}) 9{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        exec_sql("INSERT INTO contatos(cliente_id,tipo,nome_contato,telefone,email,status_telefone,possui_whatsapp,principal,preferencia_canal,data_validacao) VALUES(?,?,?,?,?,?,?,?,?,date('now'))", (cid, "Celular", nome, tel, f"cliente{i}@exemplo.com", "Válido", random.choice(["Sim","Sim","Não","Não verificado"]), "Sim", "WhatsApp"))
        venc = date.today() - timedelta(days=random.randint(-10,420)); dias = calcular_atraso(venc); valor = round(random.uniform(300,9000),2)
        exec_sql("INSERT INTO dividas(cliente_id,carteira_id,contrato,produto,numero_titulo,data_vencimento,dias_atraso,faixa_atraso,valor_original,valor_atualizado,valor_desconto,valor_minimo,status,responsavel,etapa,data_proximo_followup,observacoes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (cid, random.choice(carteiras), f"CTR-{random.randint(10000,99999)}", random.choice(["Cartão","Empréstimo","Serviço","Contrato"]), f"TIT-{random.randint(100000,999999)}", venc.isoformat(), dias, classificar_atraso(dias), valor, round(valor*1.15,2), round(valor*.15,2), round(valor*.65,2), random.choice(["Aberto","Em negociação","Sem contato","Acordo enviado"]), random.choice(["Gestor Cobrança","Operador 01"]), "Contato inicial", (date.today()+timedelta(days=random.randint(1,10))).isoformat(), "Dívida fictícia."))
        exec_sql("INSERT INTO oportunidades(cliente_id,nome,produto_servico,valor_estimado,etapa,probabilidade,origem,responsavel,data_abertura,data_prevista_fechamento,status,observacoes) VALUES(?,?,?,?,?,?,?,?,date('now'),?,?,?)", (cid, f"Oportunidade {i}", random.choice(["Sistema CRM","BPO","Consultoria"]), round(random.uniform(1000,50000),2), random.choice(ETAPAS_VENDAS[:-2]), random.choice([10,25,40,60,80]), random.choice(["Site","Indicação","Prospecção"]), "Gestor Comercial", (date.today()+timedelta(days=random.randint(7,45))).isoformat(), "Aberta", "Oportunidade fictícia."))
        exec_sql("INSERT INTO tarefas(titulo,descricao,cliente_id,tipo,responsavel,prioridade,status,data_criacao,data_vencimento,observacoes) VALUES(?,?,?,?,?,?,?,date('now'),?,?)", (random.choice(["Retornar cliente","Enviar proposta","Confirmar pagamento"]), "Tarefa fictícia.", cid, random.choice(["Retornar ligação","Enviar proposta","Negociar dívida"]), random.choice(["Gestor Comercial","Gestor Cobrança","Operador 01"]), random.choice(PRIORIDADES), random.choice(["Pendente","Em andamento","Concluída"]), (date.today()+timedelta(days=random.randint(-3,10))).isoformat(), ""))

def page_dashboard():
    c1, c2 = st.columns([1,5]); c1.image(LOGO_URL, width=120)
    with c2: hero("Vyrio Sistemas", "CRM de Vendas e Cobrança | Clientes, carteiras, negociações, pipeline e recuperação")
    total = count_table("clientes"); wpp = qone("SELECT COUNT(*) total FROM contatos WHERE possui_whatsapp='Sim'")["total"]
    aberto = qone("SELECT COALESCE(SUM(valor_atualizado),0) total FROM dividas WHERE status NOT IN ('Pago','Baixado','Cancelado')")["total"]
    negociado = qone("SELECT COALESCE(SUM(valor_negociado),0) total FROM acordos")["total"]
    pago = qone("SELECT COALESCE(SUM(valor_pago),0) total FROM pagamentos")["total"]
    tarefas = qone("SELECT COUNT(*) total FROM tarefas WHERE status IN ('Pendente','Em andamento')")["total"]
    cols = st.columns(6); cols[0].metric("Clientes",total); cols[1].metric("WhatsApp",wpp); cols[2].metric("Em aberto",moeda(aberto)); cols[3].metric("Negociado",moeda(negociado)); cols[4].metric("Pago",moeda(pago)); cols[5].metric("Tarefas",tarefas)
    a,b = st.columns(2)
    with a:
        df = qdf("SELECT COALESCE(ca.nome,'Sem carteira') carteira, COUNT(cl.id) clientes FROM clientes cl LEFT JOIN carteiras ca ON ca.id=cl.carteira_id GROUP BY ca.nome")
        st.plotly_chart(px.bar(df, x="carteira", y="clientes", title="Clientes por carteira", text_auto=True), use_container_width=True)
    with b:
        df = qdf("SELECT faixa_atraso, COALESCE(SUM(valor_atualizado),0) valor FROM dividas GROUP BY faixa_atraso")
        st.plotly_chart(px.pie(df, names="faixa_atraso", values="valor", title="Valor por faixa de atraso"), use_container_width=True)
    a,b = st.columns(2)
    with a:
        df = qdf("SELECT etapa, COALESCE(SUM(valor_estimado),0) valor FROM oportunidades GROUP BY etapa")
        st.plotly_chart(px.bar(df, x="etapa", y="valor", title="Pipeline por etapa"), use_container_width=True)
    with b:
        df = qdf("SELECT canal, COUNT(*) interacoes FROM interacoes GROUP BY canal")
        if not df.empty: st.plotly_chart(px.bar(df, x="canal", y="interacoes", title="Interações por canal"), use_container_width=True)

def form_cliente():
    carteiras = mapa_carteiras()
    with st.form("form_cliente"):
        a,b,c = st.columns([2,1,1]); nome = a.text_input("Nome/Razão social *"); tipo = b.selectbox("Tipo", ["Pessoa Física","Pessoa Jurídica"]); documento = c.text_input("CPF/CNPJ")
        a,b,c,d = st.columns(4); codigo = a.text_input("Código externo"); nascimento = b.date_input("Nascimento/Abertura", date(1990,1,1)); categoria = c.selectbox("Categoria", CATEGORIAS); segmentacao = d.selectbox("Segmentação", SEGMENTACOES)
        a,b,c,d = st.columns(4); carteira = a.selectbox("Carteira", list(carteiras.keys())) if carteiras else None; status = b.selectbox("Status", STATUS_CLIENTE); responsavel = c.text_input("Responsável", "Operador 01"); origem = d.text_input("Origem", "Manual")
        a,b,c = st.columns(3); cidade = a.text_input("Cidade"); estado = b.text_input("Estado"); endereco = c.text_input("Endereço")
        obs = st.text_area("Observações"); ok = st.form_submit_button("Salvar cliente")
    if ok and nome:
        idade = calcular_idade(nascimento)
        cid = exec_sql("INSERT INTO clientes(codigo_externo,nome,tipo_pessoa,documento,data_nascimento,idade,faixa_idade,categoria,segmentacao,carteira_id,status,responsavel,origem,cidade,estado,endereco,observacoes,data_cadastro,data_atualizacao) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,date('now'),date('now'))", (codigo,nome,tipo,documento,nascimento.isoformat(),idade,classificar_idade(idade),categoria,segmentacao,carteiras.get(carteira),status,responsavel,origem,cidade,estado,endereco,obs))
        log("clientes", cid, "criação", f"Cliente {nome} cadastrado"); st.success("Cliente salvo."); st.rerun()

def page_clientes():
    hero("Clientes", "Cadastro, filtros, ficha completa, contatos, cobrança, vendas e histórico.")
    t1,t2,t3 = st.tabs(["Lista", "Novo cliente", "Ficha"])
    with t1:
        busca = st.text_input("Buscar por nome, documento, cidade ou responsável")
        where, p = "", []
        if busca: where = "WHERE nome LIKE ? OR documento LIKE ? OR cidade LIKE ? OR responsavel LIKE ?"; p = [f"%{busca}%"]*4
        df = qdf(f"SELECT id,codigo_externo,nome,tipo_pessoa,documento,idade,faixa_idade,categoria,segmentacao,status,responsavel,cidade,estado FROM clientes {where} ORDER BY nome", p)
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"clientes_vyrio.csv")
    with t2: form_cliente()
    with t3:
        clientes = mapa_clientes()
        if not clientes: st.info("Cadastre um cliente primeiro."); return
        cid = clientes[st.selectbox("Selecione", list(clientes.keys()))]; ficha_cliente(cid)

def ficha_cliente(cid):
    cl = qone("SELECT cl.*, ca.nome carteira FROM clientes cl LEFT JOIN carteiras ca ON ca.id=cl.carteira_id WHERE cl.id=?", (cid,))
    st.subheader(cl["nome"]); st.markdown(f"<span class='badge'>{cl.get('status')}</span><span class='badge'>{cl.get('categoria')}</span><span class='badge'>{cl.get('segmentacao')}</span><span class='badge'>{cl.get('carteira') or 'Sem carteira'}</span>", unsafe_allow_html=True)
    contato = qdf("SELECT * FROM contatos WHERE cliente_id=? AND possui_whatsapp='Sim' LIMIT 1", (cid,))
    if not contato.empty: botao_whatsapp(contato.iloc[0].telefone, get_config("mensagem_cobranca").replace("{nome}", cl["nome"].split()[0]), "Chamar cliente")
    abas = st.tabs(["Dados", "Contatos", "Cobranças", "Vendas", "Interações", "Tarefas"])
    with abas[0]: st.write(cl)
    with abas[1]: contatos_do_cliente(cid, cl["nome"])
    with abas[2]: st.dataframe(qdf("SELECT * FROM dividas WHERE cliente_id=?", (cid,)), use_container_width=True, hide_index=True)
    with abas[3]: st.dataframe(qdf("SELECT * FROM oportunidades WHERE cliente_id=?", (cid,)), use_container_width=True, hide_index=True)
    with abas[4]: st.dataframe(qdf("SELECT * FROM interacoes WHERE cliente_id=? ORDER BY data_hora DESC", (cid,)), use_container_width=True, hide_index=True)
    with abas[5]: st.dataframe(qdf("SELECT * FROM tarefas WHERE cliente_id=? ORDER BY data_vencimento", (cid,)), use_container_width=True, hide_index=True)

def contatos_do_cliente(cid, nome_cliente=""):
    df = qdf("SELECT * FROM contatos WHERE cliente_id=? ORDER BY principal DESC,id", (cid,)); st.dataframe(df, use_container_width=True, hide_index=True)
    for _, r in df.iterrows():
        if r.possui_whatsapp == "Sim" and r.telefone: botao_whatsapp(r.telefone, get_config("mensagem_cobranca").replace("{nome}", nome_cliente.split()[0]), f"WhatsApp {r.telefone}")
    with st.expander("Adicionar contato"): form_contato(cid, nome_cliente)

def form_contato(cliente_id=None, nome_cliente=""):
    clientes = mapa_clientes()
    with st.form("form_contato"):
        cli = None if cliente_id else st.selectbox("Cliente", list(clientes.keys()))
        a,b,c = st.columns(3); tipo = a.selectbox("Tipo", ["Celular","Telefone fixo","WhatsApp","E-mail","Comercial","Financeiro","Jurídico","Outro"]); telefone = b.text_input("Telefone"); email = c.text_input("E-mail")
        a,b,c = st.columns(3); wpp = a.selectbox("Possui WhatsApp", ["Sim","Não","Não verificado"]); status = b.selectbox("Status telefone", ["Válido","Inválido","Não testado","Sem resposta"]); principal = c.selectbox("Principal", ["Sim","Não"])
        obs = st.text_area("Observações"); ok = st.form_submit_button("Salvar contato")
    if ok:
        cid = cliente_id or clientes[cli]; nome = nome_cliente or qone("SELECT nome FROM clientes WHERE id=?", (cid,))["nome"]
        exec_sql("INSERT INTO contatos(cliente_id,tipo,nome_contato,telefone,email,status_telefone,possui_whatsapp,principal,preferencia_canal,observacoes,data_validacao) VALUES(?,?,?,?,?,?,?,?,?,?,date('now'))", (cid,tipo,nome,telefone,email,status,wpp,principal,"WhatsApp",obs))
        st.success("Contato salvo."); st.rerun()

def page_carteiras():
    hero("Carteiras", "Gestão de carteiras comerciais, cobrança, mistas, metas e desempenho.")
    df = qdf("SELECT ca.*, COUNT(cl.id) qtd_clientes, COALESCE(SUM(d.valor_atualizado),0) valor_aberto FROM carteiras ca LEFT JOIN clientes cl ON cl.carteira_id=ca.id LEFT JOIN dividas d ON d.carteira_id=ca.id GROUP BY ca.id ORDER BY ca.nome")
    st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"carteiras_vyrio.csv")
    with st.expander("Nova carteira"):
        with st.form("form_carteira"):
            a,b,c = st.columns(3); nome = a.text_input("Nome *"); codigo = b.text_input("Código"); tipo = c.selectbox("Tipo", TIPOS_CARTEIRA)
            a,b,c = st.columns(3); contratante = a.text_input("Cliente contratante"); responsavel = b.text_input("Responsável"); status = c.selectbox("Status", ["Ativa","Inativa","Pausada","Encerrada"])
            a,b = st.columns(2); meta_rec = a.number_input("Meta recuperação %", min_value=0.0); meta_vendas = b.number_input("Meta vendas R$", min_value=0.0)
            obs = st.text_area("Observações"); ok = st.form_submit_button("Salvar carteira")
        if ok and nome:
            exec_sql("INSERT INTO carteiras(nome,codigo,tipo,cliente_contratante,responsavel,status,meta_recuperacao,meta_vendas,observacoes) VALUES(?,?,?,?,?,?,?,?,?)", (nome,codigo,tipo,contratante,responsavel,status,meta_rec,meta_vendas,obs)); st.success("Carteira salva."); st.rerun()

def page_contatos():
    hero("Contatos", "Telefones, e-mails, status de WhatsApp e acionamento direto pelo WhatsApp Web.")
    t1,t2 = st.tabs(["Lista", "Novo contato"])
    with t1:
        busca = st.text_input("Buscar contato"); where,p = "",[]
        if busca: where="WHERE cl.nome LIKE ? OR co.telefone LIKE ? OR co.email LIKE ?"; p=[f"%{busca}%"]*3
        df = qdf(f"SELECT co.id, cl.nome cliente, co.tipo, co.telefone, co.email, co.status_telefone, co.possui_whatsapp, co.principal FROM contatos co JOIN clientes cl ON cl.id=co.cliente_id {where} ORDER BY cl.nome", p)
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"contatos_vyrio.csv")
        for _, r in df.head(20).iterrows():
            if r.possui_whatsapp == "Sim" and r.telefone:
                with st.container(border=True): st.write(f"**{r.cliente}** — {r.telefone}"); botao_whatsapp(r.telefone, get_config("mensagem_cobranca").replace("{nome}", str(r.cliente).split()[0]))
    with t2: form_contato()

def page_cobranca():
    hero("Cobrança", "Títulos, atraso, faixas de cobrança, acordos, pagamentos e follow-ups.")
    t1,t2,t3 = st.tabs(["Títulos", "Novo título", "Acordos"])
    with t1:
        faixa = st.selectbox("Filtrar faixa", ["Todas","Sem atraso","1 a 30 dias","31 a 60 dias","61 a 90 dias","91 a 180 dias","181 a 360 dias","Acima de 360 dias"]); status = st.selectbox("Filtrar status", ["Todos"]+STATUS_COBRANCA)
        where,p=[],[]
        if faixa != "Todas": where.append("d.faixa_atraso=?"); p.append(faixa)
        if status != "Todos": where.append("d.status=?"); p.append(status)
        ws = "WHERE " + " AND ".join(where) if where else ""
        df = qdf(f"SELECT d.id, cl.nome cliente, ca.nome carteira, d.contrato, d.produto, d.numero_titulo, d.data_vencimento, d.dias_atraso, d.faixa_atraso, d.valor_atualizado, d.valor_desconto, d.valor_minimo, d.status, d.responsavel, d.data_proximo_followup FROM dividas d JOIN clientes cl ON cl.id=d.cliente_id LEFT JOIN carteiras ca ON ca.id=d.carteira_id {ws} ORDER BY d.dias_atraso DESC", p)
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"cobranca_vyrio.csv")
    with t2: form_divida()
    with t3: form_acordo()

def form_divida():
    clientes, carteiras = mapa_clientes(), mapa_carteiras()
    if not clientes: st.info("Cadastre clientes primeiro."); return
    with st.form("form_divida"):
        cli = st.selectbox("Cliente", list(clientes.keys())); cart = st.selectbox("Carteira", list(carteiras.keys())) if carteiras else None
        a,b,c = st.columns(3); contrato = a.text_input("Contrato"); produto = b.text_input("Produto"); titulo = c.text_input("Número do título")
        a,b,c,d = st.columns(4); venc = a.date_input("Vencimento", date.today()); valor = b.number_input("Valor original", min_value=0.0); desconto = c.number_input("Desconto disponível", min_value=0.0); minimo = d.number_input("Valor mínimo", min_value=0.0)
        a,b,c = st.columns(3); status = a.selectbox("Status", STATUS_COBRANCA); responsavel = b.text_input("Responsável", "Operador 01"); follow = c.date_input("Próximo follow-up", date.today()+timedelta(days=1))
        obs = st.text_area("Observações"); ok = st.form_submit_button("Salvar título")
    if ok:
        dias = calcular_atraso(venc); atualizado = valor*1.15 if dias > 0 else valor
        exec_sql("INSERT INTO dividas(cliente_id,carteira_id,contrato,produto,numero_titulo,data_vencimento,dias_atraso,faixa_atraso,valor_original,valor_atualizado,valor_desconto,valor_minimo,status,responsavel,etapa,data_proximo_followup,observacoes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (clientes[cli],carteiras.get(cart),contrato,produto,titulo,venc.isoformat(),dias,classificar_atraso(dias),valor,atualizado,desconto,minimo,status,responsavel,"Contato inicial",follow.isoformat(),obs))
        st.success("Título salvo."); st.rerun()

def form_acordo():
    divs = qdf("SELECT d.id, cl.nome cliente, d.valor_atualizado FROM dividas d JOIN clientes cl ON cl.id=d.cliente_id WHERE d.status NOT IN ('Pago','Baixado','Cancelado') ORDER BY cl.nome")
    if divs.empty: st.info("Nenhum título aberto."); return
    op = {f"ID {r.id} | {r.cliente} | {moeda(r.valor_atualizado)}": int(r.id) for _, r in divs.iterrows()}; did = op[st.selectbox("Título", list(op.keys()))]; d = qone("SELECT * FROM dividas WHERE id=?", (did,))
    with st.form("form_acordo"):
        a,b,c = st.columns(3); valor = a.number_input("Valor negociado", min_value=0.0, value=float(d["valor_atualizado"] or 0)); entrada = b.number_input("Entrada", min_value=0.0); parcelas = c.number_input("Parcelas", min_value=1, value=1)
        a,b = st.columns(2); responsavel = a.text_input("Responsável", d["responsavel"] or "Operador 01"); canal = b.selectbox("Canal", CANAIS)
        obs = st.text_area("Observações"); ok = st.form_submit_button("Registrar acordo")
    if ok:
        aid = exec_sql("INSERT INTO acordos(cliente_id,divida_id,data_acordo,valor_negociado,valor_entrada,quantidade_parcelas,status,responsavel,canal,observacoes) VALUES(?,?,date('now'),?,?,?,?,?,?,?)", (d["cliente_id"], did, valor, entrada, int(parcelas), "Aberto", responsavel, canal, obs))
        exec_sql("UPDATE dividas SET status='Acordo fechado' WHERE id=?", (did,)); log("acordos", aid, "criação", "Acordo registrado"); st.success("Acordo registrado."); st.rerun()
    st.dataframe(qdf("SELECT a.id, cl.nome cliente, a.valor_negociado, a.status FROM acordos a JOIN clientes cl ON cl.id=a.cliente_id ORDER BY a.id DESC"), use_container_width=True, hide_index=True)

def page_vendas():
    hero("Vendas", "Funil comercial, oportunidades, previsão de receita e conversão.")
    t1,t2 = st.tabs(["Pipeline", "Nova oportunidade"])
    with t1:
        df = qdf("SELECT o.id, cl.nome cliente, o.nome, o.produto_servico, o.valor_estimado, o.etapa, o.probabilidade, o.status, o.responsavel, o.data_prevista_fechamento FROM oportunidades o JOIN clientes cl ON cl.id=o.cliente_id ORDER BY o.data_abertura DESC")
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"oportunidades_vyrio.csv")
        if not df.empty: st.plotly_chart(px.bar(df.groupby("etapa", as_index=False)["valor_estimado"].sum(), x="etapa", y="valor_estimado", title="Valor do pipeline por etapa"), use_container_width=True)
    with t2:
        clientes = mapa_clientes()
        if not clientes: st.info("Cadastre clientes primeiro."); return
        with st.form("form_oportunidade"):
            cli = st.selectbox("Cliente", list(clientes.keys())); a,b,c = st.columns(3); nome = a.text_input("Nome da oportunidade"); produto = b.text_input("Produto/Serviço"); valor = c.number_input("Valor estimado", min_value=0.0)
            a,b,c = st.columns(3); etapa = a.selectbox("Etapa", ETAPAS_VENDAS); prob = b.number_input("Probabilidade %", min_value=0.0, max_value=100.0, value=25.0); responsavel = c.text_input("Responsável", "Gestor Comercial")
            a,b = st.columns(2); origem = a.text_input("Origem", "Prospecção"); prevista = b.date_input("Previsão fechamento", date.today()+timedelta(days=30))
            obs = st.text_area("Observações"); ok = st.form_submit_button("Salvar oportunidade")
        if ok and nome:
            exec_sql("INSERT INTO oportunidades(cliente_id,nome,produto_servico,valor_estimado,etapa,probabilidade,origem,responsavel,data_abertura,data_prevista_fechamento,status,observacoes) VALUES(?,?,?,?,?,?,?,?,date('now'),?,?,?)", (clientes[cli],nome,produto,valor,etapa,prob,origem,responsavel,prevista.isoformat(),"Aberta",obs)); st.success("Oportunidade salva."); st.rerun()

def page_interacoes():
    hero("Interações", "Histórico de ligações, WhatsApp, e-mails, reuniões, propostas e negociações.")
    t1,t2 = st.tabs(["Histórico", "Nova interação"])
    with t1:
        df = qdf("SELECT i.id, cl.nome cliente, i.tipo, i.canal, i.data_hora, i.responsavel, i.resultado, i.descricao, i.proxima_acao, i.data_proximo_contato FROM interacoes i JOIN clientes cl ON cl.id=i.cliente_id ORDER BY i.data_hora DESC")
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"interacoes_vyrio.csv")
    with t2:
        clientes = mapa_clientes()
        with st.form("form_interacao"):
            cli = st.selectbox("Cliente", list(clientes.keys())); a,b,c = st.columns(3); tipo = a.selectbox("Tipo", ["Ligação ativa","Ligação receptiva","WhatsApp","E-mail","SMS","Reunião","Visita","Proposta","Negociação","Acordo","Pagamento","Reclamação","Anotação interna"]); canal = b.selectbox("Canal", CANAIS); responsavel = c.text_input("Responsável", "Operador 01")
            resultado = st.text_input("Resultado"); descricao = st.text_area("Descrição"); a,b = st.columns(2); proxima = a.text_input("Próxima ação"); data_prox = b.date_input("Próximo contato", date.today()+timedelta(days=1)); ok = st.form_submit_button("Salvar interação")
        if ok:
            exec_sql("INSERT INTO interacoes(cliente_id,tipo,canal,data_hora,responsavel,resultado,descricao,proxima_acao,data_proximo_contato) VALUES(?,?,?,?,?,?,?,?,?)", (clientes[cli],tipo,canal,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),responsavel,resultado,descricao,proxima,data_prox.isoformat())); st.success("Interação salva."); st.rerun()

def page_tarefas():
    hero("Tarefas e Follow-ups", "Controle de atividades, retornos, vencimentos e pendências.")
    t1,t2 = st.tabs(["Lista", "Nova tarefa"])
    with t1:
        df = qdf("SELECT t.id, t.titulo, cl.nome cliente, t.tipo, t.responsavel, t.prioridade, t.status, t.data_criacao, t.data_vencimento, t.data_conclusao, t.descricao FROM tarefas t LEFT JOIN clientes cl ON cl.id=t.cliente_id ORDER BY date(t.data_vencimento)")
        st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df,"tarefas_vyrio.csv")
    with t2:
        clientes = {"Sem cliente": None}; clientes.update(mapa_clientes())
        with st.form("form_tarefa"):
            titulo = st.text_input("Título *"); cli = st.selectbox("Cliente", list(clientes.keys())); a,b,c = st.columns(3); tipo = a.selectbox("Tipo", ["Retornar ligação","Enviar proposta","Enviar boleto","Confirmar pagamento","Negociar dívida","Atualizar cadastro","Validar contato","Reunião","Análise interna","Outro"]); responsavel = b.text_input("Responsável", "Operador 01"); prioridade = c.selectbox("Prioridade", PRIORIDADES)
            a,b = st.columns(2); status = a.selectbox("Status", STATUS_TAREFA); venc = b.date_input("Vencimento", date.today()+timedelta(days=1)); desc = st.text_area("Descrição"); ok = st.form_submit_button("Salvar tarefa")
        if ok and titulo:
            exec_sql("INSERT INTO tarefas(titulo,descricao,cliente_id,tipo,responsavel,prioridade,status,data_criacao,data_vencimento) VALUES(?,?,?,?,?,?,?,date('now'),?)", (titulo,desc,clientes[cli],tipo,responsavel,prioridade,status,venc.isoformat())); st.success("Tarefa salva."); st.rerun()

def page_relatorios():
    hero("Relatórios", "Consultas filtráveis e exportáveis para gestão executiva.")
    rel = st.selectbox("Relatório", ["Clientes","Contatos com WhatsApp","Contatos sem WhatsApp","Cobranças por faixa","Cobranças por status","Acordos","Oportunidades","Tarefas vencidas","Interações"])
    if rel == "Clientes": df = qdf("SELECT * FROM clientes ORDER BY nome")
    elif rel == "Contatos com WhatsApp": df = qdf("SELECT cl.nome cliente, co.telefone, co.email, co.possui_whatsapp FROM contatos co JOIN clientes cl ON cl.id=co.cliente_id WHERE co.possui_whatsapp='Sim'")
    elif rel == "Contatos sem WhatsApp": df = qdf("SELECT cl.nome cliente, co.telefone, co.email, co.possui_whatsapp FROM contatos co JOIN clientes cl ON cl.id=co.cliente_id WHERE co.possui_whatsapp<>'Sim'")
    elif rel == "Cobranças por faixa": df = qdf("SELECT faixa_atraso, COUNT(*) qtd, COALESCE(SUM(valor_atualizado),0) valor FROM dividas GROUP BY faixa_atraso")
    elif rel == "Cobranças por status": df = qdf("SELECT status, COUNT(*) qtd, COALESCE(SUM(valor_atualizado),0) valor FROM dividas GROUP BY status")
    elif rel == "Acordos": df = qdf("SELECT a.*, cl.nome cliente FROM acordos a JOIN clientes cl ON cl.id=a.cliente_id ORDER BY a.data_acordo DESC")
    elif rel == "Oportunidades": df = qdf("SELECT o.*, cl.nome cliente FROM oportunidades o JOIN clientes cl ON cl.id=o.cliente_id ORDER BY o.data_abertura DESC")
    elif rel == "Tarefas vencidas": df = qdf("SELECT t.*, cl.nome cliente FROM tarefas t LEFT JOIN clientes cl ON cl.id=t.cliente_id WHERE date(t.data_vencimento)<date('now') AND t.status NOT IN ('Concluída','Cancelada')")
    else: df = qdf("SELECT i.*, cl.nome cliente FROM interacoes i JOIN clientes cl ON cl.id=i.cliente_id ORDER BY i.data_hora DESC")
    st.dataframe(df, use_container_width=True, hide_index=True); baixar_csv(df, rel.lower().replace(" ","_") + "_vyrio.csv")

def page_importacao():
    hero("Importação de Dados", "Importação simples de clientes via CSV.")
    st.info("Modelo de colunas para clientes: nome, documento, telefone, email, cidade, estado")
    arq = st.file_uploader("Selecione um CSV", type=["csv"])
    if arq:
        df = pd.read_csv(arq, sep=None, engine="python", dtype=str).fillna("")
        st.dataframe(df.head(50), use_container_width=True)
        if st.button("Importar clientes"):
            imp = 0
            for _, r in df.iterrows():
                nome = r.get("nome", "")
                if not nome: continue
                cid = exec_sql("INSERT INTO clientes(nome,tipo_pessoa,documento,cidade,estado,status,data_cadastro,data_atualizacao,observacoes) VALUES(?,'Pessoa Física',?,?,?,'Ativo',date('now'),date('now'),'Importado via CSV')", (nome, r.get("documento",""), r.get("cidade",""), r.get("estado","")))
                if r.get("telefone","") or r.get("email",""):
                    exec_sql("INSERT INTO contatos(cliente_id,tipo,nome_contato,telefone,email,status_telefone,possui_whatsapp,principal,preferencia_canal,data_validacao) VALUES(?,'Celular',?,?,?,'Não testado','Não verificado','Sim','WhatsApp',date('now'))", (cid, nome, r.get("telefone",""), r.get("email","")))
                imp += 1
            st.success(f"{imp} clientes importados."); st.rerun()

def page_configuracoes():
    hero("Configurações", "Marca, mensagens padrão, parâmetros e boas práticas de LGPD.")
    st.image(LOGO_URL, width=190)
    with st.form("form_config"):
        empresa = st.text_input("Nome da empresa", get_config("empresa", "Vyrio Sistemas")); msg_cob = st.text_area("Mensagem padrão WhatsApp cobrança", get_config("mensagem_cobranca")); msg_ven = st.text_area("Mensagem padrão WhatsApp vendas", get_config("mensagem_vendas")); ok = st.form_submit_button("Salvar configurações")
    if ok:
        set_config("empresa", empresa); set_config("mensagem_cobranca", msg_cob); set_config("mensagem_vendas", msg_ven); st.success("Configurações salvas."); st.rerun()
    st.markdown("<div class='lgpd'><b>LGPD:</b> use dados pessoais apenas para finalidades legítimas, evite exposição desnecessária de CPF/CNPJ, registre alterações e evolua permissões de acesso antes de usar o sistema em produção.</div>", unsafe_allow_html=True)
    st.subheader("Auditoria"); st.dataframe(qdf("SELECT * FROM logs_auditoria ORDER BY data_hora DESC LIMIT 300"), use_container_width=True, hide_index=True)

def sidebar():
    with st.sidebar:
        st.image(LOGO_URL, use_container_width=True); st.markdown("## Vyrio Sistemas"); st.caption("CRM de Vendas e Cobrança")
        return st.radio("Menu", ["Dashboard Geral","Clientes","Carteiras","Contatos","Cobrança","Vendas","Interações","Tarefas e Follow-ups","Importação de Dados","Relatórios","Configurações"], label_visibility="collapsed")

def main():
    init_db(); seed_demo(); atualizar_calculos(); p = sidebar()
    paginas = {"Dashboard Geral":page_dashboard,"Clientes":page_clientes,"Carteiras":page_carteiras,"Contatos":page_contatos,"Cobrança":page_cobranca,"Vendas":page_vendas,"Interações":page_interacoes,"Tarefas e Follow-ups":page_tarefas,"Importação de Dados":page_importacao,"Relatórios":page_relatorios,"Configurações":page_configuracoes}
    paginas[p]()

if __name__ == "__main__":
    main()
